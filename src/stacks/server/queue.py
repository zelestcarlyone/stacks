import threading
from pathlib import Path
import json
import logging
from datetime import datetime
from stacks.constants import QUEUE_FILE

class DownloadQueue:
    def __init__(self, config):
        self.config = config
        self.storage_file = Path(QUEUE_FILE)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.queue = []
        self.current_download = None
        self.history = []
        self.lock = threading.Lock()
        self.logger = logging.getLogger('queue')
        self.load()
    
    def load(self):
        """Load queue from disk"""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    self.queue = data.get('queue', [])
                    self.history = data.get('history', [])
                self.logger.info(f"Loaded queue: {len(self.queue)} items, {len(self.history)} history")
            except Exception as e:
                self.logger.error(f"Failed to load queue: {e}")
    
    def save(self):
        """Save queue to disk"""
        try:
            max_history = self.config.get('queue', 'max_history', default=100)
            history_to_save = self.history if max_history == 0 else self.history[-max_history:]
            
            with open(self.storage_file, 'w') as f:
                json.dump({
                    'queue': self.queue,
                    'history': history_to_save
                }, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save queue: {e}")
    
    def add(self, md5, title=None, source=None):
        """Add item to queue"""
        with self.lock:
            # Check if in queue
            if any(item['md5'] == md5 for item in self.queue):
                return False, "Already in queue"
            
            # Check if currently downloading
            if self.current_download and self.current_download['md5'] == md5:
                return False, "Currently downloading"
            
            # Check if recently SUCCESSFULLY downloaded (allow retry of failures)
            if any(item['md5'] == md5 and item.get('success', False) for item in self.history[-50:]):
                return False, "Recently downloaded"
            
            item = {
                'md5': md5,
                'title': title or 'Unknown',
                'source': source,
                'added_at': datetime.now().isoformat(),
                'status': 'queued'
            }
            
            self.queue.append(item)
            self.save()
            self.logger.info(f"Added to queue: {title} ({md5})")
            return True, "Added to queue"
    
    def get_next(self):
        """Get next item from queue"""
        with self.lock:
            if self.queue:
                return self.queue.pop(0)
            return None
    
    def mark_complete(self, md5, success, filepath=None, error=None, used_fast_download=False):
        """Mark download as complete"""
        with self.lock:
            item = {
                'md5': md5,
                'title': self.current_download.get('title', 'Unknown') if self.current_download else 'Unknown',
                'completed_at': datetime.now().isoformat(),
                'success': success,
                'filepath': str(filepath) if filepath else None,
                'error': error,
                'used_fast_download': used_fast_download
            }
            self.history.append(item)
            self.current_download = None
            self.save()
            
            if success:
                method = "fast download" if used_fast_download else "mirror"
                self.logger.info(f"Download complete ({method}): {item['title']}")
            else:
                self.logger.warning(f"Download failed: {item['title']} - {error}")
    
    def get_status(self):
        """Get current queue status"""
        with self.lock:
            return {
                'current': self.current_download,
                'queue': self.queue.copy(),
                'queue_size': len(self.queue),
                'recent_history': self.history[-10:][::-1]
            }
    
    def remove_from_queue(self, md5):
        """Remove item from queue"""
        with self.lock:
            original_length = len(self.queue)
            self.queue = [item for item in self.queue if item['md5'] != md5]
            removed = original_length != len(self.queue)
            if removed:
                self.save()
                self.logger.info(f"Removed from queue: {md5}")
            return removed
    
    def clear_queue(self):
        """Clear all items from queue"""
        with self.lock:
            count = len(self.queue)
            self.queue = []
            self.save()
            self.logger.info(f"Cleared queue: {count} items removed")
            return count
    
    def clear_history(self):
        """Clear all items from history"""
        with self.lock:
            count = len(self.history)
            self.history = []
            self.save()
            self.logger.info(f"Cleared history: {count} items removed")
            return count
    
    def retry_failed(self, md5):
        """Retry a failed download by removing from history and re-adding to queue"""
        with self.lock:
            # Find the failed item in history
            failed_item = None
            for item in self.history:
                if item['md5'] == md5 and not item.get('success', False):
                    failed_item = item
                    break
            
            if not failed_item:
                return False, "Item not found in failed history"
            
            # Remove from history
            self.history = [item for item in self.history if item['md5'] != md5]
            
            # Add back to queue
            new_item = {
                'md5': md5,
                'title': failed_item.get('title', 'Unknown'),
                'source': 'retry',
                'added_at': datetime.now().isoformat(),
                'status': 'queued'
            }
            
            self.queue.append(new_item)
            self.save()
            self.logger.info(f"Retrying failed download: {failed_item.get('title')} ({md5})")
            return True, "Added to queue for retry"