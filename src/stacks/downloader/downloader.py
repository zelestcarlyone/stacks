import argparse
import re
import sys
import time
import logging
import random
import requests
import subprocess
import shutil
import tempfile
import json
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote
from bs4 import BeautifulSoup
from stacks.constants import COOKIE_CACHE_FILE
from downloader.utils import extract_md5


class AnnaDownloader:
    def __init__(self, output_dir="./downloads", incomplete_dir=None, progress_callback=None, 
                 fast_download_config=None, flaresolverr_url=None, flaresolverr_timeout=60000,
                 enable_aria2=True, aria2_min_size_mb=2, aria2_chunk_size='1M'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if incomplete_dir:
            self.incomplete_dir = Path(incomplete_dir)
        else:
            self.incomplete_dir = self.output_dir / "incomplete"
        self.incomplete_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        })
        self.logger = logging.getLogger('stacks_downloader')
        self.progress_callback = progress_callback
        
        # Fast download configuration
        self.fast_download_config = fast_download_config or {}
        self.fast_download_enabled = self.fast_download_config.get('enabled', False)
        self.fast_download_key = self.fast_download_config.get('key')
        self.fast_download_api_url = self.fast_download_config.get(
            'api_url', 
            'https://annas-archive.org/dyn/api/fast_download.json'
        )
        
        # Fast download state
        self.fast_download_info = {
            'available': bool(self.fast_download_enabled and self.fast_download_key),
            'downloads_left': None,
            'downloads_per_day': None,
            'recently_downloaded_md5s': [],
            'last_refresh': 0
        }
        
        self.fast_download_refresh_cooldown = 3600  # 1 hour
        
        # FlareSolverr configuration
        self.flaresolverr_url = flaresolverr_url
        self.flaresolverr_timeout = flaresolverr_timeout
        
        # aria2 configuration
        self.enable_aria2 = enable_aria2
        self.aria2_min_size_mb = aria2_min_size_mb
        self.aria2_chunk_size = aria2_chunk_size
        self.has_aria2 = shutil.which('aria2c') is not None
        
        if self.enable_aria2 and self.has_aria2:
            self.logger.info(f"aria2 enabled: multi-source downloads for files >{aria2_min_size_mb}MB")
        elif self.enable_aria2 and not self.has_aria2:
            self.logger.warning("aria2 not found, multi-source downloads disabled")
            self.enable_aria2 = False
        
        if flaresolverr_url:
            self.logger.info(f"FlareSolverr enabled: {flaresolverr_url}")
            self.logger.info("Using ALL download sources (Anna's Archive + external mirrors)")
            # Load cached cookies if available
            self._load_cached_cookies()
        else:
            self.logger.warning("FlareSolverr not configured - slow_download servers will be SKIPPED")
            self.logger.info("Using external mirrors only (Libgen, library.lol, etc.)")
    
    def _load_cached_cookies(self):
        """Load cookies from cache file."""
        if COOKIE_CACHE_FILE.exists():
            try:
                with open(COOKIE_CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    # Check if cookies are recent (< 24 hours old)
                    cached_time = data.get('timestamp', 0)
                    if time.time() - cached_time < 86400:
                        cookies_dict = data.get('cookies', {})
                        for name, value in cookies_dict.items():
                            self.session.cookies.set(name, value)
                        self.logger.info(f"Loaded {len(cookies_dict)} cached cookies")
                        return True
                    else:
                        self.logger.debug("Cached cookies expired (>24h old)")
            except Exception as e:
                self.logger.debug(f"Failed to load cached cookies: {e}")
        return False
    
    def _save_cookies_to_cache(self, cookies_dict):
        """Save cookies to cache file."""
        try:
            COOKIE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(COOKIE_CACHE_FILE, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'cookies': cookies_dict
                }, f, indent=2)
            self.logger.debug(f"Cached {len(cookies_dict)} cookies")
        except Exception as e:
            self.logger.debug(f"Failed to cache cookies: {e}")
    
    def prewarm_cookies(self):
        """Pre-warm cookies using FlareSolverr if enabled."""
        if not self.flaresolverr_url:
            return False
        
        self.logger.info("Pre-warming cookies with FlareSolverr...")
        # Use a real slow_download URL to get valid cookies
        test_url = "https://annas-archive.org"
        success, cookies, _ = self.solve_with_flaresolverr(test_url)
        
        if success and cookies:
            self._save_cookies_to_cache(cookies)
            self.logger.info("✓ Cookies pre-warmed and cached")
            return True
        else:
            self.logger.warning("Failed to pre-warm cookies")
            return False
    
    def extract_md5(self, input_string):
        """Extract MD5 hash from URL or return the MD5 if it's already one."""
        return extract_md5(input_string)
    
    def get_unique_filename(self, base_path):
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
                self.logger.info(f"File exists, using unique name: {new_name}")
                return new_path
            counter += 1
    
    def solve_with_flaresolverr(self, url):
        """Use FlareSolverr to bypass DDoS-Guard/Cloudflare protection."""
        if not self.flaresolverr_url:
            return False, {}, None
        
        self.logger.info(f"Using FlareSolverr to solve protection challenge...")
        
        try:
            payload = {
                "cmd": "request.get",
                "url": url,
                "maxTimeout": self.flaresolverr_timeout
            }
            
            response = requests.post(
                f"{self.flaresolverr_url}/v1",
                json=payload,
                timeout=self.flaresolverr_timeout / 1000 + 10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'ok':
                solution = data.get('solution', {})
                cookies_list = solution.get('cookies', [])
                cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
                html_content = solution.get('response')
                
                self.logger.info(f"FlareSolverr: Success - got {len(cookies_dict)} cookies")
                
                # Apply cookies to session
                for name, value in cookies_dict.items():
                    self.session.cookies.set(name, value)
                
                # Cache cookies for future use
                self._save_cookies_to_cache(cookies_dict)
                
                return True, cookies_dict, html_content
            else:
                error_msg = data.get('message', 'Unknown error')
                self.logger.error(f"FlareSolverr failed: {error_msg}")
                return False, {}, None
                
        except requests.Timeout:
            self.logger.error("FlareSolverr timeout")
            return False, {}, None
        except Exception as e:
            self.logger.error(f"FlareSolverr error: {e}")
            return False, {}, None
    
    def parse_download_link_from_html(self, html_content, md5):
        """
        Parse HTML to extract the actual download link.
        Download links contain the first 12 characters of the MD5 hash.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Get first 12 chars of MD5 - this is what appears in download URLs
        md5_prefix = md5[:12]
        
        # Domains to skip (not actual file hosts)
        skip_domains = [
            'jdownloader.org', 'telegram.org', 't.me', 'discord.gg', 
            'reddit.com', 'twitter.com', 'facebook.com', 'instagram.com',
            'patreon.com', 'ko-fi.com', 'buymeacoffee.com',
            'annas-archive.org/account', 'annas-archive.org/search',
            'annas-archive.org/md5', 'annas-archive.org/donate'
        ]
        
        # Method 1: Look for links containing MD5 prefix (primary method for slow_download)
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Must be absolute URL
            if not href.startswith('http'):
                continue
            
            # Skip navigation/social links
            if any(skip in href.lower() for skip in skip_domains):
                continue
            
            # Skip slow_download pages (we want the ACTUAL file, not another slow_download page)
            if 'slow_download' in href.lower():
                continue
            
            # Download links contain the MD5 prefix
            if md5_prefix in href.lower():
                self.logger.debug(f"Found download link with MD5 prefix: {href}")
                return href
        
        # Method 2: Fallback for external mirrors - look for file extensions
        for link in soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text().strip().lower()
            
            # Must be absolute URL
            if not href.startswith('http'):
                continue
            
            # Skip navigation
            if any(skip in href.lower() for skip in skip_domains):
                continue
            
            # Look for download indicators
            if 'download' in link_text or 'get' in link_text:
                if any(ext in href.lower() for ext in ['.epub', '.pdf', '.mobi', '.azw3', '.cbr', '.cbz', '.djvu']) \
                   or 'get.php' in href.lower() or 'main.php' in href.lower():
                    self.logger.debug(f"Found download link via fallback: {href}")
                    return href

        # Method 3: clipboard buttons containing real URLs
        for btn in soup.find_all('button', onclick=True):
            onclick = btn['onclick']
            match = re.search(r"writeText\('([^']+)'", onclick)
            if match:
                url = match.group(1)

                if md5_prefix not in url:
                    continue

                if "~" in url:
                    base = url.split("~")[0]
                    self.logger.debug(f"Found clipboard URL (normalized): {base}")
                    return base

                self.logger.debug(f"Found clipboard URL: {url}")
                return url
            
        # Method 4: spans containing raw URLs
        for span in soup.find_all('span'):
            text = span.get_text(strip=True)

            if not text.startswith("http"):
                continue
            if md5_prefix not in text:
                continue

            if "~" in text:
                base = text.split("~")[0]
                self.logger.debug(f"Found raw URL in span (normalized): {base}")
                return base

            self.logger.debug(f"Found raw URL in span: {text}")
            return text


        return None
    
    def get_all_download_urls(self, md5, solve_ddos=True, max_urls=10):
        """Get ALL possible direct download URLs for aria2 multi-source."""
        title, links = self.get_download_links(md5)
        download_urls = []
        
        self.logger.info(f"Collecting download URLs from {len(links)} mirrors...")
        
        for i, link in enumerate(links):
            if max_urls > 0 and len(download_urls) >= max_urls:
                self.logger.info(f"Collected maximum {max_urls} URLs, stopping")
                break
            
            try:
                if link['type'] == 'slow_download':
                    # Slow downloads REQUIRE FlareSolverr
                    if not self.flaresolverr_url:
                        self.logger.debug(f"Skipping slow_download {i+1} (no FlareSolverr)")
                        continue
                    
                    self.logger.debug(f"Resolving slow_download {i+1}/{len(links)} with FlareSolverr")
                    
                    success, cookies, html_content = self.solve_with_flaresolverr(link['url'])
                    if not success:
                        continue
                    
                    download_link = self.parse_download_link_from_html(html_content, md5)
                    if download_link:
                        download_urls.append(download_link)
                        self.logger.debug(f"Resolved: {download_link}")
                
                elif link['type'] == 'external_mirror':
                    self.logger.debug(f"Resolving external mirror {i+1}/{len(links)}")
                    
                    try:
                        response = self.session.get(link['url'], timeout=30)
                        
                        # If 403, try with FlareSolverr
                        if response.status_code == 403 and self.flaresolverr_url:
                            self.logger.debug(f"Mirror {i+1} returned 403, trying FlareSolverr")
                            success, cookies, html_content = self.solve_with_flaresolverr(link['url'])
                            if success:
                                download_link = self.parse_download_link_from_html(html_content, md5)
                                if download_link:
                                    download_urls.append(download_link)
                                    self.logger.debug(f"Resolved with FlareSolverr: {download_link}")
                            continue
                        
                        download_link = self.parse_download_link_from_html(response.text, md5)
                        if download_link:
                            download_urls.append(download_link)
                            self.logger.debug(f"Resolved: {download_link}")
                    
                    except Exception as e:
                        self.logger.debug(f"External mirror {i+1} error: {e}")
                        continue
            
            except Exception as e:
                self.logger.debug(f"Could not resolve mirror {i+1}: {e}")
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
        
        self.logger.info(f"✓ Collected {len(unique_urls)} unique download URLs (shuffled)")
        return unique_urls
    
    def download_with_aria2(self, download_urls, title=None, resume_attempts=3):
        """Download file using aria2c with multiple sources."""
        if not self.has_aria2 or not download_urls:
            return None
        
        self.logger.info(f"Starting aria2 multi-source download from {len(download_urls)} sources")
        
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
            base_final_path = self.output_dir / filename
            final_path = self.get_unique_filename(base_final_path)
            
            # Create aria2 input file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                input_file = f.name
                for url in download_urls:
                    f.write(url + '\n')
            
            try:
                cmd = [
                    'aria2c',
                    '--input-file', input_file,
                    '--dir', str(self.incomplete_dir),
                    '--out', final_path.name,
                    '--max-connection-per-server', '4',
                    '--min-split-size', self.aria2_chunk_size,
                    '--split', str(min(len(download_urls), 16)),
                    '--continue=true',
                    '--max-tries', str(resume_attempts),
                    '--retry-wait', '3',
                    '--user-agent', self.session.headers['User-Agent'],
                    '--allow-overwrite=true',
                    '--auto-file-renaming=false',
                ]
                
                self.logger.debug(f"aria2c command: {' '.join(cmd)}")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        self.logger.debug(f"aria2: {line}")
                        
                        if self.progress_callback and '%' in line:
                            try:
                                match = re.search(r'(\d+)%', line)
                                if match:
                                    percent = int(match.group(1))
                                    self.progress_callback({
                                        'percent': percent,
                                        'downloaded': 0,
                                        'total_size': 0
                                    })
                            except Exception:
                                pass
                
                process.wait()
                
                downloaded_file = self.incomplete_dir / final_path.name
                if downloaded_file.exists():
                    # Check if file is suspiciously small (expired download page)
                    if downloaded_file.stat().st_size < 1024:
                        self.logger.warning("Downloaded file < 1KB - likely expired download page")
                        downloaded_file.unlink()
                        return None
                    
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(downloaded_file), str(final_path))
                    self.logger.info(f"✓ Downloaded: {final_path.name}")
                    return final_path
                else:
                    self.logger.error("aria2 completed but file not found")
                    return None
                    
            finally:
                try:
                    Path(input_file).unlink()
                except Exception:
                    pass
        
        except Exception as e:
            self.logger.error(f"aria2 download failed: {e}")
            return None
    
    def try_fast_download(self, md5):
        """Attempt fast download via membership API."""
        if not self.fast_download_enabled or not self.fast_download_key:
            return False, "Fast download not configured"
        
        if self.fast_download_info.get('downloads_left') is not None:
            if self.fast_download_info['downloads_left'] <= 0:
                return False, "No fast downloads remaining"
        
        self.logger.info("Attempting fast download...")
        
        try:
            params = {
                'md5': md5,
                'key': self.fast_download_key,
                'path_index': self.fast_download_config.get('path_index', 0),
                'domain_index': self.fast_download_config.get('domain_index', 0)
            }
            
            response = self.session.get(self.fast_download_api_url, params=params, timeout=10)
            data = response.json()
            
            if 'download_url' in data and data['download_url']:
                if 'account_fast_download_info' in data:
                    info = data['account_fast_download_info']
                    self.fast_download_info.update({
                        'available': True,
                        'downloads_left': info.get('downloads_left'),
                        'downloads_per_day': info.get('downloads_per_day'),
                        'recently_downloaded_md5s': info.get('recently_downloaded_md5s', []),
                        'last_refresh': time.time()
                    })
                    self.logger.info(f"Fast downloads: {info.get('downloads_left')}/{info.get('downloads_per_day')} remaining")
                
                return True, data['download_url']
            
            error_message = data.get('error', 'Unknown error')
            return False, error_message
            
        except Exception as e:
            self.logger.error(f"Fast download API error: {e}")
            return False, f"API error: {e}"
    
    def download_direct(self, download_url, title=None, total_size=None, supports_resume=True, resume_attempts=3):
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
            base_final_path = self.output_dir / filename
            final_path = self.get_unique_filename(base_final_path)
            temp_path = self.incomplete_dir / f"{final_path.name}.part"
            
            # Check for partial download
            downloaded = 0
            if temp_path.exists() and supports_resume:
                downloaded = temp_path.stat().st_size
                self.logger.info(f"Found partial file: {downloaded}/{total_size if total_size else '?'} bytes")
            
            # Download with resume
            for attempt in range(resume_attempts):
                try:
                    headers = {}
                    if downloaded > 0 and supports_resume:
                        headers['Range'] = f'bytes={downloaded}-'
                        self.logger.info(f"Resuming from byte {downloaded}")
                    
                    response = self.session.get(download_url, headers=headers, stream=True, timeout=30)
                    
                    if downloaded > 0 and response.status_code not in [200, 206]:
                        self.logger.warning(f"Resume not supported (status {response.status_code}), starting fresh")
                        downloaded = 0
                        temp_path.unlink(missing_ok=True)
                        response = self.session.get(download_url, stream=True, timeout=30)
                    
                    # Check for HTML content
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'text/html' in content_type:
                        first_chunk = next(response.iter_content(chunk_size=1024), None)
                        if first_chunk and (b'<html' in first_chunk.lower() or b'<!doctype' in first_chunk.lower()):
                            self.logger.warning("Downloaded content appears to be HTML, aborting")
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
                                
                                if self.progress_callback and total_size:
                                    percent = (downloaded / total_size) * 100
                                    self.progress_callback({
                                        'total_size': total_size,
                                        'downloaded': downloaded,
                                        'percent': round(percent, 1)
                                    })
                    
                    # Verify complete
                    if total_size and downloaded < total_size:
                        raise Exception(f"Incomplete download: {downloaded}/{total_size} bytes")
                    
                    # Check if file is suspiciously small (expired download page)
                    if temp_path.stat().st_size < 1024:
                        self.logger.warning("Downloaded file < 1KB - likely expired download page")
                        temp_path.unlink()
                        return None
                    
                    # Move to final location
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(temp_path), str(final_path))
                    
                    self.logger.info(f"✓ Downloaded: {final_path.name}")
                    return final_path
                    
                except requests.exceptions.ChunkedEncodingError:
                    if attempt < resume_attempts - 1 and supports_resume:
                        self.logger.warning(f"Connection interrupted, resuming (attempt {attempt + 1}/{resume_attempts})")
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        return None
                        
                except Exception as e:
                    self.logger.error(f"Download error: {e}")
                    if attempt < resume_attempts - 1 and supports_resume:
                        time.sleep(2 ** attempt)
                        continue
                    return None
            
            return None
            
        except Exception as e:
            self.logger.error(f"Fatal download error: {e}")
            return None
    
    def get_download_links(self, md5):
        """Get download links from Anna's Archive."""
        url = f"https://annas-archive.org/md5/{md5}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = "Unknown"
            title_tag = soup.find('h1')
            if title_tag:
                title = title_tag.get_text().strip()
            
            links = []
            
            # Find the downloads panel
            downloads_panel = soup.find('div', id='md5-panel-downloads')
            if not downloads_panel:
                self.logger.warning("Could not find downloads panel on page")
                return title, links
            
            # Slow_download links - only accept "no waitlist" ones
            for li in downloads_panel.find_all('li', class_='list-disc'):
                a = li.find('a', href=True)
                if not a:
                    continue
                
                href = a['href']
                li_text = li.get_text().strip()
                
                # Skip fast_download links (we handle those via API)
                if '/fast_download/' in href:
                    continue
                
                # Only accept slow_download links
                if '/slow_download/' in href:
                    # Skip waitlist servers (they have 60-second JavaScript countdown)
                    if 'slightly faster but with waitlist' in li_text.lower():
                        self.logger.debug(f"Skipping waitlist server: {a.get_text().strip()}")
                        continue
                    
                    # Accept no-waitlist servers
                    if 'no waitlist' in li_text.lower():
                        full_url = urljoin(url, href)
                        server_name = a.get_text().strip() or "Slow Partner Server"
                        
                        links.append({
                            'url': full_url,
                            'domain': 'annas-archive.org',
                            'text': server_name,
                            'type': 'slow_download'
                        })
                        self.logger.debug(f"Added no-waitlist server: {server_name}")
            
            # External mirrors - look in js-show-external ul
            external_ul = downloads_panel.find('ul', class_='js-show-external')
            if external_ul:
                for a in external_ul.find_all('a', href=True):
                    href = a['href']
                    
                    # Only add absolute URLs
                    if not href.startswith('http'):
                        continue
                    
                    parsed = urlparse(href)
                    domain = parsed.netloc
                    
                    # Skip if no valid domain
                    if not domain:
                        continue
                    
                    links.append({
                        'url': href,
                        'domain': domain,
                        'text': domain,
                        'type': 'external_mirror'
                    })
                    self.logger.debug(f"Added external mirror: {domain}")
            
            return title, links
            
        except Exception as e:
            self.logger.error(f"Error fetching download links: {e}")
            return "Unknown", []
    
    def download_from_mirror(self, mirror_url, mirror_type, md5, title=None, resume_attempts=3):
        """
        Download from any mirror with stale cookie handling.
        
        Logic:
        - slow_download: ALWAYS use FlareSolverr (skip if not configured)
        - external_mirror: Try direct, use FlareSolverr on 403 (with cookie refresh)
        """
        try:
            if mirror_type == 'slow_download':
                # REQUIRE FlareSolverr for slow downloads
                if not self.flaresolverr_url:
                    self.logger.warning("Skipping slow_download - FlareSolverr not configured")
                    return None
                
                self.logger.debug(f"Accessing slow download (via FlareSolverr)")
                
                success, cookies, html_content = self.solve_with_flaresolverr(mirror_url)
                if not success:
                    self.logger.error("FlareSolverr failed")
                    return None
                
                download_link = self.parse_download_link_from_html(html_content, md5)
                if not download_link:
                    self.logger.warning("Could not find download link")
                    return None
                
                self.logger.info(f"Found download URL, downloading...")
                return self.download_direct(download_link, title=title, resume_attempts=resume_attempts)
            
            else:  # external_mirror
                self.logger.debug(f"Accessing external mirror: {mirror_url}")
                
                try:
                    response = self.session.get(mirror_url, timeout=30)
                    
                    # If 403, refresh cookies and retry
                    if response.status_code == 403:
                        if self.flaresolverr_url:
                            self.logger.warning("Got 403 - refreshing cookies with FlareSolverr...")
                            # Pre-warm new cookies
                            if self.prewarm_cookies():
                                # Retry once with fresh cookies
                                response = self.session.get(mirror_url, timeout=30)
                                
                                if response.status_code == 403:
                                    self.logger.warning("Still got 403 after cookie refresh, using FlareSolverr for full solve")
                                    success, cookies, html_content = self.solve_with_flaresolverr(mirror_url)
                                    if success:
                                        download_link = self.parse_download_link_from_html(html_content, md5)
                                        if download_link:
                                            self.logger.info(f"Found download URL via FlareSolverr, downloading...")
                                            return self.download_direct(download_link, title=title, resume_attempts=resume_attempts)
                                    return None
                        else:
                            self.logger.warning("Got 403 but FlareSolverr not configured")
                            return None
                    
                    response.raise_for_status()
                    
                    download_link = self.parse_download_link_from_html(response.text, md5)
                    if not download_link:
                        self.logger.warning("Could not find download link")
                        return None
                    
                    return self.download_direct(download_link, title=title, resume_attempts=resume_attempts)
                
                except Exception as e:
                    self.logger.error(f"Error accessing external mirror: {e}")
                    return None
        
        except Exception as e:
            self.logger.error(f"Error downloading from mirror: {e}")
            return None
    
    def download(self, input_string, prefer_mirror=None, resume_attempts=3, title_override=None):
        """Download a file from Anna's Archive."""
        md5 = self.extract_md5(input_string)
        if not md5:
            self.logger.error(f"Could not extract MD5 from: {input_string}")
            return False, False
        
        self.logger.info(f"Downloading: {md5}")
        
        title, links = self.get_download_links(md5)
        
        if title_override:
            title = title_override
        
        # Try fast download first
        if self.fast_download_enabled and self.fast_download_key:
            success, result = self.try_fast_download(md5)
            
            if success:
                self.logger.info("Using fast download")
                filepath = self.download_direct(result, title=title, resume_attempts=resume_attempts)
                if filepath:
                    self.logger.info("✓ Fast download successful")
                    return True, True
                else:
                    self.logger.warning("Fast download failed, falling back to mirrors")
            else:
                self.logger.info(f"Fast download not available: {result}")
        
        # Try aria2 multi-source if enabled
        if self.enable_aria2 and len(links) > 1:
            self.logger.info("Collecting all download URLs for multi-source...")
            all_urls = self.get_all_download_urls(md5, solve_ddos=True, max_urls=10)
            
            if len(all_urls) >= 2:
                filepath = self.download_with_aria2(all_urls, title=title, resume_attempts=resume_attempts)
                if filepath:
                    self.logger.info("✓ aria2 multi-source download successful")
                    return True, False
                else:
                    self.logger.warning("aria2 failed, falling back to single-source")
        
        # Single-source fallback
        if not links:
            self.logger.error("No download links found")
            return False, False
        
        self.logger.info(f"Found {len(links)} mirror(s)")
        
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
            self.logger.info(f"Trying mirror {i+1}/{len(links)}: {mirror_name}")
            
            filepath = self.download_from_mirror(
                mirror_link['url'],
                mirror_link['type'],
                md5,
                title=title,
                resume_attempts=resume_attempts
            )
            
            if filepath:
                self.logger.info("✓ Download successful")
                return True, False
            else:
                self.logger.warning(f"Mirror {mirror_name} failed")
                if i < len(links) - 1:
                    self.logger.info("Trying next mirror...")
        
        self.logger.error("All mirrors failed")
        return False, False
    
    def get_fast_download_info(self):
        """Get current fast download status."""
        return self.fast_download_info.copy()
    
    def refresh_fast_download_info(self, force=False):
        """Refresh fast download info from API (respects 1-hour cooldown)."""
        if not self.fast_download_enabled or not self.fast_download_key:
            return False
        
        if not force:
            time_since_refresh = time.time() - self.fast_download_info.get('last_refresh', 0)
            if time_since_refresh < self.fast_download_refresh_cooldown:
                return True
        
        try:
            test_md5 = 'd6e1dc51a50726f00ec438af21952a45'
            params = {
                'md5': test_md5,
                'key': self.fast_download_key,
                'path_index': 0,
                'domain_index': 0
            }
            
            response = self.session.get(self.fast_download_api_url, params=params, timeout=10)
            data = response.json()
            
            if 'account_fast_download_info' in data:
                info = data['account_fast_download_info']
                self.fast_download_info.update({
                    'available': True,
                    'downloads_left': info.get('downloads_left'),
                    'downloads_per_day': info.get('downloads_per_day'),
                    'recently_downloaded_md5s': info.get('recently_downloaded_md5s', []),
                    'last_refresh': time.time()
                })
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to refresh fast download info: {e}")
            return False