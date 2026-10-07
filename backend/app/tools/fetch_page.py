from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

MAX_RESPONSE_BYTES = 2_000_000

STRIP_TAGS = (
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "template",
    "nav",
    "header",
    "footer",
    "form",
)


def clean_text(text: str) -> str:
    return " ".join((text or "").split())


def extract_page_text(html: str) -> tuple[str, str, str]:
    """Return (title, meta description, visible body text) from an HTML document."""
    soup = BeautifulSoup(html or "", "html.parser")

    title = clean_text(soup.title.get_text(" ")) if soup.title else ""

    meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta",
        attrs={"property": "og:description"},
    )
    meta_description = clean_text((meta_tag.get("content") or "")) if meta_tag else ""

    for tag_name in STRIP_TAGS:
        for node in soup.find_all(tag_name):
            node.decompose()

    body = clean_text(soup.get_text(" "))

    return title, meta_description, body


def fetch_page(
    url: str,
    *,
    timeout: float = 10.0,
    max_chars: int = 6000,
) -> dict[str, Any]:
    """Fetch a single page and return extracted research fields."""
    result: dict[str, Any] = {
        "url": url,
        "ok": False,
        "title": "",
        "meta_description": "",
        "text": "",
        "error": None,
    }

    parsed = urlparse(url or "")

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        result["error"] = "unsupported_url"
        return result

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            response = client.get(url)
            response.raise_for_status()

            declared_size = response.headers.get("content-length")

            if declared_size and declared_size.isdigit() and int(declared_size) > MAX_RESPONSE_BYTES:
                result["error"] = "response_too_large"
                return result

            content_type = (response.headers.get("content-type") or "").lower()

            if content_type and not any(
                allowed in content_type
                for allowed in ("html", "text/plain", "xml")
            ):
                result["error"] = f"unsupported_content_type:{content_type}"
                return result

            title, meta_description, text = extract_page_text(response.text)

            result.update(
                {
                    "ok": bool(text),
                    "title": title,
                    "meta_description": meta_description,
                    "text": text[:max_chars],
                    "error": None if text else "empty_page",
                }
            )

    except Exception as exc:
        result["error"] = str(exc) or exc.__class__.__name__

    return result


def fetch_pages(
    urls: list[str],
    *,
    concurrency: int | None = None,
    timeout: float | None = None,
    max_chars: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch many pages concurrently, keyed by the requested URL."""
    unique_urls = list(dict.fromkeys(url for url in urls if url))

    if not unique_urls:
        return {}

    settings = get_settings()

    workers = max(1, concurrency or settings.research_concurrency)
    timeout = timeout or settings.research_timeout
    max_chars = max_chars or settings.research_max_chars

    results: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=min(workers, len(unique_urls))) as pool:
        futures = {
            pool.submit(fetch_page, url, timeout=timeout, max_chars=max_chars): url
            for url in unique_urls
        }

        for future in as_completed(futures):
            url = futures[future]

            try:
                results[url] = future.result()
            except Exception as exc:
                results[url] = {
                    "url": url,
                    "ok": False,
                    "title": "",
                    "meta_description": "",
                    "text": "",
                    "error": str(exc) or exc.__class__.__name__,
                }

    return results
