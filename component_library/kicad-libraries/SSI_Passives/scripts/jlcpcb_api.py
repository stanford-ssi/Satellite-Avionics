"""Minimal client for JLCPCB's public parts-search endpoint (the one behind jlcpcb.com/parts).

This is an unofficial API; keep requests slow and few.
"""

import json
import time
import urllib.request

SEARCH_URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (SSI-Satellites passive library builder)",
    "Origin": "https://jlcpcb.com",
    "Referer": "https://jlcpcb.com/parts",
}
PAGE_SIZE = 1000
REQUEST_DELAY_S = 2.0


def search_page(page, keyword=None, **filters):
    body = {"currentPage": page, "pageSize": PAGE_SIZE, "keyword": keyword, "searchType": 2, **filters}
    req = urllib.request.Request(SEARCH_URL, data=json.dumps(body).encode(), headers=HEADERS)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
            if payload.get("code") != 200:
                raise RuntimeError(f"API error: {payload.get('code')} {payload.get('message')}")
            return payload["data"]["componentPageInfo"]
        except Exception as err:  # network hiccups / rate limiting
            if attempt == 3:
                raise
            wait = 10 * (attempt + 1)
            print(f"    request failed ({err}); retrying in {wait}s")
            time.sleep(wait)


def search_all(keyword=None, **filters):
    """Yield every result for a query, walking all pages."""
    page = 1
    seen = 0
    while True:
        info = search_page(page, keyword, **filters)
        items = info.get("list") or []
        yield from items
        seen += len(items)
        total = info.get("total") or 0
        print(f"    page {page}: {seen}/{total}")
        if not items or seen >= total:
            return
        page += 1
        time.sleep(REQUEST_DELAY_S)
