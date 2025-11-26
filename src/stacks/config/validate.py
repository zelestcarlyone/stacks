import os
import logging
from stacks.constants import (
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
    LOG_LEVELS,
    RE_32_BIT_KEY,
    RE_IPV4,
    RE_IPV6,
    RE_URL,
)

from stacks.security.auth import (
    generate_api_key,
    hash_password,
    is_valid_bcrypt_hash,
)

logger = logging.getLogger('config')

def _validate(config: dict, schema: dict) -> dict:
    logger.debug("Validating config.")
    normalized = {}
    
    for section, section_schema in schema.items():
        user_section = config.get(section, {})
        if isinstance(section_schema, dict):
            normalized[section] = {}

            for key, rules in section_schema.items():
                value = user_section.get(key, None)               
                normalized[section][key] = _validate_value(value, rules, key)
        else:
            logging.debug(f"Error '{key}', no such key in schema.")
    logger.debug("Config validated.")
    return normalized

def _apply_default(default, key, old_value):
    match default:
        case "GENERATE_32_BIT_KEY":
            logger.info(f"Generated new 32-bit key for {key}")
            return generate_api_key()
        case "HASH_PASSWORD":
            logger.warning("Valid password missing, resetting to default.")
            default = os.environ.get('PASSWORD', DEFAULT_PASSWORD)
            return hash_password(default)
        case "USERNAME":
            logger.warning(f"Username '{old_value}' is invalid. Resetting back to '{DEFAULT_USERNAME}'.")
            default = os.environ.get('USERNAME', DEFAULT_USERNAME)
        case "FLARESOLVERR":
            default = os.environ.get("SOLVERR_URL", None)
            logger.warning(f"FlareSolverr URL is invalid Resetting back to '{default}'.")
    return default

def _validate_value(value, rules, key):
    allowed_types = rules.get("types", [])
    default = rules.get("default")
    min_value = rules.get("min")
    max_value = rules.get("max")
    max_length = rules.get("max_length")
    
    for t in allowed_types:
        match t:
            case "STRING":
                if isinstance(value, str):
                    if max_length is None or len(value) <= max_length:
                         return value
            case "INTEGER":
                if isinstance(value, int):
                    if (min_value is None or value >= min_value) and (max_value is None or value <= max_value):
                        return value
            case "BOOL":
                if isinstance(value, bool):
                    return value
            case "NULL":
                if value is None:
                    return value
            case "PORT_RANGE":
                if isinstance(value, int) and 0 <= value <= 65535:
                    return value
            case "32_BIT_KEY":
                if isinstance(value, str):
                    if RE_32_BIT_KEY.fullmatch(value):
                        return value
            case "IP":
                if isinstance(value, str):
                    if RE_IPV4.fullmatch(value) or RE_IPV6.fullmatch(value):
                        return value
            case "URL":
                if isinstance(value, str):
                    if RE_URL.fullmatch(value):
                        return value
            case "LOGGING":
                if isinstance(value, str):
                    if value.upper() in LOG_LEVELS:
                        return value
            case "BCRYPTHASH":
                if is_valid_bcrypt_hash(value) and not os.environ.get('RESET_ADMIN','').lower() == 'true':
                    return value
                
    return _apply_default(default, key, value)

def ensure_login_credentials(self):
    logger = logging.getLogger('config')

    username = self.get("login", "username")
    password_hash = self.get("login", "password")

    reset_admin = os.environ.get("RESET_ADMIN", "").lower() == "true"
    
    needs_reset = (
        reset_admin or
        not username or
        not password_hash or
        not is_valid_bcrypt_hash(password_hash)
    )

    if not needs_reset:
        return
    
    new_username = os.environ.get("USERNAME", DEFAULT_USERNAME)
    new_password = os.environ.get("PASSWORD", DEFAULT_PASSWORD)
    new_password_hash = hash_password(new_password)

    self.set("login", "username", value=new_username)
    self.set("login", "password", value=new_password_hash)
    self.save()

    if reset_admin:
        logger.warning("RESET_ADMIN=true detected - Admin credentials reset via environment/defaults")
    elif not username or not password_hash:
        logger.info(f"Login credentials initialized (username: '{new_username}')")
    else:
        logger.warning(
            f"Password hash was invalid - credentials reset using environment/defaults (username: '{new_username}')"
        )
