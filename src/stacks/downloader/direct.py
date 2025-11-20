import re
import time
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
