# TPS54426 — 4 A buck converter (battery → 5 V)

**Datasheet:** [`datasheets-only/ICs/POWER/TPS54426/`](../../../../../datasheets-only/ICs/POWER/TPS54426/) (TI, 4.5–18 V in, 4 A synchronous step-down)
**Extracted from:** `samwise-avionics/RPi_Interface/RPi_interface.kicad_sch` (U1, "RPi Payload Power Converter")

## What it is, in basic terms
A **buck converter** is a switching regulator that steps a higher voltage *down* to a lower one
efficiently (typically 85–95 %), unlike an LDO which burns the excess as heat. The TPS54426 has both
power switches built in (it's "synchronous"), takes **4.5–18 V in**, delivers up to **4 A**, and
switches at about **700 kHz**. It uses TI's **D-CAP2** control, which responds fast to load steps and
works with small ceramic output capacitors, and **Eco-mode**, which skips pulses at light load to save
power. It has an enable pin, adjustable soft-start, and a power-good output.

Output voltage is set by two resistors:

> V<sub>OUT</sub> = 0.765 V × (1 + R3/R4) = 0.765 × (1 + 121k/22.1k) ≈ **4.95 V**

## What it did on SAMWISE
It powered the **Raspberry Pi + camera payload** on the RPi Interface board, converting the battery
bus (`VBATT`) to `5V`. PiCubed turns it on with `ENAB_RPI`, so the payload can be fully switched off.
It shares the input capacitors C3/C4 with the radio's TPS7A4501 LDO (see the
[TT&C TPS7A4501 block](../../../TT%26C/TT%26C.kicad_blocks/TPS7A4501.kicad_block/README.md)).

## What is in the block
| Ref | Value | Job |
|-----|-------|-----|
| U1 | TPS54426PWPR (HTSSOP-14) | The buck converter |
| L1 | 3.3 µH | Power inductor between SW and the 5 V output |
| C1, C2 | 22 µF each | Output capacitors on `5V` |
| C3, C4 | 47 µF each | Input capacitors on `VBATT` — deliberately larger than the datasheet asks, to ride through radio-LDO inrush (schematic note) |
| C5 | 0.1 µF | Bootstrap capacitor (VBST → SW) that powers the high-side switch's gate driver |
| C6 | 3.3 nF | Soft-start capacitor: t<sub>SS</sub> ≈ 3.3 nF × 0.765 V / 2 µA ≈ **1.3 ms** ramp, limiting inrush at turn-on |
| C7 | 1 µF | Decoupling for the internal 5 V regulator (VREG5) |
| R3 / R4 | 121 kΩ / 22.1 kΩ | Feedback divider setting ~4.95 V |
| C11 | 22 pF | Feed-forward cap across R3 — improves transient response / stability |
| R2 | 330 kΩ | Pull-down on EN so the Pi stays **off** when PiCubed is unpowered (~33 µW) |
| R5 | 100 kΩ | Pull-up on PG (power-good) to VREG5 |

## How it is wired
| Net | Pin(s) | Notes |
|-----|--------|-------|
| `VBATT` | 13, 14 (VIN1/2) | 4.5–18 V battery bus |
| `5V` | 1 (VO) + L1 output | ~4.95 V to the Raspberry Pi |
| `ENAB_RPI` | 7 (EN) | High (>1.5 V) = on; from PiCubed |
| — | 10, 11 (SW1/2) | Switch node → L1, and C5 to VBST (12) |
| — | 2 (VFB) | R3/R4 divider + C11 |
| — | 4 (SS) | C6 to GND |
| — | 3 (VREG5) | C7; also R5 pull-up for PG |
| — | 6 (PG) | Pulled up by R5; not routed off-board in SAMWISE |
| GND | 5 (GND), 8–9 (PGND), 15 (EPAD) | Schematic note: keep signal ground (GND) and power ground (PGND) separate on the PCB and join them at one point, per the datasheet |

## Notes for reusing this
- **Layout matters more than the schematic** for a buck: keep the VIN caps → IC → PGND loop and the
  SW node tiny, put the feedback divider next to VFB away from SW and L1, and lots of vias under EPAD.
- Rated –40 to +85 °C (commercial). TI has newer parts with similar ratings but higher efficiency,
  lower quiescent current, or spread-spectrum for EMI. Check these before reusing it; the upgrade
  research covers candidates.
- Route PG to the MCU if you want the flight computer to know the payload rail is up.
