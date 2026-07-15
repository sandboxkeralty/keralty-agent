"""Executive news aggregation from Spanish/Basque newspapers via official RSS.

All six sources publish real RSS (probed July 2026 — no scraping needed), but with
two traps encoded here:
- El País's legacy feed (elpais.com/rss/elpais/portada.xml) is FROZEN at 2020 —
  only feeds.elpais.com is current.
- Vocento feeds (Diario Vasco, El Correo) intermittently serve an anti-bot HTML
  wall instead of XML, and their XML breaks Python's strict ElementTree parser —
  hence feedparser (tolerant), candidate-URL lists, per-source failure isolation,
  and a stale-cache fallback so one successful fetch per source per day suffices.

"Daily" cadence = a global Firestore cache (news_cache/latest) with a TTL,
refreshed on page load / manual refresh — no Cloud Scheduler exists in this
project yet. Summaries are batched through Gemini Flash (thinking_budget=0,
same pattern as services/email/triage_service.py) with the cleaned RSS
description as fallback, so a Gemini hiccup never blanks the page.
"""

import hashlib
import html as _html
import io
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import settings
from services.firestore import db

_CACHE_DOC = ("news_cache", "latest")

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

SOURCES: List[Dict[str, Any]] = [
    {
        "id": "diariovasco",
        "name": "El Diario Vasco",
        "region": "pais_vasco",
        "site_url": "https://www.diariovasco.com/",
        "feed_urls": [
            "https://www.diariovasco.com/rss/2.0/portada",
            "https://www.diariovasco.com/rss/2.0/?section=ultima-hora",
            "https://www.diariovasco.com/rss/2.0/?section=portada",
        ],
    },
    {
        "id": "eitb",
        "name": "EITB",
        "region": "pais_vasco",
        "site_url": "https://www.eitb.eus/es/",
        "feed_urls": ["https://www.eitb.eus/es/rss/noticias/"],
    },
    {
        "id": "elcorreo",
        "name": "El Correo",
        "region": "pais_vasco",
        "site_url": "https://www.elcorreo.com/",
        "feed_urls": [
            "https://www.elcorreo.com/rss/2.0/portada",
            "https://www.elcorreo.com/rss/2.0/?section=portada",
        ],
    },
    {
        "id": "elcorreo_alava",
        "name": "El Correo Álava",
        "region": "pais_vasco",
        "site_url": "https://www.elcorreo.com/alava/",
        "feed_urls": ["https://www.elcorreo.com/rss/2.0/?section=alava"],
    },
    {
        "id": "elpais",
        "name": "El País",
        "region": "espana",
        "site_url": "https://elpais.com/",
        # NOT elpais.com/rss/... — that legacy feed stopped updating in 2020.
        "feed_urls": ["https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"],
    },
    {
        "id": "elmundo",
        "name": "El Mundo",
        "region": "espana",
        "site_url": "https://www.elmundo.es/",
        "feed_urls": ["https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml"],
    },
]

_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
_WS_RE = re.compile(r"\s+")


def _clean_html(text: str, limit: int = 400) -> str:
    text = _TAG_RE.sub(" ", text or "")
    text = _WS_RE.sub(" ", _html.unescape(text)).strip()
    return text[:limit]


def _is_recent(published_at: str) -> bool:
    """True when the item is within NEWS_MAX_AGE_HOURS. Items without a parseable
    date are excluded — every source provides dates, and undated entries are
    typically pinned/stale (e.g. EITB kept a 2025 promo item at the feed top)."""
    if not published_at:
        return False
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(published_at)
        return age.total_seconds() <= settings.NEWS_MAX_AGE_HOURS * 3600
    except Exception:
        return False


def _fetch_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fetches one source's items, trying candidate URLs in order.

    Raises on total failure — the caller isolates per-source errors.
    feedparser is fed raw bytes we download ourselves so we control the
    User-Agent (Vocento's bot wall) and the timeout.
    """
    import feedparser

    last_err: Optional[Exception] = None
    for url in source["feed_urls"]:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": _UA,
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw = resp.read()
            parsed = feedparser.parse(io.BytesIO(raw))
            entries = parsed.get("entries") or []
            if not entries:
                last_err = RuntimeError(f"no entries at {url}")
                continue
            items = []
            saw_valid_but_old = False
            for e in entries:
                if len(items) >= settings.NEWS_MAX_ITEMS_PER_SOURCE:
                    break
                link = e.get("link") or ""
                title = _clean_html(e.get("title") or "", 200)
                if not link or not title:
                    continue
                published = ""
                tp = e.get("published_parsed") or e.get("updated_parsed")
                if tp:
                    published = datetime(*tp[:6], tzinfo=timezone.utc).isoformat()
                if not _is_recent(published):
                    saw_valid_but_old = True
                    continue
                image_url = ""
                for m in (e.get("media_content") or []) + (e.get("media_thumbnail") or []):
                    if m.get("url"):
                        image_url = m["url"]
                        break
                if not image_url:
                    m = _IMG_RE.search(e.get("summary") or "")
                    if m:
                        image_url = m.group(1)
                items.append({
                    "id": hashlib.sha1(link.encode()).hexdigest()[:16],
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "region": source["region"],
                    "title": title,
                    "raw_summary": _clean_html(e.get("summary") or e.get("description") or ""),
                    "summary": "",
                    "link": link,
                    "published_at": published,
                    "image_url": image_url,
                })
            if items:
                return items
            if saw_valid_but_old:
                # The feed works — there simply is no news in the window.
                # Not a failure: return empty rather than triggering the
                # stale-fallback/warning path.
                return []
            last_err = RuntimeError(f"entries without usable title/link at {url}")
        except Exception as e:
            last_err = e
    raise RuntimeError(f"{source['id']}: all feed candidates failed ({last_err})")


def _summarize_batch(items: List[Dict[str, Any]]) -> None:
    """Fills item['summary'] with a 1-2 sentence executive Spanish summary.

    One batched Gemini call for all items (triage_service pattern). On ANY
    failure every item falls back to its cleaned RSS description — the page
    must render regardless.
    """
    for it in items:
        it["summary"] = it["raw_summary"] or it["title"]
    if not items:
        return
    try:
        from google.genai import types
        from services.genai_client import get_genai_client

        snippets = "\n".join(
            f"[{i}] {it['title']} — {it['raw_summary'][:250]}"
            for i, it in enumerate(items)
        )
        prompt = (
            "Eres un editor de prensa para ejecutivos. Para cada noticia, escribe un "
            "resumen de 1-2 frases en español, informativo y neutro, que permita a un "
            "directivo decidir si abrir el artículo. No repitas el titular literalmente; "
            "no inventes datos que no estén en el texto.\n\n"
            f"Noticias:\n{snippets}\n\n"
            f"Responde con SOLO un array JSON de {len(items)} strings, uno por noticia, "
            "en el mismo orden."
        )
        client = get_genai_client()
        response = client.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
                # Mandatory: thinking tokens otherwise consume the budget and
                # the JSON comes back empty/truncated (see triage_service.py).
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = (response.text or "").strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        summaries = json.loads(raw[start:end]) if start >= 0 else []
        if len(summaries) == len(items):
            for it, s in zip(items, summaries):
                if isinstance(s, str) and s.strip():
                    it["summary"] = s.strip()[:400]
    except Exception as e:
        print(f"[news_service] batch summarization failed, using RSS descriptions: {e}",
              flush=True)


def _load_cache() -> Optional[Dict[str, Any]]:
    try:
        doc = db.collection(_CACHE_DOC[0]).document(_CACHE_DOC[1]).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"[news_service] cache load failed: {e}", flush=True)
        return None


def get_news(force_refresh: bool = False) -> Dict[str, Any]:
    """Returns {generated_at, items, warnings}. Serves the shared Firestore
    cache while fresh; otherwise refetches all sources concurrently,
    summarizes only NEW items (deduped by id against cache), and keeps a
    failed source's previous items (stale fallback + warning)."""
    cached = _load_cache()
    if cached and not force_refresh:
        try:
            age_h = (datetime.now(timezone.utc)
                     - datetime.fromisoformat(cached["generated_at"])).total_seconds() / 3600
            if age_h < settings.NEWS_CACHE_TTL_HOURS:
                # Re-apply the age window at serving time: cached items keep
                # aging between refreshes and must drop out at the 24h mark.
                cached["items"] = [i for i in cached["items"] if _is_recent(i.get("published_at", ""))]
                return cached
        except Exception:
            pass

    cached_items = {it["id"]: it for it in (cached or {}).get("items", [])}
    cached_by_source: Dict[str, List[dict]] = {}
    for it in cached_items.values():
        cached_by_source.setdefault(it["source_id"], []).append(it)

    warnings: List[str] = []
    fresh_by_source: Dict[str, List[dict]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_fetch_source, s): s for s in SOURCES}
        for fut, s in futures.items():
            try:
                fresh_by_source[s["id"]] = fut.result()
            except Exception as e:
                print(f"[news_service] {s['id']} fetch failed: {e}", flush=True)
                warnings.append(s["id"])
                # Stale fallback: yesterday's news beats an empty section.
                fresh_by_source[s["id"]] = cached_by_source.get(s["id"], [])

    # Summarize only items we haven't summarized before.
    new_items = []
    for its in fresh_by_source.values():
        for it in its:
            prev = cached_items.get(it["id"])
            if prev and prev.get("summary"):
                it["summary"] = prev["summary"]
            else:
                new_items.append(it)
    _summarize_batch(new_items)

    all_items: List[dict] = []
    for its in fresh_by_source.values():
        # Stale-fallback items age too — enforce the window on everything.
        its = [i for i in its if _is_recent(i.get("published_at", ""))]
        its.sort(key=lambda x: x.get("published_at") or "", reverse=True)
        all_items.extend(its)
    for it in all_items:
        it.pop("raw_summary", None)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": all_items,
        "warnings": warnings,
    }
    try:
        db.collection(_CACHE_DOC[0]).document(_CACHE_DOC[1]).set(result)
    except Exception as e:
        print(f"[news_service] cache write failed: {e}", flush=True)
    return result
