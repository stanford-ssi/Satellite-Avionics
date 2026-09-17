# SSI Passives — KiCad database library for approved passive series

One KiCad library that contains **only the passive component series the SSI Satellites Avionics team
has approved** (see the *Component Library & Standards Guide*, CL-000001). Every entry is a real,
in-stock LCSC/JLCPCB part with its LCSC number, manufacturer part number, ratings, footprint and
datasheet — so a schematic built from it is orderable as-is, and BOM/placement files for JLCPCB come
straight out of the JLCPCB plugin.

Parts are grouped by kind and by **JLCPCB fee class**, because every distinct *Extended* part on an
order costs a $3 loading fee while *Basic* and *Preferred* parts are free:

```
SSI_Passives
├─ R Basic - no fee               Uniroyal thick film (+ any WSLP that JLCPCB lists as Basic/Preferred)
├─ R Extended - 3 USD fee         Uniroyal thick film, Vishay WSLP current sense
├─ C Basic - no fee               Samsung CL MLCC
├─ C Extended - 3 USD fee         Samsung CL MLCC
├─ L Power - Coilcraft XAL        molded power inductors (all Extended)
├─ L RF - Coilcraft Ceramic Core  0402/0603/0805/1008/1206 CS/HP/DC/HL/HC/CT (all Extended)
├─ R Flight - Vishay TNPW         thin film e3 (all Extended)
└─ C Flight - TDK CGA             automotive MLCC (all Extended)
```

Part names read `<kind> <value> <package> <ratings> <series>`, e.g. `R 10k 0603 1% Uniroyal`,
`C 100nF 0402 16V X7R 10% Samsung`, `L 2.2uH XAL4020 20% Coilcraft`, `L 33nH 0402CS 5% Coilcraft`,
`R 10m 2512 1% Vishay WSLP`. Type `10k 0603` in KiCad's symbol chooser and it filters straight to the part. Fields on every part: Value,
Package, LCSC, LCSC Type (Basic / Preferred / Extended), MPN, Series, Manufacturer, Standard, Value
Series (E24/E96), Datasheet, LCSC URL, Stock, plus kind-specific ratings (Tolerance, Power, TempCo,
Voltage / Dielectric / Current, Isat, DCR).

## How it works

```
series.json               rules: the approved series, how to recognise their part numbers, what to keep,
                          and which sub-library each series feeds (split by fee class for pre-flight R and C)
scripts/fetch_parts.py    1. JLCPCB search API  -> raw/<series>.json        (needs network; raw/ is git-ignored)
scripts/build_csv.py      2. raw + rules        -> csv/<sub-library>.csv    (reviewable: one row = one LCSC part)
scripts/build_db.py       3. csv                -> SSI_Passives.sqlite + SSI_Passives.kicad_dbl, then verifies via ODBC
scripts/gen_footprints.py 4. datasheet pad table-> SSI_Passives.pretty/     (WSLP footprints KiCad doesn't ship)
scripts/build.py          runs 2-4 (add --fetch to run 1 first)
```

KiCad's *database library* feature reads the `.kicad_dbl` file, which says "sub-library X is table Y,
column Z is field W", and pulls the rows from the `.sqlite` file through an ODBC driver. KiCad never
writes to it: the library is read-only in KiCad and changes go through this repo (edit rules → rebuild →
pull request → everyone pulls).

**Why SQLite?** KiCad's database libraries need a SQL database. SQLite is a complete database engine
that stores everything in one ordinary file (`SSI_Passives.sqlite`, ~3 MB). No server to run or host,
nothing to log in to, works offline, and the file can be committed to git like any other. The only
thing each machine needs is the small ODBC driver KiCad uses to open it. The alternatives (MySQL,
PostgreSQL) would need a server somebody keeps running for the whole team.

**Parts can move between sub-libraries.** JLCPCB reclassifies parts over time, so after a refresh a
part may move from `R Basic` to `R Extended` (or back). Part names are unique across the whole library
and the `.kicad_dbl` sets `globally_unique_keys`, so schematics link to `SSI_Passives:<Part name>` and
keep working when that happens. Always check the JLCPCB plugin's fee column before ordering.

## One-time setup (every team member)

1. **Install the SQLite ODBC driver** (KiCad talks to SQLite through it).
   - Windows: run `sqliteodbc_w64.exe` from <http://www.ch-werner.de/sqliteodbc/> (the driver the
     KiCad docs recommend; installs "SQLite3 ODBC Driver"). Needs admin.
   - macOS: `brew install sqliteodbc` and register the driver in `~/.odbcinst.ini` **under the name
     `SQLite3 ODBC Driver`** so the shared connection string works unchanged
     (see <https://cdwilson.dev/articles/kicad-database-libraries-on-macos/>).
   - Linux: install `libsqliteodbc` / `sqliteodbc` from your distro, same driver-name note.
2. **Get the library**: clone (or pull) the repo containing this folder.
3. **KiCad → Preferences → Configure Paths**: add `SSI_LIB` = the path of this folder
   (the one containing `SSI_Passives.kicad_dbl`).
4. **Preferences → Manage Symbol Libraries → Global Libraries** → click **+** (add empty row), then fill
   the cells by typing (the folder-browse button cannot pick a `.kicad_dbl` file):
   Nickname `SSI_Passives`, Library Path `${SSI_LIB}/SSI_Passives.kicad_dbl`, Library Format **Database**
   (click the cell to get the dropdown).
5. **Preferences → Manage Footprint Libraries → Global Libraries** → add a row:
   Nickname **`SSI_Passives`** (must be exactly this — the database refers to
   `SSI_Passives:R_Vishay_WSLP…`), Library Path `${SSI_LIB}/SSI_Passives.pretty`, Format KiCad.
6. Restart KiCad. In the schematic editor press **A** (Add Symbol): the tree shows `SSI_Passives` with
   the eight sub-libraries; the chooser columns show Value, Package, LCSC, LCSC Type, Series and ratings.

Everything else (Device:R/C/L symbols, chip footprints, Coilcraft XAL footprints) comes from KiCad's
standard libraries, which must stay enabled.

## Using it

- Place parts from `SSI_Passives` instead of `Device:R` etc. The LCSC field is filled in, so the
  [kicad-jlcpcb-tools](https://github.com/bouni/kicad-jlcpcb-tools) plugin picks it up for BOM/CPL.
- For prototypes, start in the **Basic** sub-library and only go to **Extended** when the value isn't
  there; prefer **Value Series = E24** as the standards guide asks.
- Flight series are separate sub-libraries so a prototype can't accidentally pull a flight part.
- KiCad caches the library when the chooser first opens; **restart KiCad after pulling an update**.
  Existing schematics keep their old field values until you run *Tools → Update Symbols from Library*.

## Maintaining the library

Refreshing stock / fee classes / new parts, or changing the rules:

```bash
python scripts/build.py --fetch      # ~5 min: download, filter, rebuild db + dbl + footprints
```

Then review `git diff csv/` (that is the human-readable change set), commit `csv/`, `SSI_Passives.sqlite`,
`SSI_Passives.kicad_dbl` and `SSI_Passives.pretty/` together, and open a pull request. Rebuilding while
KiCad is open is fine (KiCad keeps the `.sqlite` open, so the tables are rewritten in place); KiCad
shows the new data after a restart.

[`series.json`](series.json) has two parts:

- `sublibraries` — the tables KiCad sees: key (SQLite table name), `name` shown in KiCad, `kind`
  (R/C/L), `description`. Don't rename a sub-library key or change how part names are formed once boards
  use the library.
- `series` — one object per approved manufacturer series:

| Key | Meaning |
|-----|---------|
| `id`, `series_name`, `id_tag` | raw-file name, the `Series` field, and the tag appended to part names |
| `sublibrary` | where selected parts go: a table key, or `{"no_fee": …, "fee": …}` to split by JLCPCB class |
| `queries` | JLCPCB search filters (brand, category, keyword) that fetch the raw candidates |
| `mpn_regex` | part-number pattern that defines the series (e.g. Uniroyal size + power code) |
| `packages` | chip sizes to keep |
| `tolerances`, `value_series`, `min_stock` | further narrowing; `value_series` is any of `E24`, `E96`, `ZERO` |
| `exclude_lcsc` | LCSC numbers to drop by hand (bad datasheets, obsolete, etc.) |
| `footprint_rule` | `chip` (KiCad `R_/C_/L_<size>_<metric>Metric`), `xal` (KiCad Coilcraft XAL footprints), `wslp` (this repo's footprints, chosen by resistance range) |

When several LCSC parts have the same spec (same value, package, tolerance, rating), one is kept:
Basic before Preferred before Extended, then the deepest stock. Parts whose footprint KiCad doesn't have
are dropped and listed by `build_csv.py` so a footprint can be added to `SSI_Passives.pretty/`.

Adding a series = add an object to `series` (copy the closest one), point `sublibrary` at an existing
table or add a new one, and rebuild.

Scripts need Python 3.10+ and only the standard library; `pip install pyodbc` enables the end-to-end
ODBC check in `build_db.py` (recommended on the machine that builds).

## Data source

Part data comes from JLCPCB's public parts search (the same endpoint behind <https://jlcpcb.com/parts>),
which is what community tools such as jlcparts and kicad-jlcpcb-tools use. It is unofficial; the fetch
script is deliberately slow (1000 parts per request, 2 s pause) and only runs when someone refreshes the
library. Stock, price and fee class are a snapshot from the fetch date (`library_info` / `series_info`
tables in the database record what was built).
