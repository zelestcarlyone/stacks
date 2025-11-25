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

        # Status callback to update current download status
        def status_callback(status_message):
            if self.queue.current_download:
                with self.queue.lock:
                    self.queue.current_download.update({
                        'status_message': status_message
                    })

        # Initialize downloader
        self.progress_callback = progress_callback
        self.status_callback = status_callback
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
            status_callback=self.status_callback,
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
        if flaresolverr_enabled and flaresolverr_url:
            # Normalize URL for testing (same as downloader does)
            test_url = flaresolverr_url
            if not test_url.startswith(('http://', 'https://')):
                test_url = f"http://{test_url}"

            self.logger.info(f"Testing FlareSolverr connection at {test_url}...")
            try:
                import requests
                response = requests.get(test_url, timeout=5)
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
        """Stop worker thread and cancel any active downloads"""
        self.logger.info("Stopping download worker...")
        self.running = False

        # Mark current download as interrupted if one is active
        if self.queue.current_download:
            with self.queue.lock:
                item = self.queue.current_download
                self.logger.warning(f"Cancelling active download: {item.get('title', 'Unknown')}")
                # Put it back in the queue so it can be resumed later
                self.queue.queue.insert(0, {
                    'md5': item['md5'],
                    'title': item.get('title', 'Unknown'),
                    'source': item.get('source'),
                    'added_at': item.get('added_at'),
                    'status': 'queued'
                })
                self.queue.current_download = None
                self.queue.save()

        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                self.logger.warning("Worker thread did not stop gracefully within timeout")
            else:
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
            
            # Fetch download info FIRST (before setting current_download)
            self.logger.info(f"Fetching download info: {item['md5']}")
            try:
                filename, links = self.downloader.get_download_links(item['md5'])
            except Exception as e:
                self.logger.error(f"Failed to fetch download info: {e}")
                self.queue.mark_complete(item['md5'], False, error=f"Failed to fetch download info: {e}")
                continue

            # Set as current download with ALL information
            with self.queue.lock:
                self.queue.current_download = item
                self.queue.current_download['status'] = 'downloading'
                self.queue.current_download['started_at'] = datetime.now().isoformat()
                self.queue.current_download['filename'] = filename
                self.queue.current_download['status_message'] = f"Found {len(links)} mirror(s)"
                self.queue.current_download['progress'] = {
                    'total_size': 0,
                    'downloaded': 0,
                    'percent': 0
                }

            self.logger.info(f"Starting download: {filename} ({item['md5']})")

            try:
                # Pass pre-fetched filename and links to avoid duplicate API calls
                success, used_fast_download, filepath = self.downloader.download(
                    item['md5'],
                    resume_attempts=resume_attempts,
                    filename=filename,
                    links=links
                )

                if success:
                    self.queue.mark_complete(item['md5'], True, filepath=filepath, used_fast_download=used_fast_download, filename=filename)
                else:
                    self.queue.mark_complete(item['md5'], False, error="Download failed", filename=filename)

            except Exception as e:
                self.logger.error(f"Download error: {item['md5']} - {e}")
                self.queue.mark_complete(item['md5'], False, error=str(e), filename=filename)
            
            # Rate limiting
            if self.queue.queue:
                time.sleep(delay)