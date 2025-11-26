"""Site-specific scrapers for different mirror sites."""

from .zlib import parse_zlib_download_link

__all__ = ['parse_zlib_download_link']
