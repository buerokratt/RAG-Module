#!/bin/bash

# Vault Secrets Deletion Script
# This script deletes LLM and embedding credentials from HashiCorp Vault

set -e  # Exit on any error

# Configuration
VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
VAULT_TOKEN_FILE="/agent/out/token"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "=== Starting Vault Secrets Deletion ==="

# Debug: Print received parameters
log "Received parameters:"
log "  connectionId: $connectionId"
log "  llmPlatform: $llmPlatform"
log "  llmModel: $llmModel"
log "  embeddingModel: $embeddingModel"
log "  embeddingPlatform: $embeddingPlatform"
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
    local platform=$1
    case "$platform" in
        "aws") echo "aws_bedrock" ;;
        "azure") echo "azure_openai" ;;
        *) 
            log "ERROR: Unsupported platform: $platform"
            exit 1
            ;;
    esac
}

# Function to get model name (first element from array)
get_model_name() {
    local model_array=$1
    # Remove brackets and quotes, get first element
    echo "$model_array" | sed 's/\[//g' | sed 's/\]//g' | sed 's/"//g' | cut -d',' -f1 | xargs
}

# Function to build vault path
build_vault_path() {
    local secret_type=$1  # "llm" or "embeddings"
    local platform_name=$2
    local model_name=$3
    
    if [ "$deploymentEnvironment" = "test" ]; then
        echo "secret/$secret_type/connections/$platform_name/$deploymentEnvironment/$connectionId"
    else
        echo "secret/$secret_type/connections/$platform_name/$deploymentEnvironment/$model_name"
    fi
}

# Function to delete vault secret (both data and metadata)
delete_vault_secret() {
    local vault_path=$1
    local secret_description=$2
    
    log "Deleting $secret_description at path: $vault_path"
    
    # Convert path for KV v2 API (secret/path -> secret/data/path and secret/metadata/path)
    local data_path=$(echo "$vault_path" | sed 's|^secret/|secret/data/|')
    local metadata_path=$(echo "$vault_path" | sed 's|^secret/|secret/metadata/|')
    
    log "Data API URL: $VAULT_ADDR/v1/$data_path"
    log "Metadata API URL: $VAULT_ADDR/v1/$metadata_path"
    
    local success=true
    
    # Delete secret data
    log "Deleting secret data..."
    local data_response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X DELETE \
        -H "X-Vault-Token: $VAULT_TOKEN" \
        "$VAULT_ADDR/v1/$data_path")
    
    local data_http_code=$(echo "$data_response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    local data_body=$(echo "$data_response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if [[ "$data_http_code" -ge 200 && "$data_http_code" -lt 300 ]] || [[ "$data_http_code" == "404" ]]; then
        log "Secret data deleted successfully (HTTP $data_http_code)"
    else
        log "WARNING: Failed to delete secret data (HTTP $data_http_code)"
        log "Data response: $data_body"
        success=false
    fi
    
    # Delete secret metadata
    log "Deleting secret metadata..."
    local metadata_response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X DELETE \
        -H "X-Vault-Token: $VAULT_TOKEN" \
        "$VAULT_ADDR/v1/$metadata_path")
    
    local metadata_http_code=$(echo "$metadata_response" | grep -o "HTTPSTATUS:[0-9]*" | cut -d: -f2)
    local metadata_body=$(echo "$metadata_response" | sed -E 's/HTTPSTATUS:[0-9]*$//')
    
    if [[ "$metadata_http_code" -ge 200 && "$metadata_http_code" -lt 300 ]] || [[ "$metadata_http_code" == "404" ]]; then
        log "Secret metadata deleted successfully (HTTP $metadata_http_code)"
    else
        log "WARNING: Failed to delete secret metadata (HTTP $metadata_http_code)"
        log "Metadata response: $metadata_body"
        success=false
    fi
    
    if [ "$success" = true ]; then
        log "$secret_description deletion completed successfully"
    else
        log "WARNING: $secret_description deletion completed with some failures"
    fi
    
    return 0  # Continue even if some deletions fail
}

# Function to delete LLM secrets
delete_llm_secrets() {
    if [ -z "$llmPlatform" ] || [ -z "$llmModel" ]; then
        log "No LLM platform or model specified, skipping LLM secrets deletion"
        return 0
    fi
    
    local platform_name=$(get_platform_name "$llmPlatform")
    local model_name=$(get_model_name "$llmModel")
    local vault_path=$(build_vault_path "llm" "$platform_name" "$model_name")
    
    delete_vault_secret "$vault_path" "LLM secrets"
}

# Function to delete embedding secrets
delete_embedding_secrets() {
    if [ -z "$embeddingPlatform" ] || [ -z "$embeddingModel" ]; then
        log "No embedding platform or model specified, skipping embedding secrets deletion"
        return 0
    fi
    
    local platform_name=$(get_platform_name "$embeddingPlatform")
    local vault_path=$(build_vault_path "embeddings" "$platform_name" "$embeddingModel")
    
    delete_vault_secret "$vault_path" "Embedding secrets"
}

# Main execution
if [ -n "$llmPlatform" ]; then
    log "LLM Platform: $(get_platform_name "$llmPlatform")"
fi

if [ -n "$llmModel" ]; then
    log "LLM Model: $(get_model_name "$llmModel")"
fi

if [ -n "$embeddingPlatform" ]; then
    log "Embedding Platform: $(get_platform_name "$embeddingPlatform")"
fi

# Delete LLM secrets
delete_llm_secrets

# Delete embedding secrets
delete_embedding_secrets

log "=== Vault secrets deletion completed ==="
