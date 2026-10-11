# TT&C (Telemetry, Tracking & Command) — IC design blocks

KiCad 10 **design blocks** for every TT&C IC used on **SAMWISE** (`stanford-ssi/samwise-avionics`).
Each block is the real SAMWISE circuit around the IC — the IC plus its resistors, capacitors,
jumpers, connectors and net labels — cropped from the flight/ground-station schematics, with the
original wiring and part values. Each block's connectivity was checked against the original board
netlist.

Datasheets for all of these are in [`component_library/datasheets-only/ICs/TT&C/`](../../../datasheets-only/ICs/TT%26C/).

## Blocks
| Block | IC | What it is | Role on SAMWISE | Segment |
|-------|----|-----------|-----------------|---------|
| [RFM98PW](TT%26C.kicad_blocks/RFM98PW.kicad_block/README.md) | HopeRF RFM98PW (SX1278) | 433 MHz, 1 W LoRa/FSK radio module | Main UHF telemetry/command radio on PiCubed | Flight |
| [TPS7A4501](TT%26C.kicad_blocks/TPS7A4501.kicad_block/README.md) | TI TPS7A4501 | 1.5 A low-noise adjustable LDO with shutdown | Switchable ~4.9 V rail for each radio (`ENAB_RF`) | Flight |
| [LoRa1280F27-TCXO](TT%26C.kicad_blocks/LoRa1280F27-TCXO.kicad_block/README.md) | NiceRF LoRa1280F27-TCXO (SX1280) | 2.4 GHz LoRa radio module with PA + TCXO | S-band high-rate link on the RPi Interface board | Flight (+ 2.4 GHz ground station) |
| [HHM1589D1](TT%26C.kicad_blocks/HHM1589D1.kicad_block/README.md) | TDK HHM1589D1 | 350–950 MHz balun (50 Ω → 200 Ω balanced) | Feeds the UHF dipole antenna on the Z+ panel | Flight |
| [RFM96W](TT%26C.kicad_blocks/RFM96W.kicad_block/README.md) | HopeRF RFM96W (SX1276) | 433 MHz, 100 mW LoRa radio (Adafruit breakout) | Ground-station 433 MHz radio + PA/LNA PTT buffer | Ground |
| [L298N](TT%26C.kicad_blocks/L298N.kicad_block/README.md) | ST L298 | Dual H-bridge driver | Drives the ground-station TX/RX and LoRa/SDR coax relays | Ground |

## How the SAMWISE TT&C chain fits together
```
                  FLIGHT                                                     GROUND
RP2350 ──SPI──► RFM98PW (433 MHz, 1 W) ──coax──► HHM1589D1 balun ──► UHF dipole  ))))  antenna ─ relays (L298N) ─ PA/LNA ─ RFM96W ◄─SPI─ Raspberry Pi
   └─ENAB_RF──► TPS7A4501 (RF_5V)
RPi  ──SPI──► LoRa1280F27 (2.4 GHz) ──coax──► patch antenna  ))))  antenna ─ LoRa1280F27 ◄─SPI─ Raspberry Pi (2400 HAT)
   └─ENAB_RF──► TPS7A4501 (V_RF)
```

## Using the blocks in KiCad 10
1. **Preferences → Manage Design Block Libraries → Add** and point it at the
   `TT&C.kicad_blocks` folder (nickname e.g. `SSI_TTC`; use `${KIPRJMOD}`-relative or a path variable
   if you want it portable).
2. In the schematic editor open the **Design Blocks** panel, pick a block and place it. KiCad
   re-annotates on placement (blocks keep their SAMWISE reference designators for traceability).
3. Each `.kicad_sch` also opens on its own in the schematic editor if you just want to look.

Things to know:
- The IC/connector symbols are **embedded** in each block, so they render without any library. ERC
  will warn that the SAMWISE libraries (`ssi_IC`, `ssi_rf`, …) aren't installed — harmless; swap to
  our own library symbols as they get made.
- Footprint fields still point at SAMWISE's `ssi_*` footprint libraries (no layout was done here).
- Passives are generic `Device:` symbols with the SAMWISE values — swap them for approved
  [SSI_Passives](../../SSI_Passives/README.md) parts when you use a block in a real board.
- Interface signals are net/global/hierarchical labels; ERC "label connected to only one pin"
  warnings are expected until the block is wired into a design.
- RF traces use a `50Ω`/`50ohm` net-class directive; define that net class in your project.

## Folder layout
```
TT&C/
├── README.md                       ← this file
└── TT&C.kicad_blocks/              ← KiCad design-block library
    └── <IC>.kicad_block/
        ├── <IC>.kicad_sch          ← the schematic block
        ├── <IC>.json               ← block description + keywords (shown in KiCad)
        └── README.md               ← what the IC does, how it's wired, part values, reuse notes
```
