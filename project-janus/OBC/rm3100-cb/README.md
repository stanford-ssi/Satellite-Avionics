# RM3100-CB magnetometer (Janus) — chip-level recreation

Recreation of the PNI RM3100-CB sensor suite (MagI2C ASIC, 2x Sen-XY-f, 1x Sen-Z-f) in SPI mode,
as a standalone schematic with its own symbols and footprints. Kept separate from `../rm3100/`
(PR #41) so the two can be compared before one is chosen for the remote board.

- Interface: SPI (I2CEN tied low), mode 0 or 3, MSB first, SCLK <= 1 MHz, plus DRDY.
- Power: single 3V3 rail (2.0–3.6 V) on AVDD/DVDD, 10 µF + 100 nF ceramic decoupling.
- Connector J1: kept generic (7-pin placeholder, no footprint). Recommended: **Harwin Gecko
  1.25 mm latching 2x5** for flight, **JST GH 1.25 mm** for dev/EM. Planned 10-pin pinout with
  interleaved grounds: 3V3, GND, SCLK, GND, MOSI, MISO, GND, ~CS, DRDY, GND. Check the mated
  connector's magnetic signature near the coils before flight.

Status: schematic complete, ERC clean (0 errors / 0 warnings), footprints assigned. Layout not started.
Owner: Marlon Moenius.

## Files

| File | Contents |
|---|---|
| `rm3100-cb.kicad_sch` | Schematic (single sheet), title block + design notes |
| `PNI_RM3100.kicad_sym` | Symbols: MagI2C, Sen-XY-f, Sen-Z-f |
| `PNI_RM3100.pretty/` | Footprints: MagI2C MLF-28 4x4 P0.4 (no EP land), Sen-XY-f, Sen-Z-f |

## Datasheet references

Datasheet: `../rm3100/datasheets/RM3100_1017252_r06.pdf` (PNI Doc 1017252 r06).

- Circuit: SPI reference schematic Fig. 4-1 (p. 15) — R_bias 121 Ω x6 (xDRVP–R–xINP–coil–xINN–R–xDRVN),
  R_EXT 33 kΩ to GND, RES (2, 20) and I2CEN (22) to GND, NC (21, 24) floating. Values: Table 3-1.
- Footprints: Sen-XY-f Fig. 3-3 (pads 1.40x1.70 @ 5.80 c-c, paste 0.60x1.20, mask +0.125);
  Sen-Z-f Fig. 3-6 (pads 2.40x1.95, 0.40 gap, paste 1.66x1.35 at inner edge, mask +0.125);
  MagI2C Fig. 3-7 (exposed die pad intentionally not landed — PNI: do not solder it).
- Sen-Z-f polarity: pad 2 / silk dot = polarity indicator = ZDRVN side (Fig. 4-4). Mounting the
  Z coil on the bottom side swaps the pads. Sen-XY-f is polarity-insensitive.
- Assembly: PNI coils need halide-free solder paste and processes (§3.5).
