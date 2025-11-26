"""Z-Library (z-lib.fm) specific scraper."""

from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


def parse_zlib_download_link(d, html_content, mirror_url):
    """
    Parse z-lib.fm HTML to extract download link.

    Z-lib structure:
    - Main download button: <a class="btn btn-default addDownloadedBook" href="/dl/{book_id}/{code}">
    - Alternative formats in dropdown: <a onclick="..." data-book_id="{id}">
    - Multiple language domains (z-lib.fm, ru.z-lib.fm, de.z-lib.fm, etc.)

    Args:
        d: Downloader instance
        html_content: HTML content from z-lib page
        mirror_url: The original mirror URL

    Returns:
        Download URL or None
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    parsed_url = urlparse(mirror_url)
    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

    # Method 1: Look for main download button with addDownloadedBook class
    main_download = soup.find('a', class_='addDownloadedBook', href=True)
    if main_download:
        href = main_download['href']
        if href.startswith('/dl/'):
            download_url = urljoin(base_domain, href)
            d.logger.debug(f"Found z-lib main download button: {download_url}")
            return download_url

    # Method 2: Look for download links in dropdown (alternative formats)
    # These have onclick handlers but also contain data-book_id
    dropdown_links = soup.find_all('a', class_='addDownloadedBook')
    for link in dropdown_links:
        book_id = link.get('data-book_id')
        if book_id:
            # Try to extract the download code from the main button if available
            # Format: /dl/{book_id}/{code}
            if main_download and main_download.get('href'):
                main_href = main_download['href']
                if '/dl/' in main_href:
                    # Extract code from main download link
                    parts = main_href.split('/')
                    if len(parts) >= 3:
                        code = parts[-1]
                        # Construct download URL for alternative format
                        download_url = f"{base_domain}/dl/{book_id}/{code}"
                        d.logger.debug(f"Found z-lib alternative format: {download_url}")
                        return download_url

    # Method 3: Try to extract from any /dl/ link in the page
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/dl/' in href and href.startswith('/'):
            download_url = urljoin(base_domain, href)
            d.logger.debug(f"Found z-lib download via /dl/ link: {download_url}")
            return download_url

    d.logger.warning("Could not find z-lib download link in HTML")
    return None


def is_zlib_domain(url):
    """Check if URL is a z-lib domain."""
    zlib_domains = [
        'z-lib.fm',
        'z-lib.org',
        'z-lib.is',
        'singlelogin.re',
        'singlelogin.se',
    ]

    parsed = urlparse(url.lower())
    domain = parsed.netloc

    # Check for main domains and language subdomains (ru.z-lib.fm, de.z-lib.fm, etc.)
    for zlib_domain in zlib_domains:
        if domain == zlib_domain or domain.endswith(f'.{zlib_domain}'):
            return True

    return False
