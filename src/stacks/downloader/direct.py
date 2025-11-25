import re
import time
import requests
import shutil
import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote

def calculate_md5(filepath):
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def download_direct(d, download_url, title=None, total_size=None, supports_resume=True, resume_attempts=3, md5=None):
    """Download a file directly from a URL with resume support.

    Args:
        d: Downloader instance
        download_url: URL to download from
        title: Expected filename
        total_size: Expected file size (optional)
        supports_resume: Whether resume is supported
        resume_attempts: Number of resume attempts
        md5: Expected MD5 hash for verification (optional)
    """
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

                # Verify MD5 hash if provided
                if md5:
                    d.logger.info("Verifying MD5 checksum...")
                    file_md5 = calculate_md5(temp_path)
                    if file_md5.lower() != md5.lower():
                        d.logger.error(f"MD5 mismatch: expected {md5}, got {file_md5}")
                        temp_path.unlink()
                        return None
                    d.logger.info("MD5 checksum verified")

                # Move to final location
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(temp_path), str(final_path))

                d.logger.info(f"Downloaded: {final_path.name}")
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
