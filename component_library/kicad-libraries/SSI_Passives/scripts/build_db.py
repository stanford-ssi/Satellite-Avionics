"""Stage 3: csv/*.csv -> SSI_Passives.sqlite + SSI_Passives.kicad_dbl, then verify through ODBC.

Offline. KiCad reads the .kicad_dbl (which sub-library = which table, which column = which field) and
opens the .sqlite through the "SQLite3 ODBC Driver".

Usage:
    python scripts/build_db.py
"""

import csv
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize import COLUMNS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = ROOT / "csv"

INTEGER_COLUMNS = {"Stock"}
REAL_COLUMNS = {"Unit_Price_USD"}

# KiCad field name shown for each column.
FIELD_NAMES = {
    "LCSC": "LCSC", "LCSC_Type": "LCSC Type", "MPN": "MPN", "Manufacturer": "Manufacturer", "Series": "Series",
    "Package": "Package", "Tolerance": "Tolerance", "Power": "Power", "Voltage": "Voltage",
    "Dielectric": "Dielectric", "Current": "Current", "Isat": "Isat", "DCR": "DCR", "TempCo": "TempCo",
    "Value_Series": "Value Series", "Standard": "Standard", "Datasheet": "Datasheet",
    "LCSC_URL": "LCSC URL", "Stock": "Stock",
}
# (column, visible on schematic when placed, shown as a column in the Symbol Chooser)
KIND_FIELDS = {
    "R": [("Tolerance", False, True), ("Power", False, True), ("TempCo", False, False), ("Voltage", False, False)],
    "C": [("Voltage", False, True), ("Dielectric", False, True), ("Tolerance", False, True)],
    "L": [("Current", False, True), ("Isat", False, True), ("DCR", False, True), ("Tolerance", False, False)],
}
COMMON_FIELDS = [
    ("Package", False, True), ("LCSC", False, True), ("LCSC_Type", False, True), ("MPN", False, True),
    ("Series", False, True), ("Manufacturer", False, False), ("Standard", False, False),
    ("Value_Series", False, False), ("Datasheet", False, False), ("LCSC_URL", False, False), ("Stock", False, False),
]


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def convert(text, col):
    if col in INTEGER_COLUMNS:
        return int(text or 0)
    if col in REAL_COLUMNS:
        return float(text) if text else None
    return text


def build_sqlite(config, tables):
    db_path = ROOT / config["db_file"]
    # Rebuild inside the existing file rather than delete + recreate: a running KiCad keeps the .sqlite
    # open (which blocks deletion on Windows), but SQLite copes with a writer next to KiCad's reader.
    con = sqlite3.connect(db_path, timeout=15)
    try:
        for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
            con.execute(f'DROP TABLE IF EXISTS "{name}"')
        fill_tables(con, config, tables)
        con.commit()
        try:
            con.execute("VACUUM")
        except sqlite3.OperationalError:
            print("  (VACUUM skipped: file in use by KiCad; size will shrink on a later build)")
    except sqlite3.OperationalError as err:
        if "locked" in str(err):
            raise SystemExit(f"{db_path.name} is locked by another program (KiCad?). Close it and re-run build_db.py.") from err
        raise
    finally:
        con.close()
    return db_path


def fill_tables(con, config, tables):
    built = time.strftime("%Y-%m-%d")
    for table, sub, rows in tables:
        defs = []
        for col in COLUMNS:
            sql_type = "INTEGER" if col in INTEGER_COLUMNS else "REAL" if col in REAL_COLUMNS else "TEXT"
            defs.append(f'"{col}" {sql_type}' + (" PRIMARY KEY" if col == "Part_ID" else " NOT NULL"))
        con.execute(f'CREATE TABLE "{table}" ({", ".join(defs)})')
        placeholders = ", ".join("?" * len(COLUMNS))
        con.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', [[convert(row[col], col) for col in COLUMNS] for row in rows])

    con.execute('CREATE TABLE "library_info" ("table_name" TEXT PRIMARY KEY, "library" TEXT, "kind" TEXT, "description" TEXT, "parts" INTEGER, "built" TEXT)')
    con.executemany('INSERT INTO "library_info" VALUES (?, ?, ?, ?, ?, ?)',
                    [(table, sub["name"], sub["kind"], sub["description"], len(rows), built) for table, sub, rows in tables])
    per_series = Counter(row["Series"] for _, _, rows in tables for row in rows)
    con.execute('CREATE TABLE "series_info" ("series_id" TEXT PRIMARY KEY, "series" TEXT, "standard" TEXT, "manufacturer" TEXT, "product_line" TEXT, "series_datasheet" TEXT, "parts" INTEGER)')
    con.executemany('INSERT INTO "series_info" VALUES (?, ?, ?, ?, ?, ?, ?)',
                    [(s["id"], s["series_name"], s["standard"], s["manufacturer"], s["product_line"], s["series_datasheet"], per_series[s["series_name"]]) for s in config["series"]])


def field_entry(column, visible_on_add, visible_in_chooser):
    return {
        "column": column,
        "name": FIELD_NAMES[column],
        "visible_on_add": visible_on_add,
        "visible_in_chooser": visible_in_chooser,
        "show_name": False,
        "inherit_properties": column == "Datasheet",
    }


def build_dbl(config, tables):
    libraries = []
    for table, sub, _ in tables:
        fields = [{"column": "Value", "name": "Value", "visible_on_add": True, "visible_in_chooser": True, "show_name": False, "inherit_properties": True}]
        fields += [field_entry(*f) for f in KIND_FIELDS[sub["kind"]] + COMMON_FIELDS]
        libraries.append({
            "name": sub["name"],
            "table": table,
            "key": "Part_ID",
            "symbols": "Symbol",
            "footprints": "Footprint",
            "fields": fields,
            "properties": {"description": "Description", "keywords": "Keywords"},
        })
    dbl = {
        "meta": {"version": 0},
        "name": config["dbl_name"],
        "description": "SSI Satellites approved passive series, grouped by kind and JLCPCB fee class. "
                       "Generated by scripts/build_db.py from csv/ - do not edit by hand.",
        # Part_IDs are unique across all tables, so schematics link to LIB:Part_ID and a part may move
        # between sub-libraries (e.g. JLCPCB reclassifies it Basic -> Extended) without breaking links.
        "globally_unique_keys": True,
        "source": {
            "type": "odbc",
            "dsn": "",
            "username": "",
            "password": "",
            "timeout_seconds": 5,
            # ${CWD} is expanded by KiCad to the folder containing this .kicad_dbl file.
            "connection_string": f"Driver={{SQLite3 ODBC Driver}};Database=${{CWD}}/{config['db_file']};",
        },
        "libraries": libraries,
    }
    path = ROOT / config["dbl_file"]
    path.write_text(json.dumps(dbl, indent=2) + "\n", encoding="utf-8")
    return path, dbl


def verify(dbl, tables):
    """Check what KiCad will see: globally unique keys, well-formed lib references, and a live ODBC round trip."""
    all_ids = [row["Part_ID"] for _, _, rows in tables for row in rows]
    assert len(set(all_ids)) == len(all_ids), "Part_ID not unique across the library"
    for _, _, rows in tables:
        for row in rows:
            for col in ("Symbol", "Footprint"):
                assert row[col].count(":") == 1 and "/" not in row[col], f"bad {col} {row[col]!r} for {row['Part_ID']}"
            assert row["Value"] and row["LCSC"].startswith("C"), f"bad row {row['Part_ID']}"
    print("  structure OK: Part_IDs unique across all tables, Symbol/Footprint are Lib:Name, every row has Value and LCSC")

    connection_string = dbl["source"]["connection_string"].replace("${CWD}", str(ROOT).replace("\\", "/"))
    try:
        import pyodbc
    except ImportError:
        print("  ODBC check skipped (pip install pyodbc to enable)")
        return
    try:
        con = pyodbc.connect(connection_string, autocommit=True, timeout=5)
    except pyodbc.Error as err:
        print(f"  ODBC connection FAILED: {err}\n  -> install the SQLite3 ODBC Driver (see README) and re-run")
        return
    cur = con.cursor()
    for lib in dbl["libraries"]:
        (count,) = cur.execute(f'SELECT COUNT(*) FROM "{lib["table"]}"').fetchone()
        sample = cur.execute(f'SELECT "{lib["key"]}", "{lib["footprints"]}" FROM "{lib["table"]}" ORDER BY "Stock" DESC LIMIT 1').fetchone()
        print(f"  ODBC OK  {count:5d} rows  {lib['name']:<32} e.g. {sample[0]!r} -> {sample[1]}")
    con.close()


def main():
    config = json.loads((ROOT / "series.json").read_text(encoding="utf-8"))
    tables = [(table, sub, read_csv(CSV_DIR / f"{table}.csv")) for table, sub in config["sublibraries"].items()]
    db_path = build_sqlite(config, tables)
    dbl_path, dbl = build_dbl(config, tables)
    total = sum(len(rows) for _, _, rows in tables)
    print(f"wrote {db_path.name} ({db_path.stat().st_size // 1024} KB, {total} parts in {len(tables)} sub-libraries) and {dbl_path.name}")
    verify(dbl, tables)


if __name__ == "__main__":
    main()
