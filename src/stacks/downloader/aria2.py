import re
import subprocess
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse, unquote

def download_with_aria2(d, download_urls, title=None, resume_attempts=3):
    """Download file using aria2c with multiple sources."""
    if not d.has_aria2 or not download_urls:
        return None
    
    d.logger.info(f"Starting aria2 multi-source download from {len(download_urls)} sources")
    
    try:
        # Determine filename
        if title:
            filename = re.sub(r'[<>:"/\\|?*]', '_', title)
        else:
            parsed_url = urlparse(download_urls[0])
            filename = unquote(Path(parsed_url.path).name)
            if not filename:
                filename = 'download'
        
        # Ensure extension
        if '.' not in filename:
            ext = '.epub'
            for url in download_urls:
                if '.pdf' in url.lower():
                    ext = '.pdf'
                    break
                elif '.mobi' in url.lower() or '.azw' in url.lower():
                    ext = '.mobi'
                    break
                elif '.cbr' in url.lower() or '.cbz' in url.lower():
                    ext = '.cbz'
                    break
            filename = filename + ext
        
        # Clean filename
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Get unique path
        base_final_path = d.output_dir / filename
        final_path = d.get_unique_filename(base_final_path)
        
        # Create aria2 input file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            input_file = f.name
            for url in download_urls:
                f.write(url + '\n')
        
        try:
            cmd = [
                'aria2c',
                '--input-file', input_file,
                '--dir', str(d.incomplete_dir),
                '--out', final_path.name,
                '--max-connection-per-server', '4',
                '--min-split-size', d.aria2_chunk_size,
                '--split', str(min(len(download_urls), 16)),
                '--continue=true',
                '--max-tries', str(resume_attempts),
                '--retry-wait', '3',
                '--user-agent', d.session.headers['User-Agent'],
                '--allow-overwrite=true',
                '--auto-file-renaming=false',
            ]
            
            d.logger.debug(f"aria2c command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            for line in process.stdout:
                line = line.strip()
                if line:
                    d.logger.debug(f"aria2: {line}")
                    
                    if d.progress_callback and '%' in line:
                        try:
                            match = re.search(r'(\d+)%', line)
                            if match:
                                percent = int(match.group(1))
                                d.progress_callback({
                                    'percent': percent,
                                    'downloaded': 0,
                                    'total_size': 0
                                })
                        except Exception:
                            pass
            
            process.wait()
            
            downloaded_file = d.incomplete_dir / final_path.name
            if downloaded_file.exists():
                # Check if file is suspiciously small (expired download page)
                if downloaded_file.stat().st_size < 1024:
                    d.logger.warning("Downloaded file < 1KB - likely expired download page")
                    downloaded_file.unlink()
                    return None
                
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(downloaded_file), str(final_path))
                d.logger.info(f"✓ Downloaded: {final_path.name}")
                return final_path
            else:
                d.logger.error("aria2 completed but file not found")
                return None
                
        finally:
            try:
                Path(input_file).unlink()
            except Exception:
                pass
    
    except Exception as e:
        d.logger.error(f"aria2 download failed: {e}")
        return None