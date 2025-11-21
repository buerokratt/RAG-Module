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
    
    # Create policy
    echo "Creating llm-orchestration policy..."
    POLICY='path "secret/metadata/llm/*" { capabilities = ["list", "delete"] }
path "secret/data/llm/*" { capabilities = ["create", "read", "update", "delete"] }
path "auth/token/lookup-self" { capabilities = ["read"] }
path "secret/metadata/embeddings/*" { capabilities = ["list", "delete"] }
path "secret/data/embeddings/*" { capabilities = ["create", "read", "update", "delete"] }'
    
    POLICY_JSON=$(echo "$POLICY" | jq -Rs '{"policy":.}')
    wget -q -O- --post-data="$POLICY_JSON" \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/sys/policies/acl/llm-orchestration" >/dev/null
    
    # Create AppRole
    echo "Creating llm-orchestration-service AppRole..."
    wget -q -O- --post-data='{"token_policies":["llm-orchestration"],"token_no_default_policy":true,"token_ttl":"1h","token_max_ttl":"24h","secret_id_ttl":"24h","secret_id_num_uses":0,"bind_secret_id":true}' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        --header='Content-Type: application/json' \
        "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service" >/dev/null
    
    # Ensure credentials directory exists
    mkdir -p /agent/credentials
    
    # Get role_id
    echo "Getting role_id..."
    ROLE_ID=$(wget -q -O- \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service/role-id" | \
        grep -o '"role_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$ROLE_ID" > /agent/credentials/role_id
    
    # Generate secret_id
    echo "Generating secret_id..."
    SECRET_ID=$(wget -q -O- --post-data='' \
        --header="X-Vault-Token: $ROOT_TOKEN" \
        "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service/secret-id" | \
        grep -o '"secret_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
    echo "$SECRET_ID" > /agent/credentials/secret_id
    
    chmod 644 /agent/credentials/role_id /agent/credentials/secret_id
    
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
        
        # Get root token
        ROOT_TOKEN=$(grep -o '"root_token":"[^"]*"' "$UNSEAL_KEYS_FILE" | cut -d':' -f2 | tr -d '"')
        export VAULT_TOKEN="$ROOT_TOKEN"
        
        # Ensure credentials directory exists
        mkdir -p /agent/credentials
        
        # Regenerate secret_id after unseal
        echo "Regenerating secret_id..."
        SECRET_ID=$(wget -q -O- --post-data='' \
            --header="X-Vault-Token: $ROOT_TOKEN" \
            "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service/secret-id" | \
            grep -o '"secret_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
        echo "$SECRET_ID" > /agent/credentials/secret_id
        chmod 644 /agent/credentials/secret_id
        
        # Ensure role_id exists
        if [ ! -f /agent/credentials/role_id ]; then
            echo "Copying role_id..."
            mkdir -p /agent/credentials
            ROLE_ID=$(wget -q -O- \
                --header="X-Vault-Token: $ROOT_TOKEN" \
                "$VAULT_ADDR/v1/auth/approle/role/llm-orchestration-service/role-id" | \
                grep -o '"role_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
            echo "$ROLE_ID" > /agent/credentials/role_id
            chmod 644 /agent/credentials/role_id
        fi
    else
        echo "Vault is unsealed. No action needed."
    fi
fi

echo "=== Vault init complete ==="