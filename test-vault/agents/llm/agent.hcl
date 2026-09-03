vault {
  # Inside Docker network, the service name "vault" resolves to the dev Vault
  address = "http://vault:8200"
}

pid_file = "/agent/llm-token/pidfile"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path                   = "/agent/in/role_id"
      secret_id_file_path                 = "/agent/in/secret_id"
      remove_secret_id_file_after_reading = false  # test-friendly
    }
  }

  sink "file" {
    config = {
      path = "/agent/llm-token/token"
    }
  }
}

# In-memory cache (free, no Enterprise license)
cache {
  default_lease_duration = "1h"
}

# Listener is required for Agent’s internal servers (not exposed)
listener "tcp" {
  address     = "127.0.0.1:8201"
  tls_disable = true
}

# dummy template so cache is “active” (some versions require this)
template {
  source      = "/dev/null"
  destination = "/agent/llm-token/dummy"
}

# Disable API proxy; not needed here
api_proxy {
  disable = true
}