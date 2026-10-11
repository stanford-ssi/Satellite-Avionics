# POWER — power-conversion IC design blocks

KiCad 10 **design blocks** for power ICs, taken from SAMWISE (`stanford-ssi/samwise-avionics`). Each
block is the real SAMWISE circuit (IC + passives + net labels, original values), checked against the
original board netlist. Datasheets are in
[`component_library/datasheets-only/ICs/POWER/`](../../../datasheets-only/ICs/POWER/).

| Block | IC | What it is | Role on SAMWISE |
|-------|----|-----------|-----------------|
| [TPS54426](POWER.kicad_blocks/TPS54426.kicad_block/README.md) | TI TPS54426 | 4.5–18 V in, 4 A synchronous buck converter | VBATT → 5 V for the Raspberry Pi payload (RPi Interface board) |

The radios' dedicated **TPS7A4501 LDO** stays in the [TT&C section](../TT%26C/README.md) because it is
part of the radio chain (it's a linear regulator, not a buck).

**Using the blocks:** in KiCad add `POWER.kicad_blocks` under *Preferences → Manage Design Block
Libraries*, then place blocks from the Design Blocks panel. See the [TT&C README](../TT%26C/README.md)
for notes on embedded symbols, footprints and passives — the same apply here.
