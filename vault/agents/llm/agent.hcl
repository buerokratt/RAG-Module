vault {
  address = "http://vault:8200"
}

pid_file = "/agent/out/pidfile"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/agent/credentials/role_id"
      secret_id_file_path = "/agent/credentials/secret_id"
      remove_secret_id_file_after_reading = false
    }
  }

  sink "file" {
    config = {
      path = "/agent/out/token"
    }
  }
}

cache {
  default_lease_duration = "1h"
}

listener "tcp" {
  address     = "127.0.0.1:8201"
  tls_disable = true
}

api_proxy {
  use_auto_auth_token = true
  enforce_consistency = "always"
  when_inconsistent = "forward"
}
