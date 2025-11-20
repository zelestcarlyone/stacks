import re
import time
import random
import requests
import shutil
from pathlib import Path
from urllib.parse import urlparse, unquote

def download_direct(d, download_url, title=None, total_size=None, supports_resume=True, resume_attempts=3):
    """Download a file directly from a URL with resume support."""
    try:
        # Determine filename
        if title:
            filename = re.sub(r'[<>:"/\\|?*]', '_', title)
        else:
            parsed_url = urlparse(download_url)
            filename = unquote(Path(parsed_url.path).name)
            if not filename:
                filename = 'download'
        
        # Ensure extension
        if '.' not in filename:
            ext = '.epub'
            if '.pdf' in download_url.lower():
                ext = '.pdf'
            elif '.mobi' in download_url.lower() or '.azw' in download_url.lower():
                ext = '.mobi'
            elif '.cbr' in download_url.lower() or '.cbz' in download_url.lower():
                ext = '.cbz'
            filename = filename + ext
        
        # Clean filename
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Get unique path
        base_final_path = d.output_dir / filename
        final_path = d.get_unique_filename(base_final_path)
        temp_path = d.incomplete_dir / f"{final_path.name}.part"
        
        # Check for partial download
        downloaded = 0
        if temp_path.exists() and supports_resume:
            downloaded = temp_path.stat().st_size
            d.logger.info(f"Found partial file: {downloaded}/{total_size if total_size else '?'} bytes")
        
        # Download with resume
        for attempt in range(resume_attempts):
            try:
                headers = {}
                if downloaded > 0 and supports_resume:
                    headers['Range'] = f'bytes={downloaded}-'
                    d.logger.info(f"Resuming from byte {downloaded}")
                
                response = d.session.get(download_url, headers=headers, stream=True, timeout=30)
                
                if downloaded > 0 and response.status_code not in [200, 206]:
                    d.logger.warning(f"Resume not supported (status {response.status_code}), starting fresh")
                    downloaded = 0
                    temp_path.unlink(missing_ok=True)
                    response = d.session.get(download_url, stream=True, timeout=30)
                
                # Check for HTML content
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type:
                    first_chunk = next(response.iter_content(chunk_size=1024), None)
                    if first_chunk and (b'<html' in first_chunk.lower() or b'<!doctype' in first_chunk.lower()):
                        d.logger.warning("Downloaded content appears to be HTML, aborting")
                        return None
                    if first_chunk:
                        mode = 'ab' if downloaded > 0 else 'wb'
                        with open(temp_path, mode) as f:
                            f.write(first_chunk)
                            downloaded += len(first_chunk)
                
                # Get total size
                if total_size is None:
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        if response.status_code == 206:
                            total_size = downloaded + int(content_length)
                        else:
                            total_size = int(content_length)
                
                # Download
                mode = 'ab' if downloaded > 0 else 'wb'
                with open(temp_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if d.progress_callback and total_size:
                                percent = (downloaded / total_size) * 100
                                d.progress_callback({
                                    'total_size': total_size,
                                    'downloaded': downloaded,
                                    'percent': round(percent, 1)
                                })
                
                # Verify complete
                if total_size and downloaded < total_size:
                    raise Exception(f"Incomplete download: {downloaded}/{total_size} bytes")
                
                # Check if file is suspiciously small (expired download page)
                if temp_path.stat().st_size < 1024:
                    d.logger.warning("Downloaded file < 1KB - likely expired download page")
                    temp_path.unlink()
                    return None
                
                # Move to final location
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(temp_path), str(final_path))
                
                d.logger.info(f"✓ Downloaded: {final_path.name}")
                return final_path
                
            except requests.exceptions.ChunkedEncodingError:
                if attempt < resume_attempts - 1 and supports_resume:
                    d.logger.warning(f"Connection interrupted, resuming (attempt {attempt + 1}/{resume_attempts})")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return None
                    
            except Exception as e:
                d.logger.error(f"Download error: {e}")
                if attempt < resume_attempts - 1 and supports_resume:
                    time.sleep(2 ** attempt)
                    continue
                return None
        
        return None
        
    except Exception as e:
        d.logger.error(f"Fatal download error: {e}")
        return None
    
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

