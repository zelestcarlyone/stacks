import logging
import requests
from pathlib import Path
from stacks.utils.md5utils import extract_md5
from stacks.utils.domainutils import get_working_domain
from stacks.downloader.cookies import _load_cached_cookies, _save_cookies_to_cache, _prewarm_cookies
from stacks.downloader.direct import download_direct
from stacks.downloader.fast_download import try_fast_download, get_fast_download_info, refresh_fast_download_info
from stacks.downloader.flaresolver import solve_with_flaresolverr
from stacks.downloader.html import get_download_links, parse_download_link_from_html
from stacks.downloader.mirrors import download_from_mirror
from stacks.downloader.orchestrator import orchestrate_download
from stacks.downloader.utils import get_unique_filename

class AnnaDownloader:
    def __init__(self, output_dir="./downloads", incomplete_dir=None, progress_callback=None,
                 fast_download_config=None, flaresolverr_url=None, flaresolverr_timeout=60000,
                 status_callback=None, prefer_title_naming=False, include_hash="none"):
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
        self.status_callback = status_callback
        
        # Fast download configuration
        self.fast_download_config = fast_download_config or {}
        self.fast_download_enabled = self.fast_download_config.get('enabled', False)
        self.fast_download_key = self.fast_download_config.get('key')
        # Use dynamic domain for API URL (with fallback support)
        default_api_url = f'https://{get_working_domain()}/dyn/api/fast_download.json'
        self.fast_download_api_url = self.fast_download_config.get('api_url', default_api_url)
        
        # Fast download state
        self.fast_download_info = {
            'available': bool(self.fast_download_enabled and self.fast_download_key),
            'downloads_left': None,
            'downloads_per_day': None,
            'last_refresh': 0
        }
        
        self.fast_download_refresh_cooldown = 3600  # 1 hour
        
        # FlareSolverr configuration
        # Normalize URL: add http:// if no scheme is present
        if flaresolverr_url and not flaresolverr_url.startswith(('http://', 'https://')):
            flaresolverr_url = f"http://{flaresolverr_url}"

        self.flaresolverr_url = flaresolverr_url
        self.flaresolverr_timeout = flaresolverr_timeout

        # Filename preference configuration
        self.prefer_title_naming = prefer_title_naming
        self.include_hash = include_hash  # "none", "prefix", or "suffix"

        if flaresolverr_url:
            self.logger.info(f"FlareSolverr enabled: {flaresolverr_url}")
            self.logger.info("Using ALL download sources (Anna's Archive slow_download + external mirrors)")
        else:
            self.logger.info("FlareSolverr not configured - using external mirrors and slow_download with cached cookies")

        # Always try to load cached cookies (useful for slow_download even without FlareSolverr)
        self.load_cached_cookies()
    
    # Cookies
    def load_cached_cookies(self, domain=None):
        return _load_cached_cookies(self, domain)

    def save_cookies_to_cache(self, cookies_dict, domain=None):
        return _save_cookies_to_cache(self, cookies_dict, domain)

    def prewarm_cookies(self):
        return _prewarm_cookies(self)
    
    
    # Direct
    def download_direct(self, download_url, title=None, total_size=None, supports_resume=True, resume_attempts=3, md5=None, subfolder=None):
        return download_direct(self, download_url, title, total_size, supports_resume, resume_attempts, md5, subfolder)
    
    
    # Download orchestrator
    def download(self, input_string, prefer_mirror=None, resume_attempts=3, filename=None, links=None, subfolder=None):
        return orchestrate_download(self, input_string, prefer_mirror, resume_attempts, filename, links, subfolder)
 
 
    # Fast Download
    def try_fast_download(self, md5):
        return try_fast_download(self, md5)

    def get_fast_download_info(self):
        return get_fast_download_info(self)

    def refresh_fast_download_info(self, force=False):
        return refresh_fast_download_info(self, force)
    
    
    # Flare solver
    def solve_with_flaresolverr(self, url):
        return solve_with_flaresolverr(self, url)
    
    
    # HTML
    def parse_download_link_from_html(self, html_content, md5, mirror_url=None):
        return parse_download_link_from_html(self, html_content, md5, mirror_url)

    def get_download_links(self, md5):
        return get_download_links(self, md5)
    
    
    # Mirrors
    def download_from_mirror(self, mirror_url, mirror_type, md5, title=None, resume_attempts=3, subfolder=None):
        return download_from_mirror(self, mirror_url, mirror_type, md5, title, resume_attempts, subfolder)


    # Utils
    def extract_md5(self, input_string):
        return extract_md5(input_string)

    def get_unique_filename(self, base_path):
        return get_unique_filename(self, base_path)

    def cleanup(self):
        """Cleanup resources (close session, etc.)"""
        try:
            if hasattr(self, 'session') and self.session:
                self.logger.info("Closing HTTP session...")
                self.session.close()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")