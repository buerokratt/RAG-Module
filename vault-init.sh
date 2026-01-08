#!/bin/sh
set -e

VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
UNSEAL_KEYS_FILE="/vault/data/unseal-keys.json"
INIT_FLAG="/vault/data/.initialized"

echo "=== Vault Initialization Script ==="

# Wait for Vault to be ready
echo "Waiting for Vault..."
for i in $(seq 1 30); do
    if wget -q -O- "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1; then
        echo "Vault is ready"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Check if this is first time
if [ ! -f "$INIT_FLAG" ]; then
    echo "=== FIRST TIME DEPLOYMENT ==="
    
    # Initialize Vault
    echo "Initializing Vault..."
    wget -q -O- --post-data='{"secret_shares":5,"secret_threshold":3}' \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/init" > "$UNSEAL_KEYS_FILE"
    
    ROOT_TOKEN=$(grep -o '"root_token":"[^"]*"' "$UNSEAL_KEYS_FILE" | cut -d':' -f2 | tr -d '"')
    export VAULT_TOKEN="$ROOT_TOKEN"
    
    # Extract unseal keys
    KEY1=$(grep -o '"keys":\[[^]]*\]' "$UNSEAL_KEYS_FILE" | grep -o '"[^"]*"' | sed -n '2p' | tr -d '"')
    KEY2=$(grep -o '"keys":\[[^]]*\]' "$UNSEAL_KEYS_FILE" | grep -o '"[^"]*"' | sed -n '3p' | tr -d '"')
    KEY3=$(grep -o '"keys":\[[^]]*\]' "$UNSEAL_KEYS_FILE" | grep -o '"[^"]*"' | sed -n '4p' | tr -d '"')
    
    # Unseal Vault
    echo "Unsealing Vault..."
    wget -q -O- --post-data="{\"key\":\"$KEY1\"}" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/unseal" >/dev/null
    
    wget -q -O- --post-data="{\"key\":\"$KEY2\"}" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/unseal" >/dev/null
    
    wget -q -O- --post-data="{\"key\":\"$KEY3\"}" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/unseal" >/dev/null
    
    sleep 2
    echo "Vault unsealed"
    
    # Enable KV v2
    echo "Enabling KV v2 secrets engine..."
    wget -q -O- --post-data='{"type":"kv","options":{"version":"2"}}' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/mounts/secret" >/dev/null 2>&1 || echo "KV already enabled"
    
    # Enable AppRole
    echo "Enabling AppRole..."
    wget -q -O- --post-data='{"type":"approle"}' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/auth/approle" >/dev/null 2>&1 || echo "AppRole already enabled"
    
    # Create GUI policy - Read public encryption key only
    echo "Creating gui-policy..."
    GUI_POLICY='path "secret/data/encryption/public_key" { capabilities = ["read"] }
path "secret/metadata/encryption/public_key" { capabilities = ["read"] }
path "secret/data/encryption/private_key" { capabilities = ["deny"] }
path "secret/data/llm/*" { capabilities = ["deny"] }
path "secret/data/embeddings/*" { capabilities = ["deny"] }'
    
    GUI_POLICY_JSON=$(echo "$GUI_POLICY" | jq -Rs '{"policy":.}')
    wget -q -O- --post-data="$GUI_POLICY_JSON" \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/policies/acl/gui-policy" >/dev/null
    
    # Create CronManager policy - Read encryption keys + Write LLM/Embedding secrets
    echo "Creating cron-manager-policy..."
    CRON_POLICY='path "secret/data/encryption/public_key" { capabilities = ["read"] }
path "secret/metadata/encryption/public_key" { capabilities = ["read"] }
path "secret/data/encryption/private_key" { capabilities = ["read"] }
path "secret/metadata/encryption/private_key" { capabilities = ["read"] }
path "secret/data/llm/connections/*" { capabilities = ["create", "read", "update", "delete"] }
path "secret/metadata/llm/connections/*" { capabilities = ["read", "list", "delete"] }
path "secret/data/embeddings/connections/*" { capabilities = ["create", "read", "update", "delete"] }
path "secret/metadata/embeddings/connections/*" { capabilities = ["read", "list", "delete"] }
path "auth/token/lookup-self" { capabilities = ["read"] }'
    
    CRON_POLICY_JSON=$(echo "$CRON_POLICY" | jq -Rs '{"policy":.}')
    wget -q -O- --post-data="$CRON_POLICY_JSON" \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/policies/acl/cron-manager-policy" >/dev/null
    
    # Create LLM Orchestration policy - Read LLM/Embedding secrets only
    echo "Creating llm-orchestration-policy..."
    LLM_POLICY='path "secret/data/llm/connections/*" { capabilities = ["read", "list"] }
path "secret/metadata/llm/connections/*" { capabilities = ["read", "list"] }
path "secret/data/embeddings/connections/*" { capabilities = ["read", "list"] }
path "secret/metadata/embeddings/connections/*" { capabilities = ["read", "list"] }
path "secret/data/encryption/*" { capabilities = ["deny"] }
path "auth/token/lookup-self" { capabilities = ["read"] }'
    
    LLM_POLICY_JSON=$(echo "$LLM_POLICY" | jq -Rs '{"policy":.}')
    wget -q -O- --post-data="$LLM_POLICY_JSON" \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/policies/acl/llm-orchestration-policy" >/dev/null
    
    # Create GUI AppRole
    echo "Creating gui-service AppRole..."
    wget -q -O- --post-data='{"token_policies":["gui-policy"],"token_no_default_policy":true,"token_ttl":"15m","token_max_ttl":"1h","secret_id_ttl":"24h","secret_id_num_uses":0,"bind_secret_id":true}' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/auth/approle/role/gui-service" >/dev/null
    
    # Create CronManager AppRole
    echo "Creating cron-manager-service AppRole..."
    wget -q -O- --post-data='{"token_policies":["cron-manager-policy"],"token_no_default_policy":true,"token_ttl":"30m","token_max_ttl":"8h","secret_id_ttl":"24h","secret_id_num_uses":0,"bind_secret_id":true}' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/auth/approle/role/cron-manager-service" >/dev/null
    
    # Create LLM Orchestration AppRole
    echo "Creating llm-orchestration-service AppRole..."
    wget -q -O- --post-data='{"token_policies":["llm-orchestration-policy"],"token_no_default_policy":true,"token_ttl":"1h","token_max_ttl":"24h","secret_id_ttl":"24h","secret_id_num_uses":0,"bind_secret_id":true}' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service" >/dev/null
    
    # Ensure credentials directory exists
    mkdir -p /agent/credentials
    
    # Get GUI credentials
    echo "Getting GUI credentials..."
    GUI_ROLE_ID=$(wget -q -O- \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/gui-service/role-id" | \
        grep -o '"role_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$GUI_ROLE_ID" > /agent/credentials/gui_role_id
    
    GUI_SECRET_ID=$(wget -q -O- --post-data='' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/gui-service/secret-id" | \
        grep -o '"secret_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$GUI_SECRET_ID" > /agent/credentials/gui_secret_id
    
    # Get CronManager credentials
    echo "Getting CronManager credentials..."
    CRON_ROLE_ID=$(wget -q -O- \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/cron-manager-service/role-id" | \
        grep -o '"role_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$CRON_ROLE_ID" > /agent/credentials/cron_role_id
    
    CRON_SECRET_ID=$(wget -q -O- --post-data='' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/cron-manager-service/secret-id" | \
        grep -o '"secret_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$CRON_SECRET_ID" > /agent/credentials/cron_secret_id
    
    # Get LLM Orchestration credentials
    echo "Getting LLM Orchestration credentials..."
    LLM_ROLE_ID=$(wget -q -O- \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service/role-id" | \
        grep -o '"role_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$LLM_ROLE_ID" > /agent/credentials/llm_role_id
    
    LLM_SECRET_ID=$(wget -q -O- --post-data='' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service/secret-id" | \
        grep -o '"secret_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$LLM_SECRET_ID" > /agent/credentials/llm_secret_id
    
    # Set secure permissions
    chmod 640 /agent/credentials/*_role_id
    chmod 640 /agent/credentials/*_secret_id
    
    # Generate RSA keypair for credential encryption/decryption
    echo "Generating RSA keypair for encryption..."
    
    # Create temp directory for key generation
    TEMP_KEY_DIR="/tmp/vault-keys-$$"
    mkdir -p "$TEMP_KEY_DIR"
    
    # Generate private key (RSA-2048)
    if ! openssl genrsa -out "$TEMP_KEY_DIR/private.pem" 2048 2>/dev/null; then
        echo "ERROR: Failed to generate private key"
        exit 1
    fi
    
    # Extract public key from private key
    if ! openssl rsa -in "$TEMP_KEY_DIR/private.pem" -pubout -out "$TEMP_KEY_DIR/public.pem" 2>/dev/null; then
        echo "ERROR: Failed to extract public key"
        exit 1
    fi
    
    echo "Keys generated successfully"
    
    # Read keys and escape for JSON
    PRIVATE_KEY=$(cat "$TEMP_KEY_DIR/private.pem" | sed ':a;N;$!ba;s/\n/\\n/g')
    PUBLIC_KEY=$(cat "$TEMP_KEY_DIR/public.pem" | sed ':a;N;$!ba;s/\n/\\n/g')
    CREATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    KEY_ID="rsa-keypair-$(date +%s)"
    
    # Store public key in Vault
    echo "Storing public key in Vault..."
    wget -q -O- --post-data='{"data":{"key":"'"$PUBLIC_KEY"'","algorithm":"RSA-OAEP","key_size":2048,"key_id":"'"$KEY_ID"'","created_at":"'"$CREATED_AT"'"}}' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/secret/data/encryption/public_key" >/dev/null
    
    # Store private key in Vault
    echo "Storing private key in Vault..."
    wget -q -O- --post-data='{"data":{"key":"'"$PRIVATE_KEY"'","algorithm":"RSA-OAEP","key_size":2048,"key_id":"'"$KEY_ID"'","created_at":"'"$CREATED_AT"'"}}' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/secret/data/encryption/private_key" >/dev/null
    
    # Clean up temporary files
    rm -rf "$TEMP_KEY_DIR"
    echo "RSA keypair generated and stored successfully"
    
    # Store test LLM credentials for testing
    echo "Creating test LLM credentials..."
    wget -q -O- --post-data='{"data":{"access_key":"TEST_AWS_ACCESS_KEY","secret_key":"TEST_AWS_SECRET_KEY","environment":"production","model":"claude-3"}}' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/secret/data/llm/connections/aws_bedrock/production/claude-3" >/dev/null
    
    # Mark as initialized
    touch "$INIT_FLAG"
    echo "=== First time setup complete ==="

    
else
    echo "=== SUBSEQUENT DEPLOYMENT ==="
    
    # Check if Vault is sealed
    SEALED=$(wget -q -O- "$VAULT_ADDR/v1/sys/seal-status" | grep -o '"sealed":[^,}]*' | cut -d':' -f2)
    
    if [ "$SEALED" = "true" ]; then
        echo "Vault is sealed. Unsealing..."
        
        # Load unseal keys
        KEY1=$(grep -o '"keys":\[[^]]*\]' "$UNSEAL_KEYS_FILE" | grep -o '"[^"]*"' | sed -n '2p' | tr -d '"')
        KEY2=$(grep -o '"keys":\[[^]]*\]' "$UNSEAL_KEYS_FILE" | grep -o '"[^"]*"' | sed -n '3p' | tr -d '"')
        KEY3=$(grep -o '"keys":\[[^]]*\]' "$UNSEAL_KEYS_FILE" | grep -o '"[^"]*"' | sed -n '4p' | tr -d '"')
        
        wget -q -O- --post-data="{\"key\":\"$KEY1\"}" \
            --header='Content-Type: application/json' \
            "$VAULT_ADDR/v1/sys/unseal" >/dev/null
        
        wget -q -O- --post-data="{\"key\":\"$KEY2\"}" \
            --header='Content-Type: application/json' \
            "$VAULT_ADDR/v1/sys/unseal" >/dev/null
        
        wget -q -O- --post-data="{\"key\":\"$KEY3\"}" \
            --header='Content-Type: application/json' \
            "$VAULT_ADDR/v1/sys/unseal" >/dev/null
        
        sleep 2
        echo "Vault unsealed"
    else
        echo "Vault is already unsealed"
    fi
    
    # Get root token
    ROOT_TOKEN=$(grep -o '"root_token":"[^"]*"' "$UNSEAL_KEYS_FILE" | cut -d':' -f2 | tr -d '"')
    export VAULT_TOKEN="$ROOT_TOKEN"
    
    # Ensure credentials directory exists
    mkdir -p /agent/credentials
    
    # Always regenerate all secret_ids on restart
    echo "Regenerating GUI secret_id..."
    GUI_SECRET_ID=$(wget -q -O- --post-data='' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/gui-service/secret-id" | \
        grep -o '"secret_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$GUI_SECRET_ID" > /agent/credentials/gui_secret_id
    
    echo "Regenerating CronManager secret_id..."
    CRON_SECRET_ID=$(wget -q -O- --post-data='' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/cron-manager-service/secret-id" | \
        grep -o '"secret_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$CRON_SECRET_ID" > /agent/credentials/cron_secret_id
    
    echo "Regenerating LLM secret_id..."
    LLM_SECRET_ID=$(wget -q -O- --post-data='' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service/secret-id" | \
        grep -o '"secret_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$LLM_SECRET_ID" > /agent/credentials/llm_secret_id
    
    # Set permissions
    chmod 640 /agent/credentials/*_secret_id
    
    # Ensure role_ids exist
    if [ ! -f /agent/credentials/gui_role_id ]; then
        echo "Copying GUI role_id..."
        GUI_ROLE_ID=$(wget -q -O- \
            --header="X-Vault-Token: $ROOT_TOKEN" \
            "$VAULT_ADDR/v1/auth/approle/role/gui-service/role-id" | \
            grep -o '"role_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
        echo "$GUI_ROLE_ID" > /agent/credentials/gui_role_id
        chmod 640 /agent/credentials/gui_role_id
    fi
    
    if [ ! -f /agent/credentials/cron_role_id ]; then
        echo "Copying CronManager role_id..."
        CRON_ROLE_ID=$(wget -q -O- \
            --header="X-Vault-Token: $ROOT_TOKEN" \
            "$VAULT_ADDR/v1/auth/approle/role/cron-manager-service/role-id" | \
            grep -o '"role_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
        echo "$CRON_ROLE_ID" > /agent/credentials/cron_role_id
        chmod 640 /agent/credentials/cron_role_id
    fi
    
    if [ ! -f /agent/credentials/llm_role_id ]; then
        echo "Copying LLM role_id..."
        LLM_ROLE_ID=$(wget -q -O- \
            --header="X-Vault-Token: $ROOT_TOKEN" \
            "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service/role-id" | \
            grep -o '"role_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
        echo "$LLM_ROLE_ID" > /agent/credentials/llm_role_id
        chmod 640 /agent/credentials/llm_role_id
    fi
fi

echo "=== Vault init complete ==="