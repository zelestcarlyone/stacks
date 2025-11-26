def download_from_mirror(d, mirror_url, mirror_type, md5, title=None, resume_attempts=3):
    """
    Download from any mirror with stale cookie handling.

    Logic:
    - slow_download: Use pre-warmed cookies with direct HTTP requests
    - external_mirror: Try direct, use FlareSolverr on 403 (with cookie refresh)
    """
    try:
        if mirror_type == 'slow_download':
            d.logger.debug("Accessing slow download (via cookies)")

            # Try to load cached cookies for this domain
            d.load_cached_cookies(domain='annas-archive.org')

            if hasattr(d, 'status_callback'):
                d.status_callback("Accessing slow download page...")

            try:
                # Try to fetch the slow_download page with cookies
                response = d.session.get(mirror_url, timeout=30)

                # If we get a challenge page (403/503), solve it with FlareSolverr
                if response.status_code in [403, 503]:
                    if not d.flaresolverr_url:
                        d.logger.warning(f"Got {response.status_code} but no FlareSolverr configured")
                        return None

                    d.logger.warning(f"Got {response.status_code}, solving challenge with FlareSolverr...")

                    if hasattr(d, 'status_callback'):
                        d.status_callback("Solving CAPTCHA with FlareSolverr...")

                    # Solve challenge for THIS specific URL
                    success, cookies, html_content = d.solve_with_flaresolverr(mirror_url)

                    if not success:
                        d.logger.error("FlareSolverr failed")
                        return None

                    if hasattr(d, 'status_callback'):
                        d.status_callback("Extracting download link...")

                    download_link = d.parse_download_link_from_html(html_content, md5, mirror_url)
                    if not download_link:
                        d.logger.warning("Could not find download link")
                        return None

                    if hasattr(d, 'status_callback'):
                        d.status_callback("Downloading file...")

                    d.logger.info("Found download URL via FlareSolverr, downloading...")
                    return d.download_direct(download_link, title=title, resume_attempts=resume_attempts, md5=md5)

                response.raise_for_status()

                if hasattr(d, 'status_callback'):
                    d.status_callback("Extracting download link...")

                download_link = d.parse_download_link_from_html(response.text, md5, mirror_url)
                if not download_link:
                    d.logger.warning("Could not find download link")
                    return None

                if hasattr(d, 'status_callback'):
                    d.status_callback("Downloading file...")

                d.logger.info("Found download URL, downloading...")
                return d.download_direct(download_link, title=title, resume_attempts=resume_attempts, md5=md5)

            except Exception as e:
                d.logger.error(f"Error accessing slow_download page: {e}")
                return None
        
        else:  # external_mirror
            d.logger.debug(f"Accessing external mirror: {mirror_url}")

            # Try to load cached cookies for this mirror
            d.load_cached_cookies(domain=mirror_url)

            try:
                response = d.session.get(mirror_url, timeout=30)

                # If 403, refresh cookies and retry
                if response.status_code == 403:
                    if d.flaresolverr_url:
                        d.logger.warning("Got 403 - trying to refresh cookies")

                        # Try to pre-warm new cookies
                        if d.prewarm_cookies():
                            d.logger.info("Retrying with fresh cookies...")
                            # Retry once with fresh cookies
                            response = d.session.get(mirror_url, timeout=30)

                            if response.status_code == 403:
                                d.logger.warning("Still got 403 after cookie refresh, using FlareSolverr for full solve")
                            else:
                                # Success with fresh cookies, continue to parse
                                response.raise_for_status()

                                if hasattr(d, 'status_callback'):
                                    d.status_callback("Extracting download link...")

                                download_link = d.parse_download_link_from_html(response.text, md5, mirror_url)
                                if not download_link:
                                    d.logger.warning("Could not find download link")
                                    return None

                                if hasattr(d, 'status_callback'):
                                    d.status_callback("Downloading file...")

                                return d.download_direct(download_link, title=title, resume_attempts=resume_attempts, md5=md5)

                        # If cookie refresh failed or still got 403, use FlareSolverr
                        if hasattr(d, 'status_callback'):
                            d.status_callback("Solving CAPTCHA with FlareSolverr...")
                        success, cookies, html_content = d.solve_with_flaresolverr(mirror_url)
                        if success:
                            if hasattr(d, 'status_callback'):
                                d.status_callback("Extracting download link...")
                            download_link = d.parse_download_link_from_html(html_content, md5, mirror_url)
                            if download_link:
                                if hasattr(d, 'status_callback'):
                                    d.status_callback("Downloading file...")
                                d.logger.info("Found download URL via FlareSolverr, downloading...")
                                return d.download_direct(download_link, title=title, resume_attempts=resume_attempts, md5=md5)
                        return None
                    else:
                        d.logger.warning("Got 403 but FlareSolverr not configured")
                        return None

                response.raise_for_status()

                if hasattr(d, 'status_callback'):
                    d.status_callback("Extracting download link...")

                download_link = d.parse_download_link_from_html(response.text, md5, mirror_url)
                if not download_link:
                    d.logger.warning("Could not find download link")
                    return None

                if hasattr(d, 'status_callback'):
                    d.status_callback("Downloading file...")

                return d.download_direct(download_link, title=title, resume_attempts=resume_attempts, md5=md5)
            
            except Exception as e:
                d.logger.error(f"Error accessing external mirror: {e}")
                return None
    
    except Exception as e:
        d.logger.error(f"Error downloading from mirror: {e}")
        return None