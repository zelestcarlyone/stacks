import threading
import logging
import time
from datetime import datetime
from stacks.downloader.downloader import AnnaDownloader
from stacks.constants import FAST_DOWNLOAD_API_URL, DOWNLOAD_PATH, INCOMPLETE_PATH

class DownloadWorker:
    def __init__(self, queue, config):
        self.queue = queue
        self.config = config
        self.running = False
        self.thread = None
        self.logger = logging.getLogger('worker')
        
        # Progress callback to update current download
        def progress_callback(progress):
            if self.queue.current_download:
                with self.queue.lock:
                    self.queue.current_download.update({
                        'progress': progress
                    })
        
        # Initialize downloader
        self.progress_callback = progress_callback
        self.recreate_downloader()
    
    def recreate_downloader(self):
        """Recreate downloader with current config"""
        # Get fast download config from main config
        fast_config = {
            'enabled': self.config.get('fast_download', 'enabled', default=False),
            'key': self.config.get('fast_download', 'key'),
            'api_url': FAST_DOWNLOAD_API_URL,
            'path_index': 0,
            'domain_index': 0
        }
        
        # Get FlareSolverr config
        flaresolverr_enabled = self.config.get('flaresolverr', 'enabled', default=False)
        flaresolverr_url = self.config.get('flaresolverr', 'url', default='http://localhost:8191')
        flaresolverr_timeout = self.config.get('flaresolverr', 'timeout', default=60)
        
        # Convert timeout to milliseconds (downloader expects milliseconds)
        flaresolverr_timeout_ms = flaresolverr_timeout * 1000
        
        # Pass None if FlareSolverr is disabled, otherwise pass the URL
        self.downloader = AnnaDownloader(
            output_dir=DOWNLOAD_PATH,
            incomplete_dir=INCOMPLETE_PATH,
            progress_callback=self.progress_callback,
            fast_download_config=fast_config,
            flaresolverr_url=flaresolverr_url if flaresolverr_enabled else None,
            flaresolverr_timeout=flaresolverr_timeout_ms
        )
        
        # Test fast download key if enabled and key is present
        if fast_config['enabled'] and fast_config['key']:
            self.logger.info("Testing fast download key...")
            try:
                success = self.downloader.refresh_fast_download_info(force=True)
                
                if success:
                    info = self.downloader.get_fast_download_info()
                    self.logger.info(f"Fast download key valid - {info.get('downloads_left')}/{info.get('downloads_per_day')} downloads available")
                else:
                    self.logger.warning("Fast download key test failed")
            except Exception as e:
                self.logger.error(f"Failed to test fast download key: {e}")
        
        # Test FlareSolverr if enabled
        if flaresolverr_enabled:
            self.logger.info(f"Testing FlareSolverr connection at {flaresolverr_url}...")
            try:
                import requests
                response = requests.get(flaresolverr_url, timeout=5)
                if response.status_code == 200:
                    self.logger.info("FlareSolverr connection successful")
                else:
                    self.logger.warning(f"FlareSolverr returned status {response.status_code}")
            except Exception as e:
                self.logger.error(f"Failed to connect to FlareSolverr: {e}")
                self.logger.warning("Downloads will fall back to external mirrors only")
        
        self.logger.info("Downloader recreated with updated config")
    
    def update_config(self):
        """Update downloader with new config (called when config changes)"""
        self.recreate_downloader()
    
    def start(self):
        """Start worker thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.thread.start()
            self.logger.info("Download worker started")
    
    def stop(self):
        """Stop worker thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.logger.info("Download worker stopped")
    
    def get_fast_download_info(self):
        """Get current fast download status"""
        return self.downloader.get_fast_download_info()
    
    def refresh_fast_download_info_if_stale(self):
        """Refresh fast download info if it's been more than an hour"""
        return self.downloader.refresh_fast_download_info(force=False)
    
    def _worker_loop(self):
        """Main worker loop"""
        delay = self.config.get('downloads', 'delay', default=2)
        resume_attempts = self.config.get('downloads', 'resume_attempts', default=3)
        
        while self.running:
            item = self.queue.get_next()
            
            if item is None:
                time.sleep(1)
                continue
            
            # Set as current download
            with self.queue.lock:
                self.queue.current_download = item
                self.queue.current_download['status'] = 'downloading'
                self.queue.current_download['started_at'] = datetime.now().isoformat()
                self.queue.current_download['progress'] = {
                    'total_size': 0,
                    'downloaded': 0,
                    'percent': 0
                }
            
            self.logger.info(f"Starting download: {item['title']} ({item['md5']})")
            
            try:
                success, used_fast_download = self.downloader.download(
                    item['md5'], 
                    resume_attempts=resume_attempts,
                    title_override=item.get('title')
                )
                
                if success:
                    self.queue.mark_complete(item['md5'], True, used_fast_download=used_fast_download)
                else:
                    self.queue.mark_complete(item['md5'], False, error="Download failed")
                
            except Exception as e:
                self.logger.error(f"Download error: {item['title']} - {e}")
                self.queue.mark_complete(item['md5'], False, error=str(e))
            
            # Rate limiting
            if self.queue.queue:
                time.sleep(delay)