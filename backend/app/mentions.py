"""Competitor customers that no USAC dataset can see — found in public web
sources instead:

- DuckDuckGo HTML search (no API key): board minutes, tech plans, press
  releases, and news naming a competitor's school/library customers.
- mobilebeacon.org's own published case studies — Mobile Beacon names its
  customers by organization in its education/library stories.

These are "soft" leads (no BEN, no filing) — Matt presents them with their
source URL so Kim can qualify them, and can then cross-reference contacts
with the usual district-website lookup.
"""
import html
import logging
import re
import urllib.parse

import httpx

from . import db
import hashlib
import json
import time

log = logging.getLogger(__name__)

_H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
CACHE_TTL = 24 * 3600

_RESULT_RE = re.compile(
    r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_SNIPPET_RE = re.compile(
    r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)>', re.DOTALL)


def _cached(key: str, fn):
    kh = hashlib.sha256(("mentions:" + key).encode()).hexdigest()
    with db.closing_conn() as conn:
        row = conn.execute(
            "SELECT fetched_at, body FROM http_cache WHERE url_hash=?",
            (kh,)).fetchone()
    if row and time.time() - row["fetched_at"] < CACHE_TTL:
        return json.loads(row["body"])
    out = fn()
    if out:
        with db.closing_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO http_cache (url_hash, url, "
                "fetched_at, body) VALUES (?,?,?,?)",
                (kh, "mentions:" + key, time.time(), json.dumps(out)))
            conn.commit()
    return out


def _clean(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _real_url(u: str) -> str:
    """DDG links are redirects: //duckduckgo.com/l/?uddg=<encoded>."""
    if "uddg=" in u:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
        if q.get("uddg"):
            return q["uddg"][0]
    return u


def web_search(query: str, limit: int = 8) -> list[dict]:
    """DuckDuckGo HTML search -> [{title, url, snippet}]. Best-effort."""
    def go():
        try:
            r = httpx.get("https://html.duckduckgo.com/html/",
                          params={"q": query}, headers=_H, timeout=25,
                          follow_redirects=True)
            r.raise_for_status()
        except Exception as e:
            log.warning("web search failed (%s): %s", query, e)
            return []
        links = _RESULT_RE.findall(r.text)
        snips = [_clean(s) for s in _SNIPPET_RE.findall(r.text)]
        out = []
        for i, (u, t) in enumerate(links[:limit]):
            out.append({"title": _clean(t)[:140],
                        "url": _real_url(u)[:300],
                        "snippet": (snips[i][:240] if i < len(snips)
                                    else "")})
        return out
    return _cached(f"ddg:{query}:{limit}", go)


def mobile_beacon_case_studies() -> list[dict]:
    """Named customers from mobilebeacon.org's own published stories.
    Their category pages bot-block direct fetches (403), but search
    engines index them — so we pull the indexed story pages instead."""
    def go():
        out, seen = [], set()
        for seg, q in (
            ("education", 'site:mobilebeacon.org "case study" school'),
            ("libraries", 'site:mobilebeacon.org "case study" library'),
            ("stories", 'site:mobilebeacon.org hotspot district'),
        ):
            for r in web_search(q, 8):
                url = r["url"]
                if "mobilebeacon.org" not in url or url in seen:
                    continue
                seen.add(url)
                out.append({"segment": seg, "title": r["title"][:140],
                            "url": url[:300], "snippet": r["snippet"]})
        return out[:30]
    return _cached("mb:case-studies", go)


def competitor_mentions(competitor_label: str, region: str | None = None,
                        limit: int = 8) -> dict:
    """Public-web mentions of a competitor's K-12/library customers."""
    q = (f'"{competitor_label}" school district hotspot')
    if region:
        q += f" {region}"
    results = web_search(q, limit)
    extra = web_search(
        f'"{competitor_label}" library "board" minutes hotspot'
        + (f" {region}" if region else ""), max(3, limit // 2))
    seen = set()
    merged = []
    for r in results + extra:
        if r["url"] not in seen:
            seen.add(r["url"])
            merged.append(r)
    out = {"competitor": competitor_label, "region": region,
           "mentions": merged[:limit + 4],
           "note": "Public-web mentions (board minutes, tech plans, news). "
                   "Soft leads — verify before outreach; no USAC filing "
                   "backs these."}
    if "beacon" in competitor_label.lower():
        out["case_studies"] = mobile_beacon_case_studies()
        out["note"] += (" case_studies come from mobilebeacon.org's own "
                        "published customer stories.")
    return out
