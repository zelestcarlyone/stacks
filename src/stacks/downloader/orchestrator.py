import random

def orchestrate_download(d, input_string, prefer_mirror=None, resume_attempts=3, title_override=None):
    """Download a file from Anna's Archive."""
    md5 = d.extract_md5(input_string)
    if not md5:
        d.logger.error(f"Could not extract MD5 from: {input_string}")
        return False, False
    
    d.logger.info(f"Downloading: {md5}")
    
    title, links = d.get_download_links(md5)
    
    if title_override:
        title = title_override
    
    # Try fast download first
    if d.fast_download_enabled and d.fast_download_key:
        success, result = d.try_fast_download(md5)
        
        if success:
            d.logger.info("Using fast download")
            filepath = d.download_direct(result, title=title, resume_attempts=resume_attempts)
            if filepath:
                d.logger.info("✓ Fast download successful")
                return True, True
            else:
                d.logger.warning("Fast download failed, falling back to mirrors")
        else:
            d.logger.info(f"Fast download not available: {result}")
    
    # Try aria2 multi-source if enabled
    if d.enable_aria2 and len(links) > 1:
        d.logger.info("Collecting all download URLs for multi-source...")
        all_urls = d.get_all_download_urls(md5, solve_ddos=True, max_urls=10)
        
        if len(all_urls) >= 2:
            filepath = d.download_with_aria2(all_urls, title=title, resume_attempts=resume_attempts)
            if filepath:
                d.logger.info("✓ aria2 multi-source download successful")
                return True, False
            else:
                d.logger.warning("aria2 failed, falling back to single-source")
    
    # Single-source fallback
    if not links:
        d.logger.error("No download links found")
        return False, False
    
    d.logger.info(f"Found {len(links)} mirror(s)")
    
    # Preferred mirror
    if prefer_mirror:
        preferred = [l for l in links if prefer_mirror.lower() in l['domain'].lower()]
        others = [l for l in links if prefer_mirror.lower() not in l['domain'].lower()]
        links = preferred + others
    else:
        # Shuffle to spread load across mirrors (unless user has preference)
        random.shuffle(links)
    
    # Try each mirror
    for i, mirror_link in enumerate(links):
        mirror_name = mirror_link.get('text', mirror_link.get('domain', 'Unknown'))
        d.logger.info(f"Trying mirror {i+1}/{len(links)}: {mirror_name}")
        
        filepath = d.download_from_mirror(
            mirror_link['url'],
            mirror_link['type'],
            md5,
            title=title,
            resume_attempts=resume_attempts
        )
        
        if filepath:
            d.logger.info("✓ Download successful")
            return True, False
        else:
            d.logger.warning(f"Mirror {mirror_name} failed")
            if i < len(links) - 1:
                d.logger.info("Trying next mirror...")
    
    d.logger.error("All mirrors failed")
    return False, False