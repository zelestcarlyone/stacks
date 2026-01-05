import json
import logging
from stacks.constants import ANNAS_ARCHIVE_DOMAINS, DOMAIN_STATE_FILE, CONFIG_PATH

logger = logging.getLogger(__name__)


def get_working_domain():
    """Get the last known working Anna's Archive domain, or the first one if none saved."""
    try:
        if DOMAIN_STATE_FILE.exists():
            with open(DOMAIN_STATE_FILE, 'r') as f:
                data = json.load(f)
                domain = data.get('last_working_domain')
                if domain and domain in ANNAS_ARCHIVE_DOMAINS:
                    logger.debug(f"Using last known working domain: {domain}")
                    return domain
    except Exception as e:
        logger.debug(f"Failed to load working domain: {e}")

    # Default to first domain
    logger.debug(f"Using default domain: {ANNAS_ARCHIVE_DOMAINS[0]}")
    return ANNAS_ARCHIVE_DOMAINS[0]


def save_working_domain(domain):
    """Save the last known working domain to state file."""
    try:
        CONFIG_PATH.mkdir(parents=True, exist_ok=True)
        with open(DOMAIN_STATE_FILE, 'w') as f:
            json.dump({'last_working_domain': domain}, f)
        logger.info(f"Saved working domain: {domain}")
    except Exception as e:
        logger.debug(f"Failed to save working domain: {e}")


def get_next_domain(current_domain):
    """Get the next domain in the rotation after the current one."""
    try:
        current_index = ANNAS_ARCHIVE_DOMAINS.index(current_domain)
        next_index = (current_index + 1) % len(ANNAS_ARCHIVE_DOMAINS)
        next_domain = ANNAS_ARCHIVE_DOMAINS[next_index]
        logger.debug(f"Rotating from {current_domain} to {next_domain}")
        return next_domain
    except (ValueError, IndexError):
        logger.debug(f"Invalid current domain {current_domain}, using default")
        return ANNAS_ARCHIVE_DOMAINS[0]


def get_all_domains():
    """Get all available Anna's Archive domains."""
    return ANNAS_ARCHIVE_DOMAINS.copy()


def try_domains_until_success(func, *args, **kwargs):
    """
    Try a function with different Anna's Archive domains until one succeeds.

    The function should accept a 'domain' parameter.
    This will try the last working domain first, then rotate through all others.
    When successful, it saves the working domain for future use.

    Args:
        func: Function to call that accepts a 'domain' parameter
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func (domain will be added/overridden)

    Returns:
        The result of the successful function call

    Raises:
        The last exception encountered if all domains fail
    """
    # Start with the last working domain
    current_domain = get_working_domain()
    tried_domains = []
    last_error = None

    # Try all domains
    for _ in range(len(ANNAS_ARCHIVE_DOMAINS)):
        if current_domain in tried_domains:
            current_domain = get_next_domain(current_domain)
            continue

        tried_domains.append(current_domain)
        logger.debug(f"Trying domain: {current_domain}")

        try:
            # Call the function with the current domain
            kwargs['domain'] = current_domain
            result = func(*args, **kwargs)

            # Success! Save this domain for future use
            save_working_domain(current_domain)
            logger.info(f"Successfully used domain: {current_domain}")
            return result

        except Exception as e:
            logger.warning(f"Failed with domain {current_domain}: {e}")
            last_error = e
            current_domain = get_next_domain(current_domain)

    # All domains failed
    logger.error(f"All Anna's Archive domains failed. Last error: {last_error}")
    raise last_error if last_error else Exception("All domains failed")
