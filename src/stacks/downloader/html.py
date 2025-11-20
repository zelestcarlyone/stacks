import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

def parse_download_link_from_html(d, html_content, md5):
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
                d.logger.debug(f"Found download link with MD5 prefix: {href}")
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
                    d.logger.debug(f"Found download link via fallback: {href}")
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
                    d.logger.debug(f"Found clipboard URL (normalized): {base}")
                    return base

                d.logger.debug(f"Found clipboard URL: {url}")
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
                d.logger.debug(f"Found raw URL in span (normalized): {base}")
                return base

            d.logger.debug(f"Found raw URL in span: {text}")
            return text


        return None
    
def get_download_links(d, md5):
    """Get download links from Anna's Archive."""
    url = f"https://annas-archive.org/md5/{md5}"
    
    try:
        response = d.session.get(url, timeout=30)
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
            d.logger.warning("Could not find downloads panel on page")
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
                    d.logger.debug(f"Skipping waitlist server: {a.get_text().strip()}")
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
                    d.logger.debug(f"Added no-waitlist server: {server_name}")
        
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
                d.logger.debug(f"Added external mirror: {domain}")
        
        return title, links
        
    except Exception as e:
        d.logger.error(f"Error fetching download links: {e}")
        return "Unknown", []