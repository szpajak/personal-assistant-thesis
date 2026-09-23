"""Normalize job-board URLs for stable deduplication."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "trk",
    "trkInfo",
    "ref",
    "refId",
    "source",
    "mc_cid",
    "mc_eid",
    "fbclid",
    "gclid",
    "li_fat_id",
}


def normalize_job_url(url: str) -> str:
    """Lowercase host, strip fragment, drop common tracking query params."""
    raw = (url or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    # Synthetic ``source://job/id`` URLs from missing board links.
    if not parsed.scheme or not parsed.netloc:
        return raw

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(query_pairs, doseq=True)
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse(
        (parsed.scheme.lower(), host, path, parsed.params, query, "")
    )
