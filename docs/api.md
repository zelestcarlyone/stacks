# API Endpoints

## Authentication

All API endpoints (except `/api/health` and `/api/version`) require authentication via:

- **Web UI**: Session cookie (automatic after login)
- **External tools**: `X-API-Key` header or `api_key` query parameter

**Get your API key:** Log in to web UI → Settings tab → API Key section

## API Endpoints

### System

| Endpoint       | Method | Auth Required      | Description                               |
| -------------- | ------ | ------------------ | ----------------------------------------- |
| `/api/health`  | GET    | No                 | Health check - returns `{"status": "ok"}` |
| `/api/logs`    | GET    | Session or API key | Get the last 1000 lines of the system log |
| `/api/version` | GET    | No                 | Get current Stacks version                |

### Authentication & Keys

| Endpoint              | Method | Auth Required | Description                                |
| --------------------- | ------ | ------------- | ------------------------------------------ |
| `/api/key`            | GET    | Session only  | Get API key (web UI only)                  |
| `/api/key/regenerate` | POST   | Session only  | Generate new API key (invalidates old one) |

### Queue Management

| Endpoint            | Method | Auth Required      | Description                                              |
| ------------------- | ------ | ------------------ | -------------------------------------------------------- |
| `/api/status`       | GET    | Session or API key | Get current queue, downloads, history, and fast download |
| `/api/queue/add`    | POST   | Session or API key | Add item to download queue                               |
| `/api/queue/remove` | POST   | Session or API key | Remove item from queue by MD5                            |
| `/api/queue/clear`  | POST   | Session or API key | Clear entire queue                                       |

### History Management

| Endpoint             | Method | Auth Required      | Description             |
| -------------------- | ------ | ------------------ | ----------------------- |
| `/api/history/clear` | POST   | Session or API key | Clear download history  |
| `/api/history/retry` | POST   | Session or API key | Retry a failed download |

### Configuration

| Endpoint               | Method | Auth Required      | Description                        |
| ---------------------- | ------ | ------------------ | ---------------------------------- |
| `/api/config`          | GET    | Session or API key | Get current configuration          |
| `/api/config`          | POST   | Session or API key | Update configuration (live reload) |
| `/api/config/test_key` | POST   | Session or API key | Test fast download key validity    |

## Example Usage

### With API Key (for scripts/external tools):

```bash
curl -X POST http://localhost:7788/api/queue/add \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_32_CHARACTER_API_KEY" \
  -d '{
    "md5": "1d6fd221af5b9c9bffbd398041013de8",
    "title": "Example Book Title",
    "source": "manual"
  }'
```

Response:

```json
{
  "success": true,
  "message": "Added to queue",
  "md5": "abc123..."
}
```
