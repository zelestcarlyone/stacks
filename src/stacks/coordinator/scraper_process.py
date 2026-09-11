"""
Scraper worker process.

The scraper fetches metadata and mirror lists for downloads that are in
'pending_scrape' status. It populates the mirrors list so download workers
can claim jobs.
"""

import logging
import signal
import sys
from multiprocessing import Event
from pathlib import Path
from urllib.parse import urlparse

from stacks.config.config import Config
from stacks.constants import DOWNLOAD_PATH, PROJECT_ROOT
from stacks.coordinator.queue_ops import QueueOperations

logger = logging.getLogger(__name__)


def scraper_process(config_path: Path, stop_event: Event) -> None:
    """
    Scraper process entry point.

    This process fetches download metadata (filename, mirror list) for items
    that are in 'pending_scrape' status.

    Args:
        config_path: Path to the config file
        stop_event: Event to signal the scraper to stop
    """
    worker_id = "scraper-1"

    # Setup logging - write to stdout AND the shared log file so /api/logs shows worker output
    from stacks.utils.logutils import get_log_file_path, LOG_FORMAT, LOG_DATE_FORMAT
    _log_file = get_log_file_path()
    _log_file.parent.mkdir(parents=True, exist_ok=True)
    _formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
    _root = logging.getLogger()
    _root.setLevel(logging.INFO)
    for _h in _root.handlers[:]:
        _root.removeHandler(_h)
        _h.close()
    _ch = logging.StreamHandler(sys.stdout)
    _ch.setFormatter(_formatter)
    _root.addHandler(_ch)
    _fh = logging.FileHandler(_log_file, encoding='utf-8')
    _fh.setFormatter(_formatter)
    _root.addHandler(_fh)
    scraper_logger = logging.getLogger(f'worker.{worker_id}')
    scraper_logger.info("Scraper process starting")

    # Handle signals gracefully
    def signal_handler(signum, frame):
        scraper_logger.info(f"Scraper received signal {signum}, stopping")
        stop_event.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Initialize
    queue_ops = QueueOperations()
    config = Config(config_path)
    downloader = None

    # Main scraper loop
    while not stop_event.is_set():
        try:
            # Send heartbeat
            queue_ops.heartbeat(worker_id, 'scraper')

            # Try to claim a scrape job
            job = queue_ops.claim_scrape_job(worker_id)

            if not job:
                # No jobs available, wait and retry
                stop_event.wait(timeout=2)
                continue

            md5 = job['md5']
            scraper_logger.info(f"Fetching metadata for: {md5}")

            # Initialize downloader lazily
            if downloader is None:
                scraper_logger.info("Initializing downloader for scraping")
                config.load()

                from stacks.downloader.downloader import AnnaDownloader

                # Get FlareSolverr config (needed for some mirrors)
                flaresolverr_enabled = config.get('flaresolverr', 'enabled', default=False)
                flaresolverr_url = config.get('flaresolverr', 'url', default='http://localhost:8191')
                flaresolverr_timeout = config.get('flaresolverr', 'timeout', default=60)
                flaresolverr_timeout_ms = flaresolverr_timeout * 1000

                # Get incomplete folder path
                incomplete_folder_path = config.get('downloads', 'incomplete_folder_path', default='/download/incomplete')
                incomplete_dir = PROJECT_ROOT / incomplete_folder_path.lstrip('/')

                # Get fast download (membership) config — needed so the scraper can
                # use the fast-download JSON API, which is not behind DDoS-Guard
                # and therefore works from datacenter/VPS IPs.
                fast_config = {
                    'enabled': config.get('fast_download', 'enabled', default=False),
                    'key': config.get('fast_download', 'key'),
                    'path_index': 0,
                    'domain_index': 0
                }

                # Get proxy config
                proxy_config = {
                    'enabled': config.get('proxy', 'enabled', default=False),
                    'url': config.get('proxy', 'url'),
                    'username': config.get('proxy', 'username'),
                    'password': config.get('proxy', 'password')
                }

                downloader = AnnaDownloader(
                    output_dir=DOWNLOAD_PATH,
                    incomplete_dir=incomplete_dir,
                    fast_download_config=fast_config,
                    flaresolverr_url=flaresolverr_url if flaresolverr_enabled else None,
                    flaresolverr_timeout=flaresolverr_timeout_ms,
                    proxy_config=proxy_config
                )

            # Fetch download links
            filename = None
            mirrors = []
            error = None

            try:
                filename, links = downloader.get_download_links(md5)

                if links:
                    # Convert links to mirror format with domain extracted
                    for link in links:
                        domain = _extract_domain(link.get('url', ''))
                        mirrors.append({
                            'url': link['url'],
                            'type': link.get('type', 'external_mirror'),
                            'domain': domain or link.get('domain', ''),
                            'text': link.get('text', '')
                        })
                    scraper_logger.info(f"Found {len(mirrors)} mirrors for {md5}")
                else:
                    error = "No mirrors found"
                    scraper_logger.warning(f"No mirrors found for {md5}")

            except Exception as e:
                error = str(e)
                scraper_logger.error(f"Failed to fetch metadata for {md5}: {e}")

            # Check if we should stop
            if stop_event.is_set():
                scraper_logger.info(f"Scraper stopping, leaving job {md5} for cleanup")
                break

            # Report scrape completion
            queue_ops.complete_scrape(md5, filename, mirrors, error)

        except Exception as e:
            scraper_logger.error(f"Scraper loop error: {e}", exc_info=True)
            # Wait before retrying to avoid tight error loops
            stop_event.wait(timeout=5)

    # Cleanup
    scraper_logger.info("Scraper process stopping")
    queue_ops.remove_worker_heartbeat(worker_id)

    if downloader:
        try:
            downloader.cleanup()
        except Exception as e:
            scraper_logger.error(f"Error cleaning up downloader: {e}")

    scraper_logger.info("Scraper process stopped")


def _extract_domain(url: str) -> str:
    """Extract domain from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc or ''
    except Exception:
        return ''
