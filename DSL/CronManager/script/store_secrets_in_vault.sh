#!/bin/bash

# Vault Secrets Storage Script
# This script stores LLM and embedding credentials in HashiCorp Vault

set -e  # Exit on any error

# Configuration
VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
VAULT_TOKEN_FILE="/agent/out/token"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "=== Starting Vault Secrets Storage ==="

# Debug: Print received parameters
log "Received parameters:"
log "  connectionId: $connectionId"
log "  llmPlatform: $llmPlatform"
log "  llmModel: $llmModel"
log "  deploymentEnvironment: $deploymentEnvironment"

# Read vault token
if [ ! -f "$VAULT_TOKEN_FILE" ]; then
    log "ERROR: Vault token file not found at $VAULT_TOKEN_FILE"
    exit 1
fi

VAULT_TOKEN=$(cat "$VAULT_TOKEN_FILE")
if [ -z "$VAULT_TOKEN" ]; then
    log "ERROR: Vault token is empty"
    exit 1
fi

log "Vault token loaded successfully"

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
    
    # Build JSON payload
    local json_payload=$(cat <<EOF
{
    "data": {
        "connection_id": "$connectionId",
        "access_key": "$accessKey",
        "secret_key": "$secretKey",
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
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "X-Vault-Token: $VAULT_TOKEN" \
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
    
    # Build JSON payload
    local json_payload=$(cat <<EOF
{
    "data": {
        "connection_id": "$connectionId",
        "endpoint": "$targetUrl",
        "api_key": "$apiKey",
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
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "X-Vault-Token: $VAULT_TOKEN" \
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
    
    # Build JSON payload
    local json_payload=$(cat <<EOF
{
    "data": {
        "connection_id": "$connectionId",
        "access_key": "$embeddingAccessKey",
        "secret_key": "$embeddingSecretKey",
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
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "X-Vault-Token: $VAULT_TOKEN" \
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
    
    # Build JSON payload
    local json_payload=$(cat <<EOF
{
    "data": {
        "connection_id": "$connectionId",
        "endpoint": "$embeddingTargetUri",
        "api_key": "$embeddingAzureApiKey",
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
    local response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        -H "X-Vault-Token: $VAULT_TOKEN" \
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

