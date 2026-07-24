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


def news_search(query: str, limit: int = 8) -> list[dict]:
    """Google News RSS (keyless): fresh articles -> [{title, url, date,
    source}]. Catches same-week signals like a district announcing a
    hotspot-lending program or a competitor contract award."""
    def go():
        try:
            r = httpx.get("https://news.google.com/rss/search",
                          params={"q": query, "hl": "en-US", "gl": "US",
                                  "ceid": "US:en"},
                          headers=_H, timeout=25, follow_redirects=True)
            r.raise_for_status()
        except Exception as e:
            log.warning("news search failed (%s): %s", query, e)
            return []
        items = re.findall(r"<item>(.*?)</item>", r.text, re.DOTALL)
        out = []
        for it in items[:limit]:
            def tag(t):
                m = re.search(fr"<{t}>(.*?)</{t}>", it, re.DOTALL)
                return _clean(m.group(1)) if m else ""
            link = re.search(r"<link/?>?\s*(https?://\S+?)\s*(?:</link>|<)",
                             it)
            out.append({"title": tag("title")[:140],
                        "url": (link.group(1) if link else "")[:300],
                        "date": tag("pubDate")[:32],
                        "source": tag("source")[:60]})
        return out
    return _cached(f"news:{query}:{limit}", go)


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


def find_open_bids(state: str | None = None, limit: int = 10) -> dict:
    """Non-E-Rate procurement: cellular/hotspot/bus-Wi-Fi bids posted on
    public bid aggregators. Districts buy plenty of LTE outside E-Rate —
    these never appear in USAC data. Soft leads with source URLs."""
    sites = ("site:bidnetdirect.com OR site:demandstar.com OR "
             "site:bonfirehub.com OR site:publicpurchase.com OR "
             "site:ionwave.net")
    q = (f'({sites}) (cellular OR hotspot OR "wireless data" OR '
         f'"bus wifi") school')
    if state:
        q += f" {state}"
    results = web_search(q, limit)
    extra = web_search(
        f'({sites}) library hotspot lending' + (f" {state}" if state else ""),
        max(3, limit // 2))
    seen, merged = set(), []
    for r in results + extra:
        if r["url"] not in seen:
            seen.add(r["url"])
            merged.append(r)
    return {"state": state, "bids": merged[:limit + 4],
            "note": "Open bids on public procurement portals (outside "
                    "E-Rate). Verify posting dates on the source page — "
                    "search results can include closed bids."}


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
    news = news_search(f'"{competitor_label}" school OR library hotspot'
                       + (f" {region}" if region else ""), 6)
    out = {"competitor": competitor_label, "region": region,
           "mentions": merged[:limit + 4],
           "fresh_news": news,
           "note": "Public-web mentions (board minutes, tech plans, news). "
                   "Soft leads — verify before outreach; no USAC filing "
                   "backs these."}
    if "beacon" in competitor_label.lower():
        out["case_studies"] = mobile_beacon_case_studies()
        out["note"] += (" case_studies come from mobilebeacon.org's own "
                        "published customer stories.")
    return out
