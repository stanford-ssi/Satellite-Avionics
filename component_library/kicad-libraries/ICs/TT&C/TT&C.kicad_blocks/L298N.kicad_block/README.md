# L298N — H-bridge relay driver for the ground station RF path

**Datasheet:** [`datasheets-only/ICs/TT&C/L298N/`](../../../../../datasheets-only/ICs/TT%26C/L298N/) (ST L298)
**Extracted from:** `samwise-avionics/Groundstation_433_Hat/Groundstation_433_Hat.kicad_sch` (U1, the L298N module) + `433_hat_board.kicad_sch` (R1, R2 pull-downs)

## What it is, in basic terms
The ST **L298** is a **dual full H-bridge**: two pairs of high-current switches that can drive a load
in either direction (normally a DC motor or stepper). It runs loads up to **46 V** and about **2 A per
bridge**, from simple 5 V logic inputs (IN1–IN4) with an enable per bridge (ENA/ENB). SAMWISE used the
common red **"L298N module"** board, which adds an on-board 5 V regulator (enabled with the REG_EN
jumper), flyback diodes and screw terminals.

## What it did on SAMWISE
On the **433 MHz ground station** the L298N doesn't drive motors — it drives **coaxial RF relays**
from Raspberry Pi GPIOs, powered from the 13.8 V station supply:
- **Bridge A (OUT1/OUT2 → `RELAY+`/`RELAY–`):** flips two coax relays (in parallel) to switch the
  antenna between the **transmit** chain (PA) and the **receive** chain (LNA). Driven by `TX_CTRL`/`RX_CTRL`.
- **Bridge B (OUT3/OUT4 → `SDR_LORA+`/`SDR_LORA–`):** switches the RF path between the **LoRa
  transceiver** (the [RFM96W](../RFM96W.kicad_block/README.md)) and an **SDR** for debugging.
  Driven by `SDR_CTRL`/`LORA_CTRL`.

Using an H-bridge means each relay coil can be driven in **either polarity** (needed if the relays are
latching/dual-polarity; the schematic doesn't name the relay part, so confirm before reusing).

## What is in the block
| Ref | Value | Job |
|-----|-------|-----|
| U1 | L298N module | Dual H-bridge |
| R1 | 10 kΩ | Pull-down on `TX_CTRL` — relays stay de-energized while the Pi boots |
| R2 | 10 kΩ | Pull-down on `RX_CTRL` |

## How it is wired
| L298N pin | Net | Source |
|-----------|-----|--------|
| IN1 (7) / IN2 (8) | `TX_CTRL` / `RX_CTRL` | Pi GPIO22 / GPIO26 |
| IN3 (9) / IN4 (10) | `SDR_CTRL` / `LORA_CTRL` | Pi GPIO23 / GPIO24 |
| ENA (6), ENB (11) | `5V` | Tied high (both bridges always enabled) |
| Vs (3) | `+13.8V` | Station supply (relay coil power) |
| Vss (5) | `5V` | Logic supply (or from the module's regulator when the REG_EN jumper is fitted) |
| REG_EN1/2 (14, 15) | jumpered together | Enables the module's on-board 5 V regulator |
| OUT1–OUT4 | `RELAY±`, `SDR_LORA±` | To the coax relays |
| GND (4) | `GND` | |

All connections to the module are jumper wires (the module mounts on the HAT), as noted on the schematic.

## Notes for reusing this
- The L298 is old and inefficient (bipolar, ~2 V drop per bridge), but fine for relays. A modern
  driver (e.g. DRV8833/DRV8871) or simple MOSFET drivers would be smaller if the station gets a
  custom board.
- Don't drive IN1 and IN2 high at the same time unless you want to brake (both outputs high).
