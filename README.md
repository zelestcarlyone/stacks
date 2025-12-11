# Stacks - Download Manager for Anna's Archive

![Stacks Logo](web/images/logo.svg)

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Docker Pulls](https://img.shields.io/docker/pulls/zelest/stacks?style=flat&logo=docker)](https://hub.docker.com/r/zelest/stacks)
[![Docker Image Size](https://img.shields.io/docker/image-size/zelest/stacks/latest?style=flat&logo=docker)](https://hub.docker.com/r/zelest/stacks)
[![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Alpine](https://img.shields.io/badge/Alpine-3.23-0D597F?style=flat&logo=alpinelinux&logoColor=white)](https://alpinelinux.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.2-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gunicorn](https://img.shields.io/badge/Gunicorn-23.0.0-499848?style=flat&logo=gunicorn&logoColor=white)](https://github.com/benoitc/gunicorn)
[![FlareSolverr](https://img.shields.io/badge/FlareSolverr-Compatible-orange?style=flat&logo=cloudflare&logoColor=white)](https://github.com/FlareSolverr/FlareSolverr)
[![Tampermonkey](https://img.shields.io/badge/tampermonkey-%2300485B.svg?style=flat&logo=tampermonkey&logoColor=white)](https://www.tampermonkey.net/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Overview

Stacks is a containerized download queue manager designed specifically for Anna's Archive. It provides a clean web interface to queue, manage, and download books automatically. With support for Anna's Archive's fast download API and automatic fallback to mirrors, Stacks ensures reliable downloads with minimal manual intervention.

### Key Features

- **Secure Web Interface** - Password-protected dashboard with session management
- **Queue Management** - Add books to a download queue from your browser with one click
- **Fast Download Support** - Utilize Anna's Archive membership for priority downloads
- **Automatic Fallback** - Seamlessly falls back to mirror sites when fast downloads are unavailable
- **Real-time Dashboard** - Monitor downloads, queue status, and history
- **Browser Integration** - Tampermonkey script adds download buttons directly to Anna's Archive
- **Docker Ready** - Easy deployment with Docker Compose
- **Beautiful UI** - Dracula-themed interface with live progress tracking
- **Resume Support** - Automatically resume interrupted downloads
- **Download History** - Track successful and failed downloads with retry capability

## Quick Start

### Docker Installation

The fastest way to install Stacks is by using the Docker image available on Docker Hub.
You can deploy it with either **Docker Compose** or the **Docker CLI**.

---

### Docker Compose

**Prerequisites**

- Docker and Docker Compose installed
- _(Recommended)_ FlareSolverr for solving Cloudflare/DDoS-guard
- _(Optional)_ Anna's Archive membership for fast downloads

1. Create a file named `docker-compose.yaml` and add the following:

   ```yaml
    networks:
      default:
        name: stacks

    services:
      stacks:
        image: zelest/stacks:latest
        container_name: stacks
        stop_signal: SIGTERM
        stop_grace_period: 30s
        ports:
          # Change the left port if 7788 is already in use
          - "7788:7788"
        volumes:
          # REQUIRED - change these paths to match your system
          - /path/to/config:/opt/stacks/config # Configuration files
          - /path/to/download:/opt/stacks/download # Downloaded files
          - /path/to/logs:/opt/stacks/logs # Log files

          # OPTIONAL: Separate incomplete folder (requires setting in Stacks UI)
          # Uncomment and set incomplete_folder_path to "/incomplete" in the UI
          # - "/path/to/incomplete:/opt/stacks/incomplete"

        restart: unless-stopped
        environment:
          # These only apply on first run, afterward edit config.yaml directly
          # or update the configuration from the UI.
          - USERNAME=admin # Default admin username (change if desired)
          - PASSWORD=stacks # Default admin password - CHANGE THIS!

          # Uncomment to reset the admin password to the above values on startup
          # - RESET_ADMIN=true

          # If you're using the included flaresolverr, this will automatically
          # connect it. If you already got it running, you can change this
          # address to match your local setup, or delete this variable and set
          # it up inside Stacks later.
          - SOLVERR_URL=flaresolverr:8191

          # Set your timezone:
          # https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
          - TZ=UTC

      # Optional, but recommended - bypasses Cloudflare and DDoS-Guard
      # protection on mirror sites. Required if you encounter 403 errors when
      # downloading. Not needed for fast downloads.
      flaresolverr:
          image: ghcr.io/flaresolverr/flaresolverr:latest
          container_name: flaresolverr
          ports:
            - "8191:8191"
          environment:
            - LOG_LEVEL=info
          restart: unless-stopped
   ```

2. Update the volume paths to wherever you want Stacks to keep its files.

3. Change `PASSWORD` to something secure (seriously, do this).

4. In the same directory, run:

   ```bash
   docker compose up
   ```

### Docker CLI Installation

If you prefer running Stacks without Docker Compose, you can use the Docker CLI directly.

**Prerequisites**

- Docker installed
- _(Recommended)_ FlareSolverr for solving Cloudflare/DDoS-guard
- _(Optional)_ Anna's Archive membership for fast downloads

1. Create the required folders on your host:

   ```bash
   mkdir -p /path/to/config /path/to/download /path/to/logs
   ```

2. Set up the network:
   ```bash
   docker network create stacks
   ```
3. Set up FlareSolverr
   ```bash
   docker run -d \
     --name flaresolverr \
     --network stacks \
     -p 8191:8191 \
     -e LOG_LEVEL=info \
     --restart unless-stopped \
     ghcr.io/flaresolverr/flaresolverr:latest
   ```
4. Set up Stacks
   ```bash
   docker run -d \
     --name stacks \
     --network stacks \
     --stop-signal SIGTERM \
     -p 7788:7788 \
     -v /path/to/config:/opt/stacks/config \
     -v /path/to/download:/opt/stacks/download \
     -v /path/to/logs:/opt/stacks/logs \
     -e USERNAME=admin \
     -e PASSWORD=stacks \
     -e SOLVERR_URL=flaresolverr:8191 \
     -e TZ=UTC \
     --restart unless-stopped \
     zelest/stacks:latest
   ```

**Important notes**

- `USERNAME` and `PASSWORD` only apply on **first run**; afterward Stacks is configured via `config.yaml`.
- Change the left side of `-p 7788:7788` if port 7788 is already taken.
- Always **change the default password** before exposing Stacks publicly.
- To reset the admin password later, add:

  ```bash
  -e RESET_ADMIN=true
  ```
### User access rights

By default, Stacks runs as  `root` inside the container. This is normal fo rmany Docker images, but means that any files created or mounted volumes will also belong to `root` on the host. 

If your other pass can't access the downloaded files, or you prefer stricter permission control, you can tell Docker to run Stacks as a different user.

**Set a specific user in Docker Compose**
```yaml
 services:
   stacks:
     # Use previous config and add:
     user: 1000:1000 # Replace with the UID:GID you want Stacks to use
```
**Set a specific user in Docker CLI**
```bash
docker run -d \
  --user 1000:1000 \
  ...
  zelest/stacks:latest
``` 

If Stacks already have created files as `root`, you may need to update ownership nefore switching users:
```bash
sudo chown -R 1000:1000 /path/to/config
sudo chown -R 1000:1000 /path/to/download
sudo chown -R 1000:1000 /path/to/logs
```
Replace the UID/GID and paths to match your setup.

## First-Time Setup

1. Navigate to the web interface at `http://localhost:7788`
2. Log in with default credentials (or custom if set via environment variables)
3. Go to **Settings** tab
4. **Change your password** in the Login Credentials section
5. Copy your API key for usage with the Tampermonkey script in step 9
6. _(Optional)_ Configure your Anna's Archive [fast download key](./docs/usage.md#getting-a-fast-download-key) and enable fast downloads.
7. Adjust download delays and retry settings as needed
8. Click **Save Settings**
9. Install the Tampermonkey Script (see [the Tampermonkey documentation](./docs/tampermonkey.md) for more information)

## Security

Stacks implements multiple layers of security:

- **Password Authentication**: Bcrypt-hashed passwords with salt
- **Session Management**: Secure HTTPOnly cookies with SameSite protection
- **Rate Limiting**: 5 failed login attempts triggers 10-minute lockout
- **API Key Authentication**: Secure 32-character keys for external tools
- **Auto-generated Secrets**: API keys and session secrets generated on first run

**Security Best Practices:**

1. Change the default password immediately after first login
2. Use strong, unique passwords
3. Keep your API key secure
4. Don't expose Stacks directly to the internet without additional security (use a VPN or reverse proxy with HTTPS)

## Further reading

- [API Manual](./docs/api.md)
- [Build your own image](./docs/development.md)
- [Configuration](./docs/configuration.md)
- [Tampermonkey installation](./docs/tampermonkey.md)
- [Usage](./docs/usage.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for personal use only. Please respect copyright laws and Anna's Archive's terms of service. Support authors and publishers when possible by purchasing their work.
