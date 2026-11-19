# SSI_Passives_v2 — curated approved parts (plain KiCad library)

A hand-picked list of the parts the Satellites Avionics team has approved for current designs.
Every part carries its footprint, MPN, manufacturer, datasheet and ratings, so a schematic built
from it is orderable as-is from Mouser or DigiKey. It's a plain KiCad symbol library: no database,
no ODBC driver, no scripts.

```
SSI_Passives_v2/
├─ SSI_Passives_v2.kicad_sym    symbols (one per approved part)
├─ SSI_Passives_v2.pretty/      footprints KiCad doesn't ship (Vishay WSLP1206)
└─ README.md
```

## Parts

| Kind | Series | Notes |
|---|---|---|
| Capacitors | TDK CGA (automotive, AEC-Q200) | X7R, C0G for 15 pF. 1206 max. |
| Resistors | Vishay TNPW e3 (thin film, AEC-Q200) | 0402, 25 ppm/°C |
| Current sense | Vishay WSLP1206 | 20 mΩ, 1 W |
| Inductors | Coilcraft XAL4030, Abracon AOTA-B201610 | Abracon has no footprint assigned yet |
| Test point | Keystone 5015 | SMT miniature, silver plated |

Symbol names read `<kind>_<value>_<package>_<rating>`, e.g. `C_100nF_0402_50V_X7R`, `R_10k_0402_TNPW`.
Press **A** in the schematic editor and type `100nF` or `10k` to find a part.

Fields on every part: Value, Footprint, Datasheet, Description, MPN, Manufacturer, plus ratings
(Voltage / Dielectric / Tolerance for caps, Tolerance / TempCo / Power for resistors, Isat / DCR for inductors).

## One-time setup (every team member)

1. Clone or pull this repo.
2. KiCad → Preferences → Configure Paths: add `SSI_PASSIVES_V2` = the path of this folder
   (the one containing `SSI_Passives_v2.kicad_sym`).
3. Preferences → Manage Symbol Libraries → Global Libraries → add a row:
   Nickname `SSI_Passives_v2`, Library Path `${SSI_PASSIVES_V2}/SSI_Passives_v2.kicad_sym`, Format KiCad.
4. Preferences → Manage Footprint Libraries → Global Libraries → add a row:
   Nickname `SSI_Passives_v2` (must be exactly this; symbols refer to `SSI_Passives_v2:R_Vishay_WSLP…`),
   Library Path `${SSI_PASSIVES_V2}/SSI_Passives_v2.pretty`, Format KiCad.

KiCad's standard libraries (`Capacitor_SMD`, `Resistor_SMD`, `Inductor_SMD`, `TestPoint`) must stay enabled;
most parts use their footprints.

## Adding a part

1. Open the library in the Symbol Editor, copy the closest existing part, and rename it.
2. Fill in Value, Footprint, Datasheet, Description, MPN, Manufacturer and the rating fields.
3. Check the part meets CL-000001 (series, dielectric, derating, size, tin finish) and is in stock.
4. Commit and open a pull request; reviewers check the new symbol's fields.

Keep field names identical (`MPN`, `Manufacturer`) so BOM exports stay consistent.

## Relationship to SSI_Passives (v1)

SSI_Passives is the JLCPCB-oriented database library. SSI_Passives_v2 is for designs built on our own
pick-and-place and bought from Mouser/DigiKey. Use SSI_Passives_v2 for new designs; v1 stays for JLCPCB-assembled prototypes.
