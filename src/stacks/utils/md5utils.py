import re

def extract_md5(input_string):
    """Extract MD5 hash from URL or return the MD5 if it's already one."""
    if re.match(r'^[a-f0-9]{32}$', input_string.lower()):
        return input_string.lower()
    
    match = re.search(r'/md5/([a-f0-9]{32})', input_string)
    if match:
        return match.group(1)
    
    return None
