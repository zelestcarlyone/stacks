import logging
import re
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from flask import current_app, jsonify, request

from . import api_bp
from stacks.security.auth import require_auth_with_permissions
from stacks.utils.domainutils import try_domains_until_success

logger = logging.getLogger("api")

MD5_RE = re.compile(r"/md5/([a-f0-9]{32})", re.IGNORECASE)
SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([KMGTP]?I?B)", re.IGNORECASE)


def _normalize_flaresolverr_url(url):
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url.rstrip("/")
    return f"http://{url}".rstrip("/")


def _build_proxies(config):
    if not config.get("proxy", "enabled"):
        return None

    proxy_url = config.get("proxy", "url")
    if not proxy_url:
        return None

    username = config.get("proxy", "username", default=None)
    password = config.get("proxy", "password", default=None)

    if username and password and "://" in proxy_url and "@" not in proxy_url:
        scheme, rest = proxy_url.split("://", 1)
        proxy_url = f"{scheme}://{username}:{password}@{rest}"

    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def _extract_size_bytes(value):
    if not value:
        return 0.0

    match = SIZE_RE.search(value.upper())
    if not match:
        return 0.0

    amount = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {
        "B": 1,
        "KB": 1e3,
        "KIB": 1024,
        "MB": 1e6,
        "MIB": 1024 ** 2,
        "GB": 1e9,
        "GIB": 1024 ** 3,
        "TB": 1e12,
        "TIB": 1024 ** 4,
    }
    return amount * multipliers.get(unit, 1)


def _parse_results(html, domain):
    soup = BeautifulSoup(html, "html.parser")
    seen_md5 = set()
    results = []

    for title_link in soup.find_all("a", href=MD5_RE):
        classes = title_link.get("class", [])
        if "js-vim-focus" not in classes:
            continue

        href = title_link.get("href", "")
        md5_match = MD5_RE.search(href)
        if not md5_match:
            continue

        md5 = md5_match.group(1).lower()
        if md5 in seen_md5:
            continue

        title = title_link.get_text(" ", strip=True)
        if not title:
            continue

        info_block = title_link.parent
        if info_block is None:
            continue

        author = ""
        publisher = ""
        metadata = ""
        description = ""

        search_links = info_block.find_all("a", href=re.compile(r"^/search\?q="))
        if search_links:
            author = search_links[0].get_text(" ", strip=True)
        if len(search_links) > 1:
            publisher = search_links[1].get_text(" ", strip=True)

        result_root = info_block.parent
        if result_root is not None:
            metadata_block = result_root.find(
                "div",
                class_=lambda value: value and "text-gray-800" in value and "font-semibold" in value and "text-sm" in value,
            )
            if metadata_block:
                metadata = metadata_block.get_text(" ", strip=True).replace("Save", "").strip(" ·")

            description_block = result_root.find(
                "div",
                class_=lambda value: value and "text-sm" in value and "text-gray-600" in value,
            )
            if description_block:
                description = description_block.get_text(" ", strip=True)

        size_human = ""
        file_type = ""
        year = ""
        languages = ""
        if metadata:
            parts = [part.strip() for part in metadata.split("·")]
            if parts:
                languages = parts[0]
            if len(parts) > 1:
                file_type = parts[1]
            if len(parts) > 2:
                size_human = parts[2]
            year_match = re.search(r"\b(19|20)\d{2}\b", metadata)
            if year_match:
                year = year_match.group(0)

        results.append({
            "md5": md5,
            "title": title,
            "author": author,
            "publisher": publisher,
            "description": description,
            "metadata": metadata,
            "language": languages,
            "file_type": file_type,
            "size_human": size_human,
            "year": year,
            "url": f"https://{domain}/md5/{md5}",
            "source": "annas",
        })
        seen_md5.add(md5)

    results.sort(key=lambda item: _extract_size_bytes(item["size_human"]), reverse=True)
    return results[:50]


def _fetch_search_html(config, url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    proxies = _build_proxies(config)
    response = requests.get(url, headers=headers, timeout=25, proxies=proxies)
    response.raise_for_status()
    return response.text


def _fetch_with_flaresolverr(config, url):
    flaresolverr_url = _normalize_flaresolverr_url(
        config.get("flaresolverr", "url", default=None)
    )
    if not flaresolverr_url or not config.get("flaresolverr", "enabled"):
        return None

    timeout_seconds = int(config.get("flaresolverr", "timeout", default=60))
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": timeout_seconds * 1000,
    }
    response = requests.post(
        f"{flaresolverr_url}/v1",
        json=payload,
        timeout=timeout_seconds + 10,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "FlareSolverr search request failed"))
    return data.get("solution", {}).get("response", "")


def _search_single_domain(query, config, domain):
    encoded_query = quote_plus(query)
    search_variants = [
        f"https://{domain}/search?q={encoded_query}&ext=epub",
        f"https://{domain}/search?q={encoded_query}",
    ]

    all_results = []
    seen_md5 = set()

    for url in search_variants:
        try:
            html = _fetch_search_html(config, url)
        except Exception as exc:
            logger.warning("Direct Anna search failed for %s: %s", url, exc)
            html = _fetch_with_flaresolverr(config, url)

        if not html:
            continue

        for result in _parse_results(html, domain):
            if result["md5"] in seen_md5:
                continue
            seen_md5.add(result["md5"])
            all_results.append(result)

    if not all_results:
        raise RuntimeError(f"No search results found on {domain}")

    all_results.sort(key=lambda item: _extract_size_bytes(item["size_human"]), reverse=True)
    return all_results[:50]


@api_bp.route("/api/search", methods=["POST"])
@require_auth_with_permissions(allow_downloader=True)
def api_search():
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()

    if len(query) < 2:
        return jsonify({
            "success": False,
            "error": "Query must be at least 2 characters",
        }), 400

    config = current_app.stacks_config

    try:
        results = try_domains_until_success(_search_single_domain, query, config)
    except Exception as exc:
        logger.exception("Search failed for query '%s'", query)
        return jsonify({
            "success": False,
            "error": f"Search failed: {exc}",
        }), 502

    return jsonify({
        "success": True,
        "query": query,
        "count": len(results),
        "results": results,
    })
