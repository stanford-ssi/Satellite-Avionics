"""Verify the library against JLCPCB: for each LCSC number, ask JLCPCB's part-detail endpoint what part it is
and compare MPN, manufacturer, package and value with what csv/ claims.

Independent of the search endpoint used by fetch_parts.py. Needs network; ~15 min for the whole library.

Usage:
    python scripts/verify_lcsc.py            # every part
    python scripts/verify_lcsc.py --sample 50  # 50 random parts per sub-library
"""

import argparse
import csv
import json
import random
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize import parse_quantity  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = ROOT / "csv"
DETAIL_URL = "https://cart.jlcpcb.com/shoppingCart/smtGood/getComponentDetail?componentCode={code}"
HEADERS = {"User-Agent": "Mozilla/5.0 (SSI-Satellites passive library verifier)", "Accept": "application/json"}
WORKERS = 3
DELAY_S = 0.6
VALUE_ATTRIBUTE = {"R": "Resistance", "C": "Capacitance", "L": "Inductance"}


def fetch_detail(code):
    req = urllib.request.Request(DETAIL_URL.format(code=code), headers=HEADERS)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)
            time.sleep(DELAY_S)
            return payload.get("data") or {}
        except Exception as err:  # network hiccup or rate limit: back off and retry
            if attempt == 3:
                return {"_error": str(err)}
            time.sleep(5 * (attempt + 1))


def check(row, detail):
    """Return a list of mismatch strings (empty = verified)."""
    if "_error" in detail:
        return [f"network: {detail['_error']}"]
    if not detail:
        return ["JLCPCB returned no part for this code"]
    problems = []
    if (detail.get("componentCode") or "").upper() != row["LCSC"]:
        problems.append(f"code mismatch: JLCPCB says {detail.get('componentCode')!r}")
    if (detail.get("componentModelEn") or "").strip().upper() != row["MPN"].upper():
        problems.append(f"MPN: library {row['MPN']!r} vs JLCPCB {detail.get('componentModelEn')!r}")
    brand = (detail.get("componentBrandEn") or "").lower()
    if row["Manufacturer"].split()[0].lower() not in brand:
        problems.append(f"manufacturer: library {row['Manufacturer']!r} vs JLCPCB {detail.get('componentBrandEn')!r}")
    package = (detail.get("componentSpecificationEn") or "").strip()
    if row["Package"].startswith("XAL"):
        if not row["MPN"].startswith(row["Package"]):
            problems.append(f"package: {row['Package']} not in MPN {row['MPN']}")
    elif package != row["Package"]:
        problems.append(f"package: library {row['Package']!r} vs JLCPCB {package!r}")
    attrs = {a.get("attribute_name_en"): a.get("attribute_value_name") for a in (detail.get("attributes") or [])}
    kind = row["Part_ID"][0]
    theirs = parse_quantity(attrs.get(VALUE_ATTRIBUTE[kind]))
    ours = parse_quantity(row["Value"])
    if theirs is None:
        problems.append(f"value: JLCPCB lists no {VALUE_ATTRIBUTE[kind]} attribute (library says {row['Value']})")
    elif ours is None or (ours == 0) != (theirs == 0) or (ours and abs(theirs - ours) / ours > 0.005):
        problems.append(f"value: library {row['Value']} vs JLCPCB {attrs.get(VALUE_ATTRIBUTE[kind])!r}")
    return problems


def is_basic(detail):
    """The detail endpoint only reports base/expand; it does not expose JLCPCB's 'Preferred' flag."""
    return detail.get("componentLibraryType") == "base"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, help="random parts per sub-library instead of all")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    config = json.loads((ROOT / "series.json").read_text(encoding="utf-8"))
    todo = []
    for table in config["sublibraries"]:
        with (CSV_DIR / f"{table}.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if args.sample and len(rows) > args.sample:
            rows = random.Random(args.seed).sample(rows, args.sample)
        todo += [(table, row) for row in rows]
    print(f"verifying {len(todo)} parts against JLCPCB ({WORKERS} workers, {DELAY_S}s pause each)", flush=True)

    results = defaultdict(list)
    class_changes = []
    started = time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        for i, ((table, row), detail) in enumerate(zip(todo, pool.map(lambda tr: fetch_detail(tr[1]["LCSC"]), todo)), 1):
            problems = check(row, detail)
            results[table].append((row, problems))
            if not problems and is_basic(detail) != (row["LCSC_Type"] == "Basic"):
                class_changes.append((row["LCSC"], row["Part_ID"], row["LCSC_Type"], "Basic" if is_basic(detail) else "Extended/Preferred"))
            if problems:
                print(f"  MISMATCH {row['LCSC']:>10}  {row['Part_ID']:<45} " + "; ".join(problems), flush=True)
            if i % 250 == 0:
                print(f"  ... {i}/{len(todo)} checked, {time.time() - started:.0f}s", flush=True)

    print("\nsummary:")
    total_bad = 0
    for table, items in results.items():
        bad = [p for _, p in items if p]
        network = [p for p in bad if p[0].startswith("network")]
        total_bad += len(bad) - len(network)
        print(f"  {config['sublibraries'][table]['name']:<32} {len(items):5d} checked  {len(items) - len(bad):5d} verified  "
              f"{len(bad) - len(network):3d} mismatched  {len(network):3d} unverified (network)")
    print(f"  TOTAL mismatches: {total_bad}")
    if class_changes:
        print(f"\n{len(class_changes)} parts moved into or out of JLCPCB's Basic class since the library was built "
              "(Preferred vs Extended can't be told apart by this endpoint; not an error - rebuild with --fetch to update):")
        for code, part_id, before, after in class_changes[:40]:
            print(f"  {code:>10}  {part_id:<45} {before} -> {after}")
        print(f"  class changes by kind: {dict(Counter(f'{b}->{a}' for _, _, b, a in class_changes))}")


if __name__ == "__main__":
    main()
