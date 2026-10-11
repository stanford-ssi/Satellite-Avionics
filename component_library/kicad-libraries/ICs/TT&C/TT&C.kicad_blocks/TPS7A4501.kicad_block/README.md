# TPS7A4501 — switchable low-noise LDO for the radios

**Datasheet:** [`datasheets-only/ICs/TT&C/TPS7A4501/`](../../../../../datasheets-only/ICs/TT%26C/TPS7A4501/) (TI TPS7A45xx)
**Extracted from:** `samwise-avionics/RPi_Interface/RPi_interface.kicad_sch` (U3). The same circuit is
on the PiCubed mainboard (`Power.kicad_sch`, U21) for the 433 MHz radio.

## What it is, in basic terms
The TPS7A4501 is a **linear voltage regulator (LDO)**: it takes a higher, noisy voltage (here the
battery bus, 4.5–18 V) and outputs a lower, very clean voltage. It can supply **1.5 A** with only
about **300 mV of dropout**, has very low output noise (which is why TI pitches it for RF supplies),
and has a **shutdown pin**: pull SHDN low and the output turns off and it draws <1 µA. The "01" is
the adjustable version — two resistors set the output voltage:

> V<sub>OUT</sub> = 1.21 V × (1 + R6/R7) + 3 µA × R6 = 1.21 × (1 + 10k/3.3k) + 0.03 ≈ **4.9 V**

## What it did on SAMWISE
Each radio got its own TPS7A4501 that the flight computer can switch on and off through the
`ENAB_RF` line. That gives TT&C a clean ~4.9 V supply (low noise = better receive sensitivity), keeps
the radio's big transmit current pulses off the 3.3 V logic rail, and lets software hard
power-cycle a hung radio.
- **PiCubed (U21):** VBATT → `RF_5V` for the [RFM98PW](../RFM98PW.kicad_block/README.md) 433 MHz radio; `ENAB_RF` = RP2350 GPIO21.
- **RPi Interface board (U3, this block):** VBATT → `V_RF` for the [LoRa1280F27-TCXO](../LoRa1280F27-TCXO.kicad_block/README.md) 2.4 GHz radio; `ENAB_RF` comes from the RPi header.

## What is in the block
| Ref | Value | Job |
|-----|-------|-----|
| U3 | TPS7A4501DCQT (SOT-223-6) | The regulator |
| C14 | 47 µF | Input capacitor on VBATT, placed right at the LDO to absorb radio inrush current |
| C8 | 10 µF | Output capacitor on `V_RF` (stability + transient response) |
| R6 | 10 kΩ | Feedback divider, top (OUT → SENSE/ADJ) |
| R7 | 3.3 kΩ | Feedback divider, bottom (SENSE/ADJ → GND) |
| R11 | 10 kΩ | Pull-down on `ENAB_RF`/SHDN so the radio stays **off** if the controller is unpowered or the line floats |

## How it is wired (block interface)
| Net | Pin | Notes |
|-----|-----|-------|
| `VBATT` | 2 (IN) | Battery bus, 4.5–18 V |
| `ENAB_RF` | 1 (SHDN) | High = on, low/floating = off |
| `V_RF` | 4 (OUT) | ~4.9 V to the radio |
| — | 5 (SENSE/ADJ) | R6/R7 divider |
| GND | 3, 6 (tab) | Ground / thermal tab |

## Notes for reusing this
- On the RPi Interface board the input also had **C3, C4 (47 µF each)** shared with the buck
  converter (the schematic note: "higher input capacitance than specified in datasheet to reduce
  effects from radio LDO inrush"). The PiCubed version used a single 10 µF in (C9) and 10 µF out (C43).
- Power dissipation is (V<sub>IN</sub> – V<sub>OUT</sub>) × I. At 18 V in and ~650 mA of TX current that is ~8.5 W —
  far too much for SOT-223. It's fine at typical battery voltages / short TX bursts, but check it for
  the new power architecture.
- Change R6/R7 to retarget the voltage (e.g. ~5.2 V for the RFM98PW's 5.0–6.0 V spec).
