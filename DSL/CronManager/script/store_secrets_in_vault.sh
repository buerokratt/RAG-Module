#!/bin/bash

# Vault Secrets Storage Script
# This script stores LLM and embedding credentials in HashiCorp Vault

set -e  # Exit on any error

# Configuration
# Use VAULT_AGENT_URL which points to vault-agent-cron proxy
# The agent automatically injects the authentication token
VAULT_ADDR="${VAULT_AGENT_URL:-http://vault-agent-cron:8203}"

# Decryption Configuration
PRIVATE_KEY_CACHE=""
PRIVATE_KEY_PATH="secret/data/encryption/private_key"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# ============================================================================
# DECRYPTION FUNCTIONS (RSA-OAEP)
# ============================================================================

# Fetch private key from Vault
fetch_private_key() {
    if [ -n "$PRIVATE_KEY_CACHE" ]; then
        # Key already cached
        return 0
    fi
    
    log "Fetching private key from Vault..."
    
    # Convert path for KV v2 API
    local api_path=$(echo "$PRIVATE_KEY_PATH" | sed 's|^secret/|secret/data/|')
    
    # Fetch private key from Vault
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X GET \
        "$VAULT_ADDR/v1/$api_path")
    
    local http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if [[ "$http_code" -ne 200 ]]; then
        log "ERROR: Failed to fetch private key from Vault (HTTP $http_code)"
        log "Response: $body"
        exit 1
    fi
    
    # Extract private key from JSON response
    PRIVATE_KEY_CACHE=$(echo "$body" | grep -o '"key":"[^"]*"' | sed 's/"key":"//; s/"$//' | sed 's/\\n/\n/g')
    
    if [ -z "$PRIVATE_KEY_CACHE" ]; then
        log "ERROR: Private key is empty or could not be extracted"
        exit 1
    fi
    
    log "Private key fetched and cached successfully"
}

# Decrypt RSA-OAEP encrypted value
# Input: Base64-encoded encrypted value
# Output: Plaintext value
decrypt_rsa_oaep() {
    local encrypted_base64="$1"
    
    if [ -z "$encrypted_base64" ]; then
        log "ERROR: decrypt_rsa_oaep called with empty value"
        exit 1
    fi
    
    # Ensure private key is fetched
    fetch_private_key
    
    # Create temporary files for decryption
    local temp_dir=$(mktemp -d)
    local private_key_file="$temp_dir/private_key.pem"
    local encrypted_file="$temp_dir/encrypted.bin"
    local decrypted_file="$temp_dir/decrypted.txt"
    
    # Cleanup function
    cleanup_temp_files() {
        rm -rf "$temp_dir" 2>/dev/null || true
    }
    
    # Set trap to cleanup on exit
    trap cleanup_temp_files EXIT
    
    # Write private key to temp file
    echo "$PRIVATE_KEY_CACHE" > "$private_key_file"
    
    # Decode base64 and write to temp file
    echo "$encrypted_base64" | base64 -d > "$encrypted_file" 2>/dev/null || {
        log "ERROR: Failed to decode base64 encrypted value"
        cleanup_temp_files
        exit 1
    }
    
    # Decrypt using OpenSSL with RSA-OAEP padding
    openssl pkeyutl -decrypt \
        -inkey "$private_key_file" \
        -in "$encrypted_file" \
        -out "$decrypted_file" \
        -pkeyopt rsa_padding_mode:oaep \
        -pkeyopt rsa_oaep_md:sha256 \
        -pkeyopt rsa_mgf1_md:sha256 2>/dev/null || {
        log "ERROR: Decryption failed - invalid ciphertext or wrong key"
        cleanup_temp_files
        exit 1
    }
    
    # Read decrypted value
    local decrypted_value=$(cat "$decrypted_file")
    
    # Cleanup
    cleanup_temp_files
    
    if [ -z "$decrypted_value" ]; then
        log "ERROR: Decrypted value is empty"
        exit 1
    fi
    
    echo "$decrypted_value"
}

# ============================================================================
# END DECRYPTION FUNCTIONS
# ============================================================================

log "=== Starting Vault Secrets Storage ==="

# Debug: Print received parameters
log "Received parameters:"
log "  connectionId: $connectionId"
log "  llmPlatform: $llmPlatform"
log "  llmModel: $llmModel"
log "  deploymentEnvironment: $deploymentEnvironment"
log "  Vault Address: $VAULT_ADDR"

# Note: No token required - vault agent proxy automatically injects authentication

# Function to determine platform name
get_platform_name() {
    case "$llmPlatform" in
        "aws") echo "aws_bedrock" ;;
        "azure") echo "azure_openai" ;;
        *) 
            log "ERROR: Unsupported platform: $llmPlatform"
            exit 1
            ;;
    esac
}

# Function to get model name (first element from array)
get_model_name() {
    # Remove brackets and quotes, get first element
    echo "$llmModel" | sed 's/\[//g' | sed 's/\]//g' | sed 's/"//g' | cut -d',' -f1 | xargs
}

# Function to build vault path
build_vault_path() {
    local secret_type=$1  # "llm" or "embeddings"
    local platform=$(get_platform_name)
    
    # Use appropriate model based on secret type
    local model
    if [ "$secret_type" = "embeddings" ]; then
        model="$embeddingModel"
    else
        model=$(get_model_name)
    fi
    
    if [ "$deploymentEnvironment" = "testing" ]; then
        echo "secret/$secret_type/connections/$platform/$deploymentEnvironment/$connectionId"
    else
        echo "secret/$secret_type/connections/$platform/$deploymentEnvironment/$model"
    fi
}

# Function to store LLM secrets
store_llm_secrets() {
    local vault_path=$(build_vault_path "llm")
    log "Storing LLM secrets at path: $vault_path"
    
    case "$llmPlatform" in
        "aws")
            store_aws_llm_secrets "$vault_path"
            ;;
        "azure")
            store_azure_llm_secrets "$vault_path"
            ;;
    esac
}

# Function to store embedding secrets
store_embedding_secrets() {
    local vault_path=$(build_vault_path "embeddings")
    log "Storing embedding secrets at path: $vault_path"
    
    case "$embeddingPlatform" in
        "aws")
            store_aws_embedding_secrets "$vault_path"
            ;;
        "azure")
            store_azure_embedding_secrets "$vault_path"
            ;;
        *)
            log "WARNING: Embedding platform '$embeddingPlatform' not supported, skipping embedding secrets"
            ;;
    esac
}

# Function to store AWS LLM secrets
store_aws_llm_secrets() {
    local vault_path=$1
    local model=$(get_model_name)
    
    log "Storing AWS LLM secrets..."
    
    # Decrypt sensitive fields
    local decrypted_access_key=$(decrypt_rsa_oaep "$accessKey")
    local decrypted_secret_key=$(decrypt_rsa_oaep "$secretKey")
    
    # Build JSON payload
    local json_payload=$(cat <<EOF
{
    "data": {
        "connection_id": "$connectionId",
        "access_key": "$decrypted_access_key",
        "secret_key": "$decrypted_secret_key",
        "environment": "$deploymentEnvironment",
        "model": "$model",
        "tags": "aws,bedrock,$deploymentEnvironment,$model"
    }
}
EOF
)
    
    log "Storing secrets at path: $vault_path"
    
    # Convert path for KV v2 API (secret/path -> secret/data/path)
    local api_path=$(echo "$vault_path" | sed 's|^secret/|secret/data/|')
    log "API URL: $VAULT_ADDR/v1/$api_path"
    
    # Execute HTTP API call
    # No X-Vault-Token header needed - vault agent proxy auto-injects it
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        "$VAULT_ADDR/v1/$api_path")
    
    local http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
        log "AWS LLM secrets stored successfully (HTTP $http_code)"
    else
        log "ERROR: Failed to store AWS LLM secrets (HTTP $http_code)"
        log "Response: $body"
        exit 1
    fi
}

# Function to store Azure LLM secrets
store_azure_llm_secrets() {
    local vault_path=$1
    local model=$(get_model_name)
    
    log "Storing Azure LLM secrets..."
    
    # Decrypt sensitive fields
    local decrypted_api_key=$(decrypt_rsa_oaep "$apiKey")
    
    # Build JSON payload
    local json_payload=$(cat <<EOF
{
    "data": {
        "connection_id": "$connectionId",
        "endpoint": "$targetUrl",
        "api_key": "$decrypted_api_key",
        "deployment_name": "$deploymentName",
        "environment": "$deploymentEnvironment",
        "model": "$model",
        "api_version": "2024-05-01-preview",
        "tags": "azure,$deploymentEnvironment,$model"
    }
}
EOF
)
    
    log "Storing secrets at path: $vault_path"
    
    # Convert path for KV v2 API (secret/path -> secret/data/path)
    local api_path=$(echo "$vault_path" | sed 's|^secret/|secret/data/|')
    log "API URL: $VAULT_ADDR/v1/$api_path"
    
    # Execute HTTP API call
    # No X-Vault-Token header needed - vault agent proxy auto-injects it
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        "$VAULT_ADDR/v1/$api_path")
    
    local http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
        log "Azure LLM secrets stored successfully (HTTP $http_code)"
    else
        log "ERROR: Failed to store Azure LLM secrets (HTTP $http_code)"
        log "Response: $body"
        exit 1
    fi
}

# Function to store AWS embedding secrets
store_aws_embedding_secrets() {
    local vault_path=$1
    
    log "Storing AWS embedding secrets..."
    
    # Decrypt sensitive fields
    local decrypted_embedding_access_key=$(decrypt_rsa_oaep "$embeddingAccessKey")
    local decrypted_embedding_secret_key=$(decrypt_rsa_oaep "$embeddingSecretKey")
    
    # Build JSON payload
    local json_payload=$(cat <<EOF
{
    "data": {
        "connection_id": "$connectionId",
        "access_key": "$decrypted_embedding_access_key",
        "secret_key": "$decrypted_embedding_secret_key",
        "environment": "$deploymentEnvironment",
        "model": "$embeddingModel",
        "tags": "aws,bedrock,embedding,$deploymentEnvironment,$embeddingModel"
    }
}
EOF
)
    
    log "Storing secrets at path: $vault_path"
    
    # Convert path for KV v2 API (secret/path -> secret/data/path)
    local api_path=$(echo "$vault_path" | sed 's|^secret/|secret/data/|')
    log "API URL: $VAULT_ADDR/v1/$api_path"
    
    # Execute HTTP API call
    # No X-Vault-Token header needed - vault agent proxy auto-injects it
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        "$VAULT_ADDR/v1/$api_path")
    
    local http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
        log "AWS embedding secrets stored successfully (HTTP $http_code)"
    else
        log "ERROR: Failed to store AWS embedding secrets (HTTP $http_code)"
        log "Response: $body"
        exit 1
    fi
}

# Function to store Azure embedding secrets
store_azure_embedding_secrets() {
    local vault_path=$1
    
    log "Storing Azure embedding secrets..."
    
    # Decrypt sensitive fields
    local decrypted_embedding_api_key=$(decrypt_rsa_oaep "$embeddingAzureApiKey")
    
    # Build JSON payload
    local json_payload=$(cat <<EOF
{
    "data": {
        "connection_id": "$connectionId",
        "endpoint": "$embeddingTargetUri",
        "api_key": "$decrypted_embedding_api_key",
        "deployment_name": "$embeddingDeploymentName",
        "environment": "$deploymentEnvironment",
        "model": "$embeddingModel",
        "api_version": "2024-12-01-preview",
        "tags": "azure,embedding,$deploymentEnvironment,$embeddingModel"
    }
}
EOF
)
    
    log "Storing secrets at path: $vault_path"
    
    # Convert path for KV v2 API (secret/path -> secret/data/path)
    local api_path=$(echo "$vault_path" | sed 's|^secret/|secret/data/|')
    log "API URL: $VAULT_ADDR/v1/$api_path"
    
    # Execute HTTP API call
    # No X-Vault-Token header needed - vault agent proxy auto-injects it
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        "$VAULT_ADDR/v1/$api_path")
    
    local http_code=$(echo "$response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
        log "Azure embedding secrets stored successfully (HTTP $http_code)"
    else
        log "ERROR: Failed to store Azure embedding secrets (HTTP $http_code)"
        log "Response: $body"
        exit 1
    fi
}

# Main execution
log "Platform: $(get_platform_name)"
log "Model: $(get_model_name)"

# Store LLM secrets
store_llm_secrets

# Store embedding secrets if embedding platform is provided
if [ -n "$embeddingPlatform" ]; then
    store_embedding_secrets
else
    log "No embedding platform specified, skipping embedding secrets"
fi

log "=== Vault secrets storage completed successfully ==="

