import threading
import logging
import time
from datetime import datetime
from pathlib import Path
from stacks.downloader.downloader import AnnaDownloader
from stacks.constants import DOWNLOAD_PATH, PROJECT_ROOT

class DownloadWorker:
    def __init__(self, queue, config):
        self.queue = queue
        self.config = config
        self.running = False
        self.paused = False
        self.cancel_current = False
        self.thread = None
        self.logger = logging.getLogger('worker')
        
        # Progress callback to update current download
        def progress_callback(progress):
            # Check if download should be cancelled
            if self.cancel_current:
                return False  # Signal to downloader to cancel

            # Handle check_only requests (for orchestrator)
            if isinstance(progress, dict) and progress.get('check_only'):
                return True  # Continue if not cancelled

            if self.queue.current_download:
                with self.queue.lock:
                    self.queue.current_download.update({
                        'progress': progress
                    })
            return True  # Continue download

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
        # Cleanup old downloader if it exists
        if hasattr(self, 'downloader') and self.downloader:
            self.downloader.cleanup()

        # Get fast download config from main config
        fast_config = {
            'enabled': self.config.get('fast_download', 'enabled', default=False),
            'key': self.config.get('fast_download', 'key'),
            'path_index': 0,
            'domain_index': 0
        }
        
        # Get FlareSolverr config
        flaresolverr_enabled = self.config.get('flaresolverr', 'enabled', default=False)
        flaresolverr_url = self.config.get('flaresolverr', 'url', default='http://localhost:8191')
        flaresolverr_timeout = self.config.get('flaresolverr', 'timeout', default=60)
        
        # Convert timeout to milliseconds (downloader expects milliseconds)
        flaresolverr_timeout_ms = flaresolverr_timeout * 1000
        
        # Get file naming config
        prefer_title_naming = self.config.get('downloads', 'prefer_title_naming', default=False)
        include_hash = self.config.get('downloads', 'include_hash', default="none")

        # Get incomplete folder path from config
        incomplete_folder_path = self.config.get('downloads', 'incomplete_folder_path', default='/download/incomplete')
        incomplete_dir = PROJECT_ROOT / incomplete_folder_path.lstrip('/')

        # Pass None if FlareSolverr is disabled, otherwise pass the URL
        self.downloader = AnnaDownloader(
            output_dir=DOWNLOAD_PATH,
            incomplete_dir=incomplete_dir,
            progress_callback=self.progress_callback,
            status_callback=self.status_callback,
            fast_download_config=fast_config,
            flaresolverr_url=flaresolverr_url if flaresolverr_enabled else None,
            flaresolverr_timeout=flaresolverr_timeout_ms,
            prefer_title_naming=prefer_title_naming,
            include_hash=include_hash
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
                    'status': 'queued',
                    'subfolder': item.get('subfolder')
                })
                self.queue.current_download = None
                self.queue.save()

        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                self.logger.warning("Worker thread did not stop gracefully within timeout")
            else:
                self.logger.info("Download worker stopped")

    def pause(self):
        """Pause the worker"""
        if not self.paused:
            self.paused = True
            self.logger.info("Download worker paused")
            # Note: Active downloads will be requeued when they complete (see worker loop)

    def resume(self):
        """Resume the worker"""
        if self.paused:
            self.paused = False
            self.logger.info("Download worker resumed")

    def cancel_and_requeue_current(self):
        """Cancel current download and requeue it"""
        if self.queue.current_download:
            self.cancel_current = True
            # Also pause the queue so it doesn't immediately restart
            if not self.paused:
                self.paused = True
                self.logger.info("Pausing queue after pausing download")
            self.logger.info(f"Pausing download and requeueing: {self.queue.current_download.get('filename', 'Unknown')}")
            return True
        return False

    def cancel_and_remove_current(self):
        """Cancel current download and remove it completely"""
        if self.queue.current_download:
            self.cancel_current = True
            # Mark for removal (worker loop will handle it)
            with self.queue.lock:
                self.queue.current_download['_remove'] = True
            # Don't pause when removing - user explicitly wants it gone and queue should continue
            self.logger.info(f"Stopping download and removing: {self.queue.current_download.get('filename', 'Unknown')}")
            return True
        return False

    def wait_for_current_download_to_stop(self, timeout=10):
        """Wait for current download to stop (for migration)"""
        start = time.time()
        while self.queue.current_download and (time.time() - start) < timeout:
            time.sleep(0.1)
        return self.queue.current_download is None

    def _cleanup_partial_file(self, md5):
        """Clean up partial download file in incomplete directory"""
        try:
            incomplete_folder_path = self.config.get('downloads', 'incomplete_folder_path', default='/download/incomplete')
            incomplete_dir = PROJECT_ROOT / incomplete_folder_path.lstrip('/')

            # Look for any files with this MD5 in incomplete directory
            if incomplete_dir.exists():
                for file in incomplete_dir.glob(f"*{md5}*"):
                    try:
                        file.unlink()
                        self.logger.info(f"Cleaned up partial file: {file.name}")
                    except Exception as e:
                        self.logger.warning(f"Failed to remove partial file {file.name}: {e}")
        except Exception as e:
            self.logger.warning(f"Error during partial file cleanup: {e}")

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
            # Check if paused
            if self.paused:
                time.sleep(1)
                continue

            item = self.queue.get_next()

            if item is None:
                time.sleep(1)
                continue
            
            # Set as current download FIRST (before fetching download info)
            # This allows pause to work properly even during the fetch phase
            with self.queue.lock:
                self.queue.current_download = item
                self.queue.current_download['status'] = 'downloading'
                self.queue.current_download['started_at'] = datetime.now().isoformat()

            # Fetch download info
            self.logger.info(f"Fetching download info: {item['md5']}")
            try:
                filename, links = self.downloader.get_download_links(item['md5'])
            except Exception as e:
                self.logger.error(f"Failed to fetch download info: {e}")

                # Check if paused - if so, requeue instead of marking as failed
                if self.paused:
                    self.logger.info(f"Pausing download after fetch failure: {item['md5']}")
                    self.queue.requeue_current()
                    continue

                self.queue.mark_complete(item['md5'], False, error=f"Failed to fetch download info: {e}", subfolder=item.get('subfolder'))
                continue

            # Update current download with fetched information
            with self.queue.lock:
                self.queue.current_download['filename'] = filename
                self.queue.current_download['status_message'] = f"Found {len(links)} mirror(s)"
                self.queue.current_download['progress'] = {
                    'total_size': 0,
                    'downloaded': 0,
                    'percent': 0
                }

            # Check if paused after fetching download info
            if self.paused:
                self.logger.info(f"Pausing download after fetch: {filename}")
                self.queue.requeue_current()
                continue

            # Check if cancelled
            if self.cancel_current:
                should_remove = self.queue.current_download.get('_remove', False)
                if should_remove:
                    self.logger.info(f"Stopping download after fetch: {filename}")
                    self._cleanup_partial_file(item['md5'])
                    self.queue.current_download = None
                    self.queue.save()
                else:
                    self.logger.info(f"Pausing download after fetch: {filename}")
                    self.queue.requeue_current()
                self.cancel_current = False
                continue

            self.logger.info(f"Starting download: {filename} ({item['md5']})")

            try:
                # Pass pre-fetched filename and links to avoid duplicate API calls
                success, used_fast_download, filepath = self.downloader.download(
                    item['md5'],
                    resume_attempts=resume_attempts,
                    filename=filename,
                    links=links,
                    subfolder=item.get('subfolder')
                )

                # Once download completes (success or failure), it's too late to cancel
                # Reset the cancel flag if it was set - cancellation is handled during download via progress_callback
                if self.cancel_current:
                    self.cancel_current = False

                # Check if paused after download completes - if so, requeue instead of marking complete
                if self.paused:
                    self.logger.info(f"Pausing download: {filename}")
                    self.queue.requeue_current()
                    continue

                if success:
                    self.queue.mark_complete(item['md5'], True, filepath=filepath, used_fast_download=used_fast_download, filename=filename, subfolder=item.get('subfolder'))
                else:
                    self.queue.mark_complete(item['md5'], False, error="Download failed", filename=filename, subfolder=item.get('subfolder'))

            except Exception as e:
                self.logger.error(f"Download error: {item['md5']} - {e}")

                # Check if cancelled during exception
                if self.cancel_current:
                    should_remove = self.queue.current_download.get('_remove', False)
                    if should_remove:
                        self.logger.info(f"Stopping download after error: {filename}")
                        self._cleanup_partial_file(item['md5'])
                        self.queue.current_download = None
                        self.queue.save()
                    else:
                        self.logger.info(f"Pausing download after error: {filename}")
                        self.queue.requeue_current()
                    self.cancel_current = False
                    continue

                # Check if paused - if so, requeue instead of marking as failed
                if self.paused:
                    self.logger.info(f"Pausing download after error: {filename}")
                    self.queue.requeue_current()
                    continue

                self.queue.mark_complete(item['md5'], False, error=str(e), filename=filename, subfolder=item.get('subfolder'))
            
            # Rate limiting
            if self.queue.queue:
                time.sleep(delay)