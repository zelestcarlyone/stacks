import random

def get_all_download_urls(d, md5, solve_ddos=True, max_urls=10):
    """Get ALL possible direct download URLs for aria2 multi-source."""
    title, links = d.get_download_links(md5)
    download_urls = []
    
    d.logger.info(f"Collecting download URLs from {len(links)} mirrors...")
    
    for i, link in enumerate(links):
        if max_urls > 0 and len(download_urls) >= max_urls:
            d.logger.info(f"Collected maximum {max_urls} URLs, stopping")
            break
        
        try:
            if link['type'] == 'slow_download':
                # Slow downloads REQUIRE FlareSolverr
                if not d.flaresolverr_url:
                    d.logger.debug(f"Skipping slow_download {i+1} (no FlareSolverr)")
                    continue
                
                d.logger.debug(f"Resolving slow_download {i+1}/{len(links)} with FlareSolverr")
                
                success, cookies, html_content = d.solve_with_flaresolverr(link['url'])
                if not success:
                    continue
                
                download_link = d.parse_download_link_from_html(html_content, md5)
                if download_link:
                    download_urls.append(download_link)
                    d.logger.debug(f"Resolved: {download_link}")
            
            elif link['type'] == 'external_mirror':
                d.logger.debug(f"Resolving external mirror {i+1}/{len(links)}")
                
                try:
                    response = d.session.get(link['url'], timeout=30)
                    
                    # If 403, try with FlareSolverr
                    if response.status_code == 403 and d.flaresolverr_url:
                        d.logger.debug(f"Mirror {i+1} returned 403, trying FlareSolverr")
                        success, cookies, html_content = d.solve_with_flaresolverr(link['url'])
                        if success:
                            download_link = d.parse_download_link_from_html(html_content, md5)
                            if download_link:
                                download_urls.append(download_link)
                                d.logger.debug(f"Resolved with FlareSolverr: {download_link}")
                        continue
                    
                    download_link = d.parse_download_link_from_html(response.text, md5)
                    if download_link:
                        download_urls.append(download_link)
                        d.logger.debug(f"Resolved: {download_link}")
                
                except Exception as e:
                    d.logger.debug(f"External mirror {i+1} error: {e}")
                    continue
        
        except Exception as e:
            d.logger.debug(f"Could not resolve mirror {i+1}: {e}")
            continue
    
    # Remove duplicates
    seen = set()
    unique_urls = []
    for url in download_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    # Shuffle to spread load across mirrors
    random.shuffle(unique_urls)
    
    d.logger.info(f"✓ Collected {len(unique_urls)} unique download URLs (shuffled)")
    return unique_urls

def download_from_mirror(d, mirror_url, mirror_type, md5, title=None, resume_attempts=3):
    """
    Download from any mirror with stale cookie handling.
    
    Logic:
    - slow_download: ALWAYS use FlareSolverr (skip if not configured)
    - external_mirror: Try direct, use FlareSolverr on 403 (with cookie refresh)
    """
    try:
        if mirror_type == 'slow_download':
            # REQUIRE FlareSolverr for slow downloads
            if not d.flaresolverr_url:
                d.logger.warning("Skipping slow_download - FlareSolverr not configured")
                return None
            
            d.logger.debug(f"Accessing slow download (via FlareSolverr)")
            
            success, cookies, html_content = d.solve_with_flaresolverr(mirror_url)
            if not success:
                d.logger.error("FlareSolverr failed")
                return None
            
            download_link = d.parse_download_link_from_html(html_content, md5)
            if not download_link:
                d.logger.warning("Could not find download link")
                return None
            
            d.logger.info(f"Found download URL, downloading...")
            return d.download_direct(download_link, title=title, resume_attempts=resume_attempts)
        
        else:  # external_mirror
            d.logger.debug(f"Accessing external mirror: {mirror_url}")
            
            try:
                response = d.session.get(mirror_url, timeout=30)
                
                # If 403, refresh cookies and retry
                if response.status_code == 403:
                    if d.flaresolverr_url:
                        d.logger.warning("Got 403 - refreshing cookies with FlareSolverr...")
                        # Pre-warm new cookies
                        if d.prewarm_cookies():
                            # Retry once with fresh cookies
                            response = d.session.get(mirror_url, timeout=30)
                            
                            if response.status_code == 403:
                                d.logger.warning("Still got 403 after cookie refresh, using FlareSolverr for full solve")
                                success, cookies, html_content = d.solve_with_flaresolverr(mirror_url)
                                if success:
                                    download_link = d.parse_download_link_from_html(html_content, md5)
                                    if download_link:
                                        d.logger.info(f"Found download URL via FlareSolverr, downloading...")
                                        return d.download_direct(download_link, title=title, resume_attempts=resume_attempts)
                                return None
                    else:
                        d.logger.warning("Got 403 but FlareSolverr not configured")
                        return None
                
                response.raise_for_status()
                
                download_link = d.parse_download_link_from_html(response.text, md5)
                if not download_link:
                    d.logger.warning("Could not find download link")
                    return None
                
                return d.download_direct(download_link, title=title, resume_attempts=resume_attempts)
            
            except Exception as e:
                d.logger.error(f"Error accessing external mirror: {e}")
                return None
    
    except Exception as e:
        d.logger.error(f"Error downloading from mirror: {e}")
        return None