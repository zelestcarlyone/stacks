# Usage

## Web Interface

The web interface provides two main tabs:

- **Downloads Tab**: Monitor current download, view queue, and check history
- **Settings Tab**: Configure download behavior, login credentials, fast download API, and logging

The dashboard updates in real-time every 2 seconds, showing:

- Current download progress with live percentage and transfer rate
- Queue size and upcoming downloads
- Recent download history with success/failure indicators
- Fast download quota (when enabled)

## FlareSolverr Integration

### What is FlareSolverr?

FlareSolverr is a proxy server that solves Cloudflare and DDoS-Guard challenges. Many mirror sites use these protections, which can block automated downloads. FlareSolverr bypasses these challenges, allowing Stacks to download from protected mirrors.

### When do you need it?

- **Recommended for most users** - Many slow download mirrors are protected by Cloudflare or DDoS-Guard
- **Required if downloads fail with 403 errors** - This indicates protection is blocking the download
- **Optional if using only fast downloads** - Fast download API doesn't need FlareSolverr

### Setup

If you used the provided docker-compose.yml, FlareSolverr is already included and configured. If not:

1. Deploy FlareSolverr (see docker-compose.yml for reference)
2. In Stacks Settings tab:
   - Enter FlareSolverr URL (e.g., `http://flaresolverr:8191`)
   - Set timeout (60 seconds recommended)
   - Click "Test FlareSolverr" to verify connection
   - Enable FlareSolverr and save settings

### How it works

- Stacks automatically uses FlareSolverr when it encounters 403 errors
- Cookies are cached per-domain for 24 hours to reduce FlareSolverr calls
- Pre-warming: Cookies are refreshed automatically on startup
- No manual intervention needed once configured

## Getting a Fast Download Key

1. Become a member of Anna's Archive (supports the project!)
2. Log into your account on Anna's Archive
3. Navigate to your account settings
4. Find your secret key in the API/Fast Downloads section
5. Copy the key and paste it into the Settings tab in Stacks
6. Click "Test Key" to verify it works
7. Enable fast downloads and save settings

The dashboard will show your remaining fast downloads quota when enabled.

## Authentication

### Default Credentials

- **Default username:** `admin`
- **Default password:** `stacks`

**IMPORTANT:** Change the default password after first login via the Settings tab!

### Changing Login Credentials

You can change your login credentials in two ways:

1. **Via Web Interface**

   - Log in to Stacks
   - Go to Settings tab
   - Update Username and/or Password
   - Click Save Settings

2. **Via Environment Variables**

   This sets the initial credentials only. Once set, you must change credentials via web interface or reset the password through the methods mentioned below.

   Edit `docker-compose.yml`:

   ```yaml
   environment:
     - USERNAME=yourusername
     - PASSWORD=yourpassword
   ```

### Resetting Forgotten Password

If you forget your password:

1. Stop the container
2. Edit `docker-compose.yml` and set:
   ```yaml
   environment:
     - RESET_ADMIN=true
     - PASSWORD=new_password
   ```
3. Restart the container with `docker compose up` or `./build.sh`
4. Log in with the new password
5. Remove `RESET_ADMIN=true` from docker-compose.yml