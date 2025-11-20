from pathlib import Path

# Directory paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DOWNLOAD_PATH = PROJECT_ROOT / "download"
INCOMPLETE_PATH = PROJECT_ROOT / "download" / "incomplete"
LOG_PATH = PROJECT_ROOT / "logs"
CACHE_PATH = PROJECT_ROOT / "cache"
CONFIG_PATH = PROJECT_ROOT / "config"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "files"
WWW_PATH = PROJECT_ROOT / "web"

# File Papths
QUEUE_FILE = CONFIG_PATH / "queue.json"
CONFIG_FILE = CONFIG_PATH / "config.yaml"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_PATH / "config.yaml"
COOKIE_CACHE_FILE = CACHE_PATH / "cookie.json"

# URLs
FAST_DOWNLOAD_API_URL = "https://annas-archive.org/dyn/api/fast_download.json"

# Logging
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Default credentials
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "stacks"

# Rate limiting settings
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 10
LOGIN_ATTEMPT_WINDOW_MINUTES = 10