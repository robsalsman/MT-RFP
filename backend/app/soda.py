"""Read-only USAC Socrata (SODA) client.

Respects USAC's data: app token when provided, exponential backoff on 429/5xx,
on-disk (SQLite) response cache with TTL, and full $offset pagination.
"""
import hashlib
import json
import logging
import time

import httpx

from . import config, db

log = logging.getLogger(__name__)

MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 2.0


def _headers() -> dict:
    h = {"Accept": "application/json"}
    if config.USAC_APP_TOKEN:
        h["X-App-Token"] = config.USAC_APP_TOKEN
    return h


def _cache_get(url: str):
    with db.closing_conn() as conn:
        row = conn.execute(
            "SELECT fetched_at, body FROM http_cache WHERE url_hash=?",
            (hashlib.sha256(url.encode()).hexdigest(),),
        ).fetchone()
    if row and time.time() - row["fetched_at"] < config.HTTP_CACHE_TTL_SECONDS:
        return json.loads(row["body"])
    return None


def _cache_put(url: str, body: list) -> None:
    with db.closing_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO http_cache (url_hash, url, fetched_at, body) "
            "VALUES (?, ?, ?, ?)",
            (hashlib.sha256(url.encode()).hexdigest(), url, time.time(),
             json.dumps(body)),
        )
        conn.commit()


def get_json(dataset_id: str, params: dict, use_cache: bool = True) -> list:
    """One SODA request with retry/backoff. Returns parsed JSON list."""
    url = f"{config.USAC_BASE}/{dataset_id}.json"
    req = httpx.Request("GET", url, params=params)
    full_url = str(req.url)
    if use_cache:
        cached = _cache_get(full_url)
        if cached is not None:
            return cached

    delay = BACKOFF_BASE_SECONDS
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.get(url, params=params, headers=_headers(), timeout=60)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp)
            resp.raise_for_status()
            data = resp.json()
            if use_cache:
                _cache_put(full_url, data)
            return data
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            if attempt == MAX_RETRIES:
                raise
            retry_after = None
            if isinstance(e, httpx.HTTPStatusError):
                retry_after = e.response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else delay
            log.warning("SODA request failed (%s), retry %d/%d in %.1fs",
                        e, attempt, MAX_RETRIES, wait)
            time.sleep(wait)
            delay *= 2
    return []  # unreachable


def fetch_all(dataset_id: str, where: str, select: str | None = None,
              order: str = ":id", group: str | None = None,
              page_size: int | None = None, use_cache: bool = True) -> list:
    """Fully paginate a SoQL query via $limit/$offset."""
    page_size = page_size or config.SODA_PAGE_SIZE
    rows: list = []
    offset = 0
    while True:
        params = {"$where": where, "$order": order,
                  "$limit": page_size, "$offset": offset}
        if select:
            params["$select"] = select
        if group:
            params["$group"] = group
        page = get_json(dataset_id, params, use_cache=use_cache)
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows
