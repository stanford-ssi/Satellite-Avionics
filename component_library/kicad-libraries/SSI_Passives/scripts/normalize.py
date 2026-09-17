"""Turn raw JLCPCB part records into normalized library rows.

Everything that understands JLCPCB's attribute strings ("4.7kΩ", "±10%", "62.5mW") or decides
which KiCad footprint a part gets lives here, so build_csv.py only has to apply series rules.
"""

import math
import re
from math import inf

# Column order of the CSV files and of the SQLite tables.
COLUMNS = [
    "Part_ID", "Value", "LCSC", "LCSC_Type", "MPN", "Manufacturer", "Series", "Package",
    "Tolerance", "Power", "Voltage", "Dielectric", "Current", "Isat", "DCR", "TempCo",
    "Value_Series", "Standard", "Use_Case", "Symbol", "Footprint", "Datasheet", "LCSC_URL",
    "Description", "Keywords", "Stock", "Unit_Price_USD",
]

SYMBOLS = {"R": "Device:R", "C": "Device:C", "L": "Device:L"}
KIND_WORD = {"R": "Resistor", "C": "Capacitor", "L": "Inductor"}

E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1]
E96 = [
    1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24, 1.27, 1.30, 1.33, 1.37, 1.40, 1.43,
    1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74, 1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10,
    2.15, 2.21, 2.26, 2.32, 2.37, 2.43, 2.49, 2.55, 2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09,
    3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12, 4.22, 4.32, 4.42, 4.53,
    4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49, 5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65,
    6.81, 6.98, 7.15, 7.32, 7.50, 7.68, 7.87, 8.06, 8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76,
]

SI_PREFIX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}
QUANTITY_RE = re.compile(r"^\s*(\d*\.?\d+)\s*([pnuµμmkKMG])?\s*([A-Za-zΩ]*)\s*$")

# Which SI prefixes a formatted value may use, per unit, largest first.
LADDERS = {
    "Ω": (("M", 1e6), ("k", 1e3), ("", 1.0), ("m", 1e-3)),
    "F": (("u", 1e-6), ("n", 1e-9), ("p", 1e-12)),
    "H": (("m", 1e-3), ("u", 1e-6), ("n", 1e-9)),
    "W": (("", 1.0), ("m", 1e-3)),
    "V": (("", 1.0),),
    "A": (("", 1.0), ("m", 1e-3)),
}

# Imperial chip size -> KiCad metric suffix (Resistor_SMD:R_0402_1005Metric etc.).
CHIP_METRIC = {
    "01005": "0402", "0201": "0603", "0402": "1005", "0603": "1608", "0805": "2012", "1008": "2520",
    "1206": "3216", "1210": "3225", "1808": "4520", "1812": "4532", "2010": "5025", "2220": "5750",
    "2512": "6332", "0612": "1632", "1218": "3246",
}
CHIP_LIB = {"R": "Resistor_SMD:R_", "C": "Capacitor_SMD:C_", "L": "Inductor_SMD:L_"}

# Coilcraft XAL footprints shipped with KiCad (Inductor_SMD.pretty, checked 2026-09-16).
XAL_GENERIC = {"1010", "1030", "1060", "1350", "4020", "4030", "4040", "5020", "5030", "5050", "6020", "6030", "6060", "7050", "7070", "8080"}
XAL_PER_VALUE = {
    "1510": {"103", "153", "223", "333", "472", "682", "822"},
    "1513": {"153"},
    "1580": {"102", "132", "182", "202", "302", "401", "452", "532", "612", "741"},
    "7020": {"102", "122", "151", "152", "222", "271", "331", "471", "681"},
    "7030": {"102", "103", "152", "161", "222", "272", "301", "332", "472", "562", "601", "682", "822"},
    "8050": {"223"},
}
XAL_RE = re.compile(r"^XAL(\d{4})-?(\d{3})")
CERAMIC_FAMILY_RE = re.compile(r"^(\d{4})(CS|CT|DC|HC|HL|HP)")

# Vishay WSLP land patterns, datasheet 30122 rev 09-Sep-2024, "SOLDER PAD DIMENSIONS" table (mm).
# The terminal length depends on the resistance range, so one footprint per (size, range).
# Fields: package, footprint suffix, upper resistance bound (exclusive, Ω), body L, body W, pad length a, pad width b, gap l.
WSLP_LAND_PATTERNS = [
    ("0603", "", inf, 1.52, 0.76, 1.02, 1.02, 0.50),
    ("0805", "", inf, 2.03, 1.27, 1.02, 1.27, 0.50),
    ("1206", "_0m5-0m99", 0.001, 3.20, 1.60, 2.26, 1.93, 0.58),
    ("1206", "_1m-1m9", 0.002, 3.20, 1.60, 2.18, 1.93, 0.74),
    ("1206", "_2m-5m9", 0.006, 3.20, 1.60, 1.78, 1.93, 1.55),
    ("1206", "_6m-50m", inf, 3.20, 1.60, 1.65, 1.93, 1.80),
    ("2010", "_1m-6m9", 0.007, 5.08, 2.54, 2.36, 3.05, 1.40),
    ("2010", "_7m-30m", inf, 5.08, 2.54, 1.40, 3.05, 3.30),
    ("2512", "_0m5-4m9", 0.005, 6.35, 3.18, 3.05, 3.68, 1.27),
    ("2512", "_5m-6m9", 0.007, 6.35, 3.18, 2.11, 3.68, 3.18),
    ("2512", "_7m-10m", inf, 6.35, 3.18, 1.65, 3.68, 4.06),
]


def parse_quantity(text):
    """'4.7kΩ' -> 4700.0, '100nF' -> 1e-7, '62.5mW' -> 0.0625. None when text is not a plain quantity."""
    match = QUANTITY_RE.match(text or "")
    if not match:
        return None
    return float(match.group(1)) * SI_PREFIX[match.group(2) or ""]


def format_quantity(value, unit, omit_unit=False):
    """4700.0,'Ω' -> '4.7kΩ'; 1e-7,'F' -> '100nF'; 0.0625,'W' -> '62.5mW'."""
    if value is None:
        return ""
    suffix = "" if omit_unit else unit
    if value == 0:
        return "0" + suffix
    for prefix, scale in LADDERS[unit]:
        if value >= scale * 0.99999:
            break
    else:
        prefix, scale = LADDERS[unit][-1]
    number = f"{value / scale:.4g}"
    if "e" in number:
        number = f"{value / scale:.6f}".rstrip("0").rstrip(".")
    return f"{number}{prefix}{suffix}"


def value_series(value):
    """Classify a value as 'E24', 'E96', 'ZERO' or 'OTHER' (E24 is checked first; they overlap)."""
    if not value:
        return "ZERO"
    mantissa = value / 10 ** math.floor(math.log10(value))
    if mantissa > 9.99:
        mantissa = 1.0
    for name, table in (("E24", E24), ("E96", E96)):
        if any(abs(mantissa - v) <= v * 0.001 for v in table):
            return name
    return "OTHER"


def clean(text):
    text = (text or "").strip()
    return "" if text == "-" else text


def clean_tolerance(text):
    return clean(text).replace("±", "")


def lcsc_type(raw):
    if raw.get("componentLibraryType") == "base":
        return "Basic"
    return "Preferred" if raw.get("preferredComponentFlag") else "Extended"


def chip_footprint(kind, package):
    metric = CHIP_METRIC.get(package)
    return f"{CHIP_LIB[kind]}{package}_{metric}Metric" if metric else ""


def xal_footprint(mpn):
    """-> (package label, footprint or '') for a Coilcraft XAL part number."""
    match = XAL_RE.match(mpn)
    if not match:
        return "", ""
    size, code = match.groups()
    if size in XAL_GENERIC:
        return f"XAL{size}", f"Inductor_SMD:L_Coilcraft_XAL{size}-XXX"
    if code in XAL_PER_VALUE.get(size, ()):
        return f"XAL{size}", f"Inductor_SMD:L_Coilcraft_XAL{size}-{code}"
    return f"XAL{size}", ""


def wslp_footprint(footprint_lib, package, ohms):
    for pkg, suffix, upper, *_ in WSLP_LAND_PATTERNS:
        if pkg == package and ohms < upper * (1 - 1e-9):
            return f"{footprint_lib}:R_Vishay_WSLP{package}{suffix}"
    return ""


def normalize_part(series, raw, footprint_lib):
    """Build one library row from a raw JLCPCB record. Returns None if the record can't be parsed."""
    attrs = {a["attribute_name_en"]: a["attribute_value_name"] for a in (raw.get("attributes") or [])}
    kind = series["kind"]
    mpn = clean(raw.get("componentModelEn"))
    package = clean(raw.get("componentSpecificationEn"))
    tolerance = clean_tolerance(attrs.get("Tolerance"))
    row = dict.fromkeys(COLUMNS, "")
    row.update(Tolerance=tolerance, Package=package)

    if kind == "R":
        ohms = parse_quantity(attrs.get("Resistance"))
        if ohms is None or (ohms and not tolerance):
            return None
        if ohms == 0:
            tolerance = row["Tolerance"] = ""  # a jumper has no meaningful tolerance
        watts = parse_quantity(attrs.get("Power(Watts)"))
        row.update(
            Value=format_quantity(ohms, "Ω"),
            Power=format_quantity(watts, "W"),
            Voltage=clean(attrs.get("Voltage-Supply(Max)")),
            TempCo=clean(attrs.get("Temperature Coefficient")).replace("℃", "°C"),
        )
        magnitude = ohms
        part_id = " ".join(filter(None, ["R", format_quantity(ohms, "Ω", omit_unit=True), package, tolerance]))
        rating = row["Power"]
    elif kind == "C":
        farads = parse_quantity(attrs.get("Capacitance"))
        volts = parse_quantity(attrs.get("Voltage Rating"))
        dielectric = clean(attrs.get("Temperature Coefficient"))
        if farads is None or volts is None or not dielectric or not tolerance:
            return None
        row.update(Value=format_quantity(farads, "F"), Voltage=format_quantity(volts, "V"), Dielectric=dielectric)
        magnitude = farads
        part_id = f"C {row['Value']} {package} {row['Voltage']} {dielectric} {tolerance}"
        rating = f"{row['Voltage']} {dielectric}"
    elif kind == "L":
        henries = parse_quantity(attrs.get("Inductance"))
        if henries is None or not tolerance:
            return None
        row.update(
            Value=format_quantity(henries, "H"),
            Current=format_quantity(parse_quantity(attrs.get("Current Rating")), "A"),
            Isat=format_quantity(parse_quantity(attrs.get("Current - Saturation(Isat)") or attrs.get("Current - Saturation (Isat)")), "A"),
            DCR=format_quantity(parse_quantity(attrs.get("DC Resistance(DCR)")), "Ω"),
        )
        magnitude = henries
        family = CERAMIC_FAMILY_RE.match(mpn)
        part_id = f"L {row['Value']} {family.group(0) if family else package} {tolerance}"
        rating = row["Current"]
    else:
        raise ValueError(f"unknown kind {kind!r}")

    rule = series.get("footprint_rule", "chip")
    if rule == "chip":
        footprint = chip_footprint(kind, package)
    elif rule == "wslp":
        footprint = wslp_footprint(footprint_lib, package, magnitude)
    elif rule == "xal":
        package, footprint = xal_footprint(mpn)
        row["Package"] = package
        part_id = f"L {row['Value']} {package} {tolerance}"
    else:
        raise ValueError(f"unknown footprint_rule {rule!r}")

    price = (raw.get("componentPrices") or [{}])[0].get("productPrice", "")
    ltype = lcsc_type(raw)
    row.update(
        Part_ID=part_id,
        LCSC=raw["componentCode"],
        LCSC_Type=ltype,
        MPN=mpn,
        Manufacturer=series["manufacturer"],
        Series=series["series_name"],
        Value_Series=value_series(magnitude),
        Standard=series["standard"],
        Use_Case=series["use_case"],
        Symbol=SYMBOLS[kind],
        Footprint=footprint,
        Datasheet=clean(raw.get("dataManualUrl")) or series["series_datasheet"],
        LCSC_URL=clean(raw.get("lcscGoodsUrl")) or f"https://www.lcsc.com/product-detail/{raw['componentCode']}.html",
        Description=" ".join(filter(None, [
            KIND_WORD[kind], row["Value"], tolerance, rating, row["Package"], series["product_line"] + ",",
            series["manufacturer"], mpn, f"({series['standard']}, LCSC {ltype})",
        ])),
        Keywords=" ".join(filter(None, [
            KIND_WORD[kind].lower(), row["Value"], row["Package"], series["manufacturer"].lower(),
            series["series_name"].lower(), series["standard"].lower(), series["use_case"].lower(),
        ])),
        Stock=int(raw.get("stockCount") or 0),
        Unit_Price_USD=price,
    )
    # Part_ID is still the bare "<kind> <value> <package> <rating>" here; build_csv appends the series tag
    # (and a tiebreaker if needed) so it is unique across the whole library.
    row["_tag"] = series["id_tag"]
    row["_kind"] = kind
    row["_sort"] = (row["Package"], magnitude, tolerance, row["Voltage"], mpn)
    return row
