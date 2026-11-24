# MMC5983MA magnetometer (Janus)

MEMSIC MMC5983MA 3-axis AMR magnetometer (±8 G, 18-bit), 4-wire SPI. Backup magnetometer to the RM3100.

- Interface: 4-wire SPI up to 10 MHz (SCK idles high, mode 3), INT active-high (hi-Z until enabled).
- Power: VDD = VDDIO = 3V3 (2.8–3.6 V, supply rise <= 5 ms). C1 >= 10 µF low-ESR at CAP (pin 10,
  SET/RESET supply, internally tied to VDD); 1 µF + 100 nF on the supply.
- Connector J1: kept generic (7-pin placeholder, no footprint). Recommended: **Harwin Gecko
  1.25 mm latching 2x5** for flight, **JST GH 1.25 mm** for dev/EM. Planned 10-pin pinout:
  3V3, GND, SCK, GND, SDI, SDO, GND, ~CS, INT, GND. If this ends up on the OBC itself, drop J1.

Status: schematic complete, ERC clean (0 errors / 0 warnings), footprint assigned. Layout not started.
Owner: Marlon Moenius.

## Files

| File | Contents |
|---|---|
| `mmc5983ma.kicad_sch` | Schematic (single sheet), title block + design notes |
| `MEMSIC.kicad_sym` | Symbol: MMC5983MA |
| `MEMSIC.pretty/` | Footprint: LGA-16 3x3 mm P0.5 (same land as KiCad `Package_LGA:LGA-16_3x3mm_P0.5mm`, from MEMSIC) |

## Datasheet references

MEMSIC MMC5983MA Rev A — pin description table, SPI connection diagrams, layout notes
(keep current-carrying traces and magnetic parts away from/under the sensor).
TODO: add the PDF to `datasheets/` and re-check the SPI connection diagram figure against the schematic.
