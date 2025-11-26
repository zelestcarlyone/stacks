def get_unique_filename(d, base_path):
    """Generate a unique filename by adding (1), (2), etc. if file exists."""
    if not base_path.exists():
        return base_path
    
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    
    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            d.logger.info(f"File exists, using unique name: {new_name}")
            return new_path
        counter += 1