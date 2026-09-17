"""Stage 2: apply the rules in series.json to raw/<series id>.json and write one csv/<sub-library>.csv per sub-library.

Offline. A series (e.g. Uniroyal thick film) feeds one sub-library, or two when it is split by JLCPCB fee
class (Basic/Preferred -> "no_fee" table, Extended -> "fee" table). The CSVs are the reviewable form of
the library: every row is one orderable LCSC part.

Usage:
    python scripts/build_csv.py
"""

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize import COLUMNS, normalize_part  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "raw"
CSV_DIR = ROOT / "csv"

NO_FEE_CLASSES = {"Basic", "Preferred"}
# Two parts with the same spec are interchangeable (typically packaging variants of one part); keep one.
# Part_ID at this point is the bare "<kind> <value> <package/family> <ratings>" name.
SPEC_COLUMNS = {
    "R": ["Part_ID"],
    "C": ["Part_ID"],
    "L": ["Part_ID", "Current", "DCR"],
}
# When two kept parts would still share a Part_ID, insert these columns (in order) until the IDs differ.
ID_TIEBREAKERS = {"R": ["Power", "MPN"], "C": ["MPN"], "L": ["Current", "MPN"]}
LCSC_RANK = {"Basic": 0, "Preferred": 1, "Extended": 2}


def select(series, raw_parts, footprint_lib):
    mpn_re = re.compile(series["mpn_regex"])
    must_contain = series.get("description_must_contain", "").lower()
    packages = set(series.get("packages", []))
    tolerances = set(series.get("tolerances", []))
    value_series = set(series.get("value_series", []))
    excluded = set(series.get("exclude_lcsc", []))
    min_stock = series.get("min_stock", 1)
    skipped = Counter()
    kept = []

    for raw in raw_parts:
        if raw["componentCode"] in excluded:
            skipped["excluded in series.json"] += 1
        elif not mpn_re.search(raw.get("componentModelEn") or ""):
            skipped["MPN not in series"] += 1
        elif must_contain and must_contain not in (raw.get("describe") or "").lower():
            skipped[f"description lacks '{series['description_must_contain']}'"] += 1
        elif (raw.get("stockCount") or 0) < min_stock:
            skipped[f"stock < {min_stock}"] += 1
        elif packages and (raw.get("componentSpecificationEn") or "") not in packages:
            skipped["package not wanted"] += 1
        elif (row := normalize_part(series, raw, footprint_lib)) is None:
            skipped["missing/unparseable attributes"] += 1
        elif tolerances and row["Tolerance"] and row["Tolerance"] not in tolerances:
            skipped["tolerance not wanted"] += 1
        elif value_series and row["Value_Series"] not in value_series:
            skipped["value not in wanted E-series"] += 1
        else:
            kept.append(row)

    # Dedupe interchangeable parts: cheapest LCSC class first, then the deepest stock.
    best = {}
    for row in kept:
        spec = tuple(row[c] for c in SPEC_COLUMNS[series["kind"]])
        rank = (LCSC_RANK[row["LCSC_Type"]], -row["Stock"])
        if spec not in best or rank < best[spec][0]:
            best[spec] = (rank, row)
    skipped["duplicate spec (kept the better LCSC part)"] = len(kept) - len(best)
    rows = [row for _, row in best.values()]

    no_footprint = [row for row in rows if not row["Footprint"]]
    rows = [row for row in rows if row["Footprint"]]
    skipped["no KiCad footprint available"] = len(no_footprint)
    return rows, skipped, no_footprint


def route(series, row):
    """Which sub-library table a selected part goes to."""
    target = series["sublibrary"]
    if isinstance(target, str):
        return target
    return target["no_fee"] if row["LCSC_Type"] in NO_FEE_CLASSES else target["fee"]


def assign_unique_ids(rows):
    """Final Part_ID = '<kind> <value> <package> <rating> [tiebreaker] <series tag>', unique across the whole
    library (the .kicad_dbl uses globally_unique_keys, so parts can move between sub-libraries)."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["Part_ID"], row["_tag"])].append(row)
    for (base, tag), members in groups.items():
        ids = [f"{base} {tag}"] * len(members)
        if len(members) > 1:
            tiebreakers = ID_TIEBREAKERS[members[0]["_kind"]]
            for depth in range(1, len(tiebreakers) + 1):
                ids = [" ".join([base] + [m[c] for c in tiebreakers[:depth] if m[c]] + [tag]) for m in members]
                if len(set(ids)) == len(ids):
                    break
            else:
                ids = [f"{base} {m['LCSC']} {tag}" for m in members]
        for member, part_id in zip(members, ids):
            # '/' is KiCad's sub-library separator and ':' its library separator.
            assert not re.search(r"[/:]", part_id), f"illegal character in Part_ID {part_id!r}"
            member["Part_ID"] = part_id
    assert len({r["Part_ID"] for r in rows}) == len(rows), "Part_IDs are not globally unique"


def write_csv(table, rows):
    CSV_DIR.mkdir(exist_ok=True)
    path = CSV_DIR / f"{table}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def main():
    config = json.loads((ROOT / "series.json").read_text(encoding="utf-8"))
    sublibraries = config["sublibraries"]
    tables = {key: [] for key in sublibraries}

    for series in config["series"]:
        raw = json.loads((RAW_DIR / f"{series['id']}.json").read_text(encoding="utf-8"))
        rows, skipped, no_footprint = select(series, raw["parts"], config["footprint_lib"])
        routed = Counter()
        for row in rows:
            table = route(series, row)
            assert sublibraries[table]["kind"] == series["kind"], f"{series['id']} routed to {table} of another kind"
            tables[table].append(row)
            routed[table] += 1
        print(f"[{series['id']}] {len(raw['parts'])} raw (fetched {raw['fetched']}) -> {len(rows)} parts -> {dict(routed)}")
        for reason, count in skipped.most_common():
            if count:
                print(f"    skipped {count:5d}  {reason}")
        if no_footprint:
            print("    parts dropped for lack of a footprint (draw one in SSI_Passives.pretty to include them):")
            for row in sorted(no_footprint, key=lambda r: r["MPN"]):
                print(f"      {row['LCSC']:>10}  {row['MPN']:<24} {row['Value']:>8}  {row['Package']}")

    assign_unique_ids([row for rows in tables.values() for row in rows])

    print("\nsub-libraries:")
    for table, rows in tables.items():
        rows.sort(key=lambda r: r["_sort"])
        path = write_csv(table, rows)
        classes = dict(Counter(r["LCSC_Type"] for r in rows))
        print(f"  {sublibraries[table]['name']:<32} {len(rows):5d} parts -> {path.relative_to(ROOT)}   {classes}")
    for stale in CSV_DIR.glob("*.csv"):
        if stale.stem not in sublibraries:
            stale.unlink()
            print(f"  removed stale {stale.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
