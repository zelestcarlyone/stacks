import threading
import yaml
from stacks.constants import CONFIG_FILE, CONFIG_SCHEMA_FILE
from stacks.config.validate import _validate, ensure_login_credentials

class Config:
    """Configuration loader with live update support"""

    def __init__(self, config_path=CONFIG_FILE, schema_path=CONFIG_SCHEMA_FILE):
        self.config_path = config_path
        self.schema_path = schema_path
        self.lock = threading.Lock()

        self.load_schema()
        self.load()

        self.data = self.validate(self.data, self.schema)
        self.ensure_login_credentials()

    def load(self):
        """Load configuration from file, or create empty dict."""
        with self.lock:
            try:
                with open(self.config_path, "r") as f:
                    self.data = yaml.safe_load(f) or {}
            except FileNotFoundError:
                self.data = {}

    def load_schema(self):
        """Load schema from file."""
        with self.lock:
            with open(self.schema_path, "r") as f:
                self.schema = yaml.safe_load(f)

    def save(self):
        """Save configuration to file."""
        with self.lock:
            with open(self.config_path, "w") as f:
                yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)

    def validate(self, data, schema):
        """Invoke the schema-validator to normalize the config."""
        return _validate(data, schema)
    
    def get(self, *keys, default=None):
        """Get nested config value"""
        with self.lock:
            value = self.data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return default
                if value is None:
                    return default
            return value
    
    def ensure_login_credentials(self):
        return ensure_login_credentials(self)
    
    
    def set(self, *keys, value):
        """Set nested config value"""
        with self.lock:
            # Navigate to parent
            data = self.data
            for key in keys[:-1]:
                if key not in data:
                    data[key] = {}
                data = data[key]
            # Set value
            data[keys[-1]] = value
    
    def get_all(self):
        """Get entire config as dict"""
        with self.lock:
            return self.data.copy()