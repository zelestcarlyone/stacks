from pathlib import Path
import re
import time
import os
import logging

# Directory paths
# Allow override via environment variable (needed for PEX deployments)
PROJECT_ROOT = Path(os.environ.get('STACKS_PROJECT_ROOT', Path(__file__).resolve().parent.parent.parent))

DOWNLOAD_PATH = PROJECT_ROOT / "download"
INCOMPLETE_PATH = PROJECT_ROOT / "download" / "incomplete"
LOG_PATH = PROJECT_ROOT / "logs"
CACHE_PATH = PROJECT_ROOT / "cache"
CONFIG_PATH = PROJECT_ROOT / "config"
FILES_PATH = PROJECT_ROOT / "files"
WWW_PATH = PROJECT_ROOT / "web"

# File Paths
QUEUE_FILE = CONFIG_PATH / "queue.json"
CONFIG_FILE = CONFIG_PATH / "config.yaml"
CONFIG_SCHEMA_FILE = FILES_PATH / "config_schema.yaml"
COOKIE_CACHE_DIR = CACHE_PATH  # Directory for domain-specific cookie files

# URLs
FAST_DOWNLOAD_API_URL = "https://annas-archive.org/dyn/api/fast_download.json"

# Logging
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_LEVELS = ["INFO", "ERROR", "WARN", "DEBUG"]
LOG_VIEW_LENGTH = 1000

# Default credentials
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "stacks"

# Rate limiting settings
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 10
LOGIN_ATTEMPT_WINDOW_MINUTES = 10

# Precompiled Regex
RE_IPV4 = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?::(?:6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5]\d{4}|[1-9]\d{0,3}))?$")
RE_IPV6 = re.compile(r"^((\[((?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}|([0-9A-Fa-f]{1,4}:){1,7}:|:([0-9A-Fa-f]{1,4}:){1,7}|([0-9A-Fa-f]{1,4}:){1,6}[0-9A-Fa-f]{1,4}|([0-9A-Fa-f]{1,4}:){1,5}(:[0-9A-Fa-f]{1,4}){1,2}|([0-9A-Fa-f]{1,4}:){1,4}(:[0-9A-Fa-f]{1,4}){1,3}|([0-9A-Fa-f]{1,4}:){1,3}(:[0-9A-Fa-f]{1,4}){1,4}|([0-9A-Fa-f]{1,4}:){1,2}(:[0-9A-Fa-f]{1,4}){1,5}|[0-9A-Fa-f]{1,4}:((:[0-9A-Fa-f]{1,4}){1,6})|:((:[0-9A-Fa-f]{1,4}){1,7}))\])(?::(?:6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5]\d{4}|[1-9]\d{0,3}))?$|(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}|([0-9A-Fa-f]{1,4}:){1,7}:|:([0-9A-Fa-f]{1,4}:){1,7}|([0-9A-Fa-f]{1,4}:){1,6}[0-9A-Fa-f]{1,4}|([0-9A-Fa-f]{1,4}:){1,5}(:[0-9A-Fa-f]{1,4}){1,2}|([0-9A-Fa-f]{1,4}:){1,4}(:[0-9A-Fa-f]{1,4}){1,3}|([0-9A-Fa-f]{1,4}:){1,3}(:[0-9A-Fa-f]{1,4}){1,4}|([0-9A-Fa-f]{1,4}:){1,2}(:[0-9A-Fa-f]{1,4}){1,5}|[0-9A-Fa-f]{1,4}:((:[0-9A-Fa-f]{1,4}){1,6})|:((:[0-9A-Fa-f]{1,4}){1,7}))$")
RE_URL = re.compile(r"^(?:https?:\/\/)?(?=[a-zA-Z0-9])[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*(?::(?:6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5]\d{4}|[1-9]\d{0,3}))?$")
RE_32_BIT_KEY = re.compile(r"^[A-Za-z0-9_-]{32}$")

# Known MD5 for testing
KNOWN_MD5 = "d6e1dc51a50726f00ec438af21952a45"

# Cache busting
TIMESTAMP = time.time()

# Legal files
LEGAL_FILES = ['.7z', '.ai', '.azw', '.azw3', '.cb7', '.cbr', '.cbz', '.chm', '.djvu', '.doc', '.docx', '.epub', '.exe', '.fb2', '.gz', '.htm', '.html', '.htmlz', '.jpg', '.json', '.lit', '.lrf', '.mht', '.mobi', '.odt', '.pdb', '.pdf', '.ppt', '.pptx', '.prc', '.rar', '.rtf', '.snb', '.tar', '.tif', '.txt', '.updb', '.xls', '.xlsx', '.zip']

# Version information (loaded once at startup)
def _load_version():
    """Load version from version file"""
    try:
        version_file = PROJECT_ROOT / "VERSION"
        with open(version_file) as f:
            return f.read().strip()
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to load version: {e}")
        return "unknown"

def _load_tamper_version():
    """Load tampermonkey script version from script metadata"""
    try:
        tamper_script = PROJECT_ROOT / "web" / "tamper" / "stacks_extension.user.js"
        if tamper_script.exists():
            with open(tamper_script, 'r', encoding='utf-8') as f:
                content = f.read(2000)  # Read first 2000 chars (metadata block)
                match = re.search(r'//\s*@version\s+(\S+)', content)
                if match:
                    return match.group(1)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to load tampermonkey version: {e}")
    return None

VERSION = _load_version()
TAMPER_VERSION = _load_tamper_version()