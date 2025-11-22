# Claude Development Guide for Stacks

## Project Overview

**Stacks** is a containerized download queue manager for Anna's Archive. It provides automated book downloading with a web-based dashboard, browser extension integration, and support for both fast downloads (via Anna's Archive API) and fallback mirror downloads.

- **Language**: Python 3.11
- **Framework**: Flask 3.1.2
- **Container**: Docker with distroless runtime
- **License**: MIT
- **Current Version**: 1.0.2

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Browser (Tampermonkey Extension + Web UI)                   │
└────────────────┬────────────────────────────────────────────┘
                 │ API Key / Session Auth
┌────────────────▼────────────────────────────────────────────┐
│ Flask Server (stacks_server.py)                             │
│  - Authentication & Sessions                                │
│  - REST API                                                 │
│  - DownloadQueue & DownloadWorker                           │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│ Download Engine (stacks_downloader.py)                      │
│  - Fast Download (Anna's Archive API)                       │
│  - Mirror Scraping (BeautifulSoup)                          │
│  - Resume Support                                           │
└─────────────────────────────────────────────────────────────┘
```

## Key File Locations

### Core Python Files
- `/home/user/stacks/stacks_server.py` - Flask web server, API, queue management (1062 lines)
- `/home/user/stacks/stacks_downloader.py` - Download engine with retry logic (740 lines)
- `/home/user/stacks/startup.py` - Container initialization and first-run setup

### Configuration & Build
- `/home/user/stacks/docker-compose.yml` - Container orchestration
- `/home/user/stacks/Dockerfile` - Multi-stage build (builder + distroless runtime)
- `/home/user/stacks/build.sh` - Build automation with version injection
- `/home/user/stacks/requirements.txt` - Python dependencies
- `/home/user/stacks/files/config.yaml` - Default configuration template

### Web Interface
- `/home/user/stacks/web/index.html` - Main dashboard
- `/home/user/stacks/web/login.html` - Login page
- `/home/user/stacks/web/script/app.js` - Dashboard logic (447 lines)
- `/home/user/stacks/web/script/login.js` - Login handler
- `/home/user/stacks/web/css/style.css` - Dracula-themed UI (690 lines)
- `/home/user/stacks/web/tamper/stacks_extension.user.js` - Tampermonkey script (517 lines)

### Documentation
- `/home/user/stacks/readme.md` - Main documentation
- `/home/user/stacks/docs/api.md` - REST API reference
- `/home/user/stacks/docs/configuration.md` - Configuration guide
- `/home/user/stacks/docs/usage.md` - User guide
- `/home/user/stacks/docs/development.md` - Development setup
- `/home/user/stacks/docs/tampermonkey.md` - Browser extension guide
- `/home/user/stacks/CHANGELOG.md` - Version history

## Core Classes and Components

### 1. Config (stacks_server.py)
**Purpose**: Thread-safe configuration management with live reload

**Key Methods**:
- `load()` - Load YAML configuration
- `save()` - Persist changes to disk
- `ensure_api_key()` - Auto-generate API keys
- `ensure_session_secret()` - Session security
- `ensure_login_credentials()` - Password initialization

**Thread Safety**: Uses `threading.Lock` for concurrent access

**Location in code**: stacks_server.py:46-155

### 2. DownloadQueue (stacks_server.py)
**Purpose**: Queue management with JSON persistence

**Key Methods**:
- `add(md5, title, source)` - Add to queue (prevents duplicates)
- `get_next()` - Get next pending download
- `mark_complete(md5, success, error, filename)` - Move to history
- `save()` - Persist to `/opt/stacks/config/queue.json`

**Storage Format**:
```json
{
  "queue": [{"md5": "...", "title": "...", "source": "...", "added_at": "..."}],
  "history": [{"md5": "...", "title": "...", "success": true, "completed_at": "..."}]
}
```

**Location in code**: stacks_server.py:158-274

### 3. DownloadWorker (stacks_server.py)
**Purpose**: Background thread that processes download queue

**Key Methods**:
- `start()` - Launch worker thread (daemon)
- `stop()` - Graceful shutdown with timeout
- `_worker_loop()` - Main processing loop with retry logic
- `update_config()` - Live config reload

**Features**:
- Configurable delay between downloads
- Retry mechanism with exponential backoff
- Resume support for interrupted downloads
- Real-time progress callbacks

**Location in code**: stacks_server.py:277-482

### 4. AnnaDownloader (stacks_downloader.py)
**Purpose**: Download engine with multiple strategies

**Key Methods**:
- `download(input_string)` - Main entry point
- `try_fast_download(md5)` - Member API downloads (returns link)
- `get_download_links(md5)` - Scrape mirror sites
- `download_direct(url, filename)` - HTTP streaming download with resume
- `refresh_fast_download_info()` - Quota tracking

**Features**:
- HTTP Range header support for resume
- Progress callbacks (10KB chunks)
- Unique filename generation
- Content-type detection from headers

**Location in code**: stacks_downloader.py (entire file)

## Authentication & Security

### Session-Based (Web UI)
- Login via `POST /login` with username/password
- Bcrypt password hashing (cost factor 12)
- HTTPOnly cookies with 30-day lifetime
- SameSite=Lax for CSRF protection
- Rate limiting: 5 failed attempts = 10-minute lockout

**Implementation**: stacks_server.py:641-701, 715-724

### API Key (External Tools)
- Header: `X-API-Key: <32-char-key>`
- Query param: `?api_key=<32-char-key>`
- Auto-generated on first run (32 bytes from `secrets.token_hex`)
- Regenerable via web UI (session required)

**Implementation**: stacks_server.py:598-638

## REST API Endpoints

### Public (No Auth)
- `GET /api/health` - Health check
- `GET /api/version` - Version info

### Session or API Key Required
- `GET /api/status` - Queue status and current download
- `POST /api/queue/add` - Add download (params: md5, title, source)
- `POST /api/queue/remove` - Remove from queue (param: md5)
- `POST /api/queue/clear` - Clear entire queue
- `POST /api/history/clear` - Clear history
- `POST /api/history/retry` - Retry failed download (param: md5)
- `GET /api/config` - Get configuration
- `POST /api/config` - Update configuration (live reload)
- `POST /api/config/test_key` - Test fast download key

### Session Only (Web UI)
- `GET /api/key` - Get current API key
- `POST /api/key/regenerate` - Generate new API key

**Full documentation**: docs/api.md

## Configuration Schema

Located at `/opt/stacks/config/config.yaml` (auto-generated from `/files/config.yaml`):

```yaml
server:
  host: "0.0.0.0"        # Bind address
  port: 7788             # Web server port

login:
  username: null         # Auto-generated or from env
  password: null         # Bcrypt hash

api:
  key: null              # 32-char API key (auto-generated)
  session_secret: null   # Flask session secret

downloads:
  delay: 2               # Seconds between downloads
  retry_count: 3         # Retries per download
  resume_attempts: 3     # Resume attempts for .part files

fast_download:
  enabled: false         # Toggle Anna's Archive API
  key: null              # Member key for fast downloads

queue:
  max_history: 100       # Max items in history

logging:
  level: "INFO"          # DEBUG, INFO, WARN, ERROR
```

**Live Reload**: Changes to config via API immediately update `DownloadWorker` without restart

## Coding Conventions & Patterns

### 1. Error Handling
- Use try/except blocks with specific exceptions
- Log errors with `logger.error()` including context
- Return meaningful error messages in API responses
- Example pattern:
  ```python
  try:
      # operation
  except SpecificException as e:
      logger.error(f"Context: {e}")
      return jsonify({"success": False, "error": str(e)}), 500
  ```

### 2. Thread Safety
- Use `threading.Lock()` for shared resources (Config, DownloadQueue)
- Always use `with lock:` context manager
- Example:
  ```python
  with self.lock:
      # thread-safe operation
  ```

### 3. Logging
- Use Python's logging module with configured formatters
- Log levels: DEBUG (verbose), INFO (normal), WARN (issues), ERROR (failures)
- Format: `%(asctime)s - %(levelname)s - %(message)s`
- Location: stacks_server.py:34-44, stacks_downloader.py:31-40

### 4. API Response Format
- Success: `{"success": True, "data": {...}}`
- Error: `{"success": False, "error": "message"}`
- Always return appropriate HTTP status codes

### 5. File Operations
- Use `os.path.exists()` before reading
- Use `os.makedirs(exist_ok=True)` for directory creation
- Handle encoding explicitly (`encoding='utf-8'`)
- Close file handles or use context managers

### 6. Progress Callbacks
- Used in downloads for real-time updates
- Signature: `callback(current_bytes, total_bytes)`
- Example: stacks_downloader.py:646-651

## Common Development Tasks

### Adding a New API Endpoint
1. Add route in stacks_server.py with appropriate decorator:
   ```python
   @app.route('/api/new_endpoint', methods=['POST'])
   @require_auth  # or @require_session
   def new_endpoint():
       # implementation
   ```
2. Update docs/api.md with endpoint documentation
3. If needed, add corresponding frontend code in web/script/app.js
4. Test with curl or web UI

### Adding a Configuration Option
1. Add to default config in files/config.yaml
2. Update Config class if special handling needed (stacks_server.py:46-155)
3. Update docs/configuration.md
4. If affects download worker, update `DownloadWorker.update_config()` (stacks_server.py:338-363)

### Modifying Download Logic
1. Edit AnnaDownloader class in stacks_downloader.py
2. Consider backward compatibility with existing queue items
3. Test both fast download and mirror fallback paths
4. Update retry logic if needed (stacks_server.py:413-442)

### Updating Web UI
1. HTML changes: web/index.html or web/login.html
2. JavaScript: web/script/app.js or web/script/login.js
3. Styling: web/css/style.css (Dracula theme colors)
4. Test authentication flows (session and API key)

### Modifying Tampermonkey Extension
1. Edit web/tamper/stacks_extension.user.js
2. Update version number and metadata
3. Test on Anna's Archive search/download pages
4. Update docs/tampermonkey.md if behavior changes

## Testing Guidelines

### Manual Testing
1. **Authentication**:
   - Login with correct/incorrect credentials
   - Test rate limiting (5 failed attempts)
   - Verify API key authentication
   - Test session persistence

2. **Queue Operations**:
   - Add items (duplicate prevention)
   - Remove items
   - Clear queue
   - View history

3. **Downloads**:
   - Fast download with valid key
   - Mirror fallback when fast download unavailable
   - Resume interrupted downloads (.part files)
   - Retry failed downloads

4. **Configuration**:
   - Update settings via UI
   - Verify live reload (no restart needed)
   - Test fast download key validation

### Testing with curl
See docs/api.md for curl examples. Basic pattern:
```bash
# With API key
curl -H "X-API-Key: your-key-here" http://localhost:7788/api/status

# Add to queue
curl -X POST -H "X-API-Key: your-key-here" \
  -H "Content-Type: application/json" \
  -d '{"md5":"abc123","title":"Test","source":"api"}' \
  http://localhost:7788/api/queue/add
```

## Build & Deployment

### Building Docker Image
```bash
./build.sh
```

**What build.sh does**:
1. Checks for project fingerprint (dfb58278-7000-469c-91be-84466af5f8e9)
2. Stops and removes existing container
3. Removes old images
4. Reads version from VERSION file
5. Builds multi-stage Docker image with version label
6. Starts container
7. Attaches to logs

### Docker Compose
```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild
docker-compose up -d --build
```

### Environment Variables (docker-compose.yml)
- `USERNAME` - Initial admin username (default: admin)
- `PASSWORD` - Initial admin password (default: auto-generated)
- `TZ` - Timezone (default: America/New_York)
- `RESET_ADMIN` - Set to 'true' to reset admin password on restart

### Volume Mounts
- `/opt/stacks/config` - Configuration and queue state
- `/opt/stacks/download` - Downloaded files
- `/opt/stacks/logs` - Log files

## Important Security Considerations

1. **Never commit secrets**:
   - API keys are auto-generated
   - Passwords are hashed with bcrypt
   - Session secrets are random

2. **Container Security**:
   - Distroless runtime (no shell, minimal attack surface)
   - Non-root user in container
   - Minimal dependencies

3. **Network Security**:
   - CORS configured for specific origins
   - CSRF protection via SameSite cookies
   - HTTPOnly cookies prevent XSS theft

4. **Rate Limiting**:
   - Implemented for login attempts
   - Consider adding to API endpoints if abuse occurs

5. **Input Validation**:
   - MD5 format validation before processing
   - URL validation for download sources
   - Configuration value bounds checking

## Debugging Tips

### Viewing Logs
```bash
# Container logs
docker-compose logs -f stacks

# Log files in volume
docker exec -it stacks ls -la /opt/stacks/logs/

# Follow specific log
docker exec -it stacks tail -f /opt/stacks/logs/stacks.log
```

### Common Issues

1. **Downloads failing**:
   - Check Anna's Archive availability
   - Verify fast download key if enabled
   - Check network connectivity from container
   - Review logs for specific error messages

2. **Queue not processing**:
   - Verify DownloadWorker thread is running (check logs)
   - Check delay configuration (downloads.delay in config)
   - Ensure no infinite retry loop (check retry_count)

3. **Authentication issues**:
   - Verify bcrypt password hash in config.yaml
   - Check session secret is set
   - Clear browser cookies
   - Use RESET_ADMIN=true to reset password

4. **API key not working**:
   - Verify key in config.yaml matches request
   - Check header format: `X-API-Key: <key>`
   - Regenerate key if corrupted

## Version History

- **1.0.2** - Hotfix release (current)
- **1.0.1** - Hotfix release
- **1.0.0** - Initial public release

See CHANGELOG.md for detailed changes.

## External Dependencies

### Python Packages (requirements.txt)
- Flask==3.1.2 - Web framework
- Flask-Cors==6.0.1 - CORS handling
- requests==2.32.5 - HTTP client
- beautifulsoup4==4.14.2 - HTML parsing
- PyYAML==6.0.3 - YAML config
- bcrypt==5.0.0 - Password hashing

### External Services
- **Anna's Archive** (annas-archive.org) - Primary download source
- **Mirror Sites** - Fallback download sources (scraped from Anna's Archive)

## Code Quality Guidelines

1. **Keep functions focused**: Each function should do one thing well
2. **Use descriptive names**: Variable and function names should be self-documenting
3. **Add docstrings**: Document complex functions and classes
4. **Handle edge cases**: Null checks, empty lists, network failures
5. **Log appropriately**: Info for normal flow, warn for issues, error for failures
6. **Maintain backward compatibility**: Queue format, API endpoints, configuration
7. **Test before committing**: Manual testing of affected functionality

## Future Enhancement Areas

Based on code review, potential areas for improvement:

1. **Unit tests**: Add pytest-based test suite
2. **Database**: Consider SQLite for queue/history instead of JSON
3. **Download scheduling**: Add time-based download scheduling
4. **Notifications**: Email/webhook notifications for completed downloads
5. **Bandwidth limiting**: Add download speed throttling
6. **Search integration**: Direct search within Stacks UI
7. **Multi-user support**: Multiple user accounts with separate queues
8. **API versioning**: Add /api/v1/ prefix for future compatibility

## Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Beautiful Soup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Anna's Archive](https://annas-archive.org/)

---

**Last Updated**: 2025-11-22
**For**: Claude AI Assistant
**Project Version**: 1.0.2
