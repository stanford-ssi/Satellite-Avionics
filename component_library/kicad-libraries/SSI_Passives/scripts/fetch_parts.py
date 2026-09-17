"""Stage 1: download in-stock parts for every series in series.json from JLCPCB into raw/<table>.json.

This is the only stage that needs network access. Re-run it to refresh stock / new parts, then run
build_csv.py and build_db.py.

Usage:
    python scripts/fetch_parts.py                      # all series
    python scripts/fetch_parts.py --only c_samsung_cl  # one or more tables
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jlcpcb_api import REQUEST_DELAY_S, search_all  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "raw"

# Only these API fields are kept in the raw cache; the rest is images, pricing tiers for the shop, etc.
RAW_KEYS = [
    "componentCode", "componentBrandEn", "componentModelEn", "componentSpecificationEn",
    "componentTypeEn", "describe", "attributes", "componentLibraryType",
    "preferredComponentFlag", "stockCount", "dataManualUrl", "lcscGoodsUrl", "componentPrices",
]


def download(series):
    parts = {}
    for query in series["queries"]:
        query = dict(query)
        keyword = query.pop("keyword", None)
        print(f"  query keyword={keyword!r} filters={query}")
        for item in search_all(keyword, stockFlag=True, **query):
            parts[item["componentCode"]] = {k: item.get(k) for k in RAW_KEYS}
        time.sleep(REQUEST_DELAY_S)
    rows = sorted(parts.values(), key=lambda p: int(p["componentCode"][1:]))
    RAW_DIR.mkdir(exist_ok=True)
    path = RAW_DIR / f"{series['id']}.json"
    path.write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d"), "parts": rows}, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"  {len(rows)} in-stock parts -> {path.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="series ids to fetch")
    args = ap.parse_args()

    config = json.loads((ROOT / "series.json").read_text(encoding="utf-8"))
    for series in config["series"]:
        if args.only and series["id"] not in args.only:
            continue
        print(f"[{series['id']}]")
        download(series)


if __name__ == "__main__":
    main()
