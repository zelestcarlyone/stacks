import threading
import yaml
import os
import logging
from stacks.constants import CONFIG_FILE, DEFAULT_USERNAME, DEFAULT_PASSWORD

from stacks.security.auth import (
    generate_api_key,
    hash_password,
    is_valid_bcrypt_hash,
)

class Config:
    """Configuration loader with live update support"""
    def __init__(self, config_path = CONFIG_FILE):
        self.config_path = config_path
        self.lock = threading.Lock()
        self.load()
        self.ensure_api_key()
        self.ensure_session_secret()
        self.ensure_login_credentials()
    
    def load(self):
        """Load configuration from file"""
        with self.lock:
            with open(self.config_path, 'r') as f:
                self.data = yaml.safe_load(f)
    
    def save(self):
        """Save configuration to file"""
        with self.lock:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)
    
    def ensure_api_key(self):
        """Ensure API key exists, generate if not present"""
        api_key = self.get('api', 'key')
        if not api_key:
            new_key = generate_api_key()
            self.set('api', 'key', value=new_key)
            self.save()
            logger = logging.getLogger('config')
            logger.info("Generated new API key")
    
    def ensure_session_secret(self):
        """Ensure session secret exists, generate if not present"""
        session_secret = self.get('api', 'session_secret')
        if not session_secret:
            new_secret = generate_api_key()  # Same format, 32 chars
            self.set('api', 'session_secret', value=new_secret)
            self.save()
            logger = logging.getLogger('config')
            logger.info("Generated new session secret")
    
    def ensure_login_credentials(self):
        """Ensure login credentials exist, generate from env vars or defaults"""
        logger = logging.getLogger('config')
        username = self.get('login', 'username')
        password_hash = self.get('login', 'password')
        
        # Check for RESET_ADMIN environment variable
        reset_admin = os.environ.get('RESET_ADMIN', '').lower() == 'true'
        
        # Determine if we need to reset/set credentials
        needs_reset = (
            reset_admin or
            not username or
            not password_hash or
            not is_valid_bcrypt_hash(password_hash)
        )
        
        if needs_reset:
            # Get credentials from environment or use defaults
            env_username = os.environ.get('USERNAME', DEFAULT_USERNAME)
            env_password = os.environ.get('PASSWORD', DEFAULT_PASSWORD)
            
            # Hash the password
            hashed = hash_password(env_password)
            
            # Save to config
            self.set('login', 'username', value=env_username)
            self.set('login', 'password', value=hashed)
            self.save()
            
            if reset_admin:
                logger.warning("RESET_ADMIN=true detected - Admin password has been reset")
            elif not username or not password_hash:
                logger.info(f"Initialized login credentials - username: {env_username}")
            else:
                logger.warning("Invalid password hash detected - credentials reset from environment")
    
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