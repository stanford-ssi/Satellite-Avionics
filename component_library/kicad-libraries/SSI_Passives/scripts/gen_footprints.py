"""Generate the custom footprints KiCad does not ship: Vishay WSLP current-sense resistors.

Writes SSI_Passives.pretty/R_Vishay_WSLP*.kicad_mod from the pad table in normalize.WSLP_LAND_PATTERNS
(taken from Vishay datasheet 30122). Deterministic output, so re-running produces no git noise.

Usage:
    python scripts/gen_footprints.py
"""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize import WSLP_LAND_PATTERNS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NAMESPACE = uuid.UUID("6f1b5e0a-3c1d-4d7e-9b2a-0a1b2c3d4e5f")

SILK_WIDTH = 0.12
FAB_WIDTH = 0.10
COURTYARD_WIDTH = 0.05
COURTYARD_CLEARANCE = 0.25
SILK_PAD_CLEARANCE = 0.20


def uid(*parts):
    return str(uuid.uuid5(NAMESPACE, "/".join(str(p) for p in parts)))


def fmt(value):
    return f"{value:.3f}".rstrip("0").rstrip(".") if value else "0"


def wslp_footprint(package, suffix, upper, body_l, body_w, pad_a, pad_b, gap):
    name = f"R_Vishay_WSLP{package}{suffix}"
    pad_x = gap / 2 + pad_a / 2
    extent_x = max(body_l / 2, pad_x + pad_a / 2)
    extent_y = max(body_w / 2, pad_b / 2)
    cy_x, cy_y = extent_x + COURTYARD_CLEARANCE, extent_y + COURTYARD_CLEARANCE
    silk_y = body_w / 2 + SILK_WIDTH / 2 + 0.05
    silk_x = gap / 2 - SILK_PAD_CLEARANCE
    text_y = cy_y + 0.8
    ohm_range = suffix.strip("_").replace("m", " mΩ").replace("-", " to ") if suffix else "full range"
    # Radius ~0.25 mm on a roundrect pad (ratio is relative to the shorter pad side).
    rratio = round(min(0.25, 0.25 / min(pad_a, pad_b)), 4)

    lines = [
        f'(footprint "{name}"',
        "\t(version 20240108)",
        '\t(generator "ssi_gen_footprints")',
        '\t(generator_version "1.0")',
        '\t(layer "F.Cu")',
        f'\t(descr "Vishay WSLP{package} Power Metal Strip current sense resistor, {ohm_range}, body {fmt(body_l)}x{fmt(body_w)}mm, '
        f'pads {fmt(pad_a)}x{fmt(pad_b)}mm gap {fmt(gap)}mm per Vishay doc 30122 rev 09-Sep-2024 (https://www.vishay.com/docs/30122/wslp.pdf)")',
        f'\t(tags "resistor shunt current sense WSLP{package} vishay")',
        prop("Reference", "REF**", 0, -text_y, "F.SilkS", uid(name, "ref")),
        prop("Value", name, 0, text_y, "F.Fab", uid(name, "val")),
        prop("Footprint", "", 0, 0, "F.Fab", uid(name, "fp"), hide=True),
        prop("Datasheet", "", 0, 0, "F.Fab", uid(name, "ds"), hide=True),
        prop("Description", "", 0, 0, "F.Fab", uid(name, "desc"), hide=True),
        "\t(attr smd)",
    ]
    if silk_x > 0.3:
        for sign in (-1, 1):
            lines.append(line(-silk_x, sign * silk_y, silk_x, sign * silk_y, "F.SilkS", SILK_WIDTH, uid(name, "silk", sign)))
    lines.append(rect(-cy_x, -cy_y, cy_x, cy_y, "F.CrtYd", COURTYARD_WIDTH, uid(name, "crtyd")))
    lines.append(rect(-body_l / 2, -body_w / 2, body_l / 2, body_w / 2, "F.Fab", FAB_WIDTH, uid(name, "fab")))
    ref_size = max(0.5, min(1.0, body_w * 0.6))
    lines += [
        f'\t(fp_text user "${{REFERENCE}}"',
        "\t\t(at 0 0 0)",
        "\t\t(unlocked yes)",
        '\t\t(layer "F.Fab")',
        f'\t\t(uuid "{uid(name, "reftext")}")',
        f"\t\t(effects (font (size {fmt(ref_size)} {fmt(ref_size)}) (thickness {fmt(ref_size * 0.15)})))",
        "\t)",
    ]
    for number, sign in (("1", -1), ("2", 1)):
        lines += [
            f'\t(pad "{number}" smd roundrect',
            f"\t\t(at {fmt(sign * pad_x)} 0)",
            f"\t\t(size {fmt(pad_a)} {fmt(pad_b)})",
            '\t\t(layers "F.Cu" "F.Paste" "F.Mask")',
            f"\t\t(roundrect_rratio {rratio})",
            f'\t\t(uuid "{uid(name, "pad", number)}")',
            "\t)",
        ]
    lines.append(")")
    return name, "\n".join(lines) + "\n"


def prop(key, value, x, y, layer, uuid_, hide=False):
    return "\n".join([
        f'\t(property "{key}" "{value}"',
        f"\t\t(at {fmt(x)} {fmt(y)} 0)",
        "\t\t(unlocked yes)",
        f'\t\t(layer "{layer}")',
        *(["\t\t(hide yes)"] if hide else []),
        f'\t\t(uuid "{uuid_}")',
        "\t\t(effects (font (size 1 1) (thickness 0.15)))",
        "\t)",
    ])


def line(x1, y1, x2, y2, layer, width, uuid_):
    return (f"\t(fp_line (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)}) "
            f'(stroke (width {width}) (type solid)) (layer "{layer}") (uuid "{uuid_}"))')


def rect(x1, y1, x2, y2, layer, width, uuid_):
    return (f"\t(fp_rect (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)}) "
            f'(stroke (width {width}) (type solid)) (fill none) (layer "{layer}") (uuid "{uuid_}"))')


def main():
    config = json.loads((ROOT / "series.json").read_text(encoding="utf-8"))
    out_dir = ROOT / f"{config['footprint_lib']}.pretty"
    out_dir.mkdir(exist_ok=True)
    for pattern in WSLP_LAND_PATTERNS:
        name, text = wslp_footprint(*pattern)
        (out_dir / f"{name}.kicad_mod").write_text(text, encoding="utf-8")
        print(f"  {out_dir.name}/{name}.kicad_mod")
    print(f"wrote {len(WSLP_LAND_PATTERNS)} footprints")


if __name__ == "__main__":
    main()
