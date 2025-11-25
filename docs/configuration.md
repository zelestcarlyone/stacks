# Configuration

## Main Configuration File

Located at `/opt/stacks/config/config.yaml` (or your mounted config directory):

```yaml
server:
  host: "0.0.0.0"
  port: 7788

login:
  username: null # Auto-generated on first run
  password: null # Auto-generated on first run (bcrypt hashed)
  disable: false # Disable all security requirements (API keys and login/password)

api:
  key: null # Auto-generated on first run
  session_secret: null # Auto-generated on first run

downloads:
  delay: 2 # Delay in seconds
  retry_count: 3
  resume_attempts: 3

fast_download:
  enabled: false
  key: null

flaresolverr:
  enabled: false # Enables or disables the use of FlareSolverr
  url: null # The url and port of your FlareSolverr instance
  timeout: 60 # How long to wait for FlareSolverr to return a result

queue:
  max_history: 100

logging:
  level: "INFO" # DEBUG, INFO, WARN, ERROR
```

All settings can be modified through the web interface Settings tab or by editing the config file directly. Changes through the web interface take effect immediately without requiring a restart. Editing the file requires a server restart for the changes to take hold. Deleting the file will create a new one upon next server start.

## Environment Variables

Set in `docker-compose.yml`:

```yaml
environment:
  - TZ=UTC # Timezone for logs and timestamps
  - USERNAME=admin # Initial username (seeds config on first run)
  - PASSWORD=stacks # Initial password (seeds config on first run)
  - SOLVERR_URL=flaresolverr:8191 # Embedds the URL and port for FlareSolverr on first run.
  # - RESET_ADMIN=true  # Uncomment to force password reset
```

**Note:** `USERNAME` and `PASSWORD` variables only seed the initial configuration. Once the config file exists, environment variables are ignored unless the password hash is invalid or `RESET_ADMIN=true` is set. In other words, once you have persistent volumes and a valid config it is safe to remove them from the compose file.

## Network Access

To access Stacks from other devices on your network, the default configuration already exposes the port. Simply access it using your server's IP address:

```
http://192.168.1.100:7788
```

Make sure to update the Tampermonkey script settings on each device to point to your server's IP.
