# RFM98PW — 433 MHz, 1 W LoRa radio module

**Datasheet:** [`datasheets-only/ICs/TT&C/RFM98PW/`](../../../../../datasheets-only/ICs/TT%26C/RFM98PW/) (HopeRF RFM98PW/RFM95PW)
**Extracted from:** `samwise-avionics/PiCubed/picubed_samwise/RF.kicad_sch` (U23, the PiCubed mainboard)

## What it is, in basic terms
The RFM98PW is a small metal-can radio module from HopeRF. Inside is a Semtech SX1278-family
LoRa transceiver chip plus a power amplifier, so it can transmit at up to **+30 dBm (1 W)** in the
433/470 MHz band and hear signals down to about **–136 dBm**. You talk to it over **SPI**: the
microcontroller writes a packet into its buffer, tells it to transmit, and the module does all of
the modulation (LoRa, FSK, GFSK, OOK…) and RF work itself. When a packet is received (or a
transmission finishes) it raises an interrupt pin (DIO0).

## What it did on SAMWISE
This was SAMWISE's **main UHF TT&C radio** (telemetry downlink + command uplink at 433 MHz). It sits
on the PiCubed mainboard, is controlled by the RP2350 flight computer, and its SMA output is cabled
(433 MHz coax, SMA M–M) to the Z+ panel where the [HHM1589D1 balun](../HHM1589D1.kicad_block/README.md)
feeds the UHF dipole antenna. It is powered from its own switchable regulator
([TPS7A4501](../TPS7A4501.kicad_block/README.md)) so flight software can power-cycle the radio.

## What is in the block
| Ref | Value | Job |
|-----|-------|-----|
| U23 | RFM98PW | The radio module |
| C44 | 10 µF, 0603 | Bulk decoupling on the module's VCC (PA draws ~650 mA bursts during TX) |
| R5 | 10 kΩ, 0603 | Pull-up on NSS (SPI chip-select) to 3.3 V so the radio stays de-selected while the MCU is booting/reset |
| JP6 | Solder jumper, **bridged** by default | Connects VCC (`RF_Vcc`) to `RF_5V` from the TPS7A4501 radio LDO |
| JP4 | Solder jumper, **open** by default | Optional link from board 3.3 V to module pin 9 (`RF_3V3`) — see note below |
| J7 | Amphenol 901-144 SMA | 50 Ω antenna output (`RF1_ANT`, in the `50ohm` net class) |

## How it is wired (block interface)
| Net | Module pin | Goes to on SAMWISE |
|-----|-----------|---------------------|
| `RF_SCK` / `RF_MOSI` / `RF_MISO` | 12 / 11 / 10 | RP2350 GPIO14 / GPIO15 / GPIO12 (SPI) |
| `RF_CS` | 13 (NSS) | RP2350 GPIO13 (+ R5 pull-up) |
| `RF_RST` | 14 (RESET) | RP2350 GPIO11 |
| `RF_IO0` | 6 (DIO0) | RP2350 GPIO20 — TX-done / RX-done interrupt |
| `RF_5V` | 5 (VCC) via JP6 | TPS7A4501 output (~4.9 V) |
| `3.3V` | 9 via JP4 (open) | Board 3.3 V rail |
| GND | 2, 16, 17 | Ground (pad 17 is also the heat-sink pad) |
DIO1–DIO5 (pins 7, 8, 3, 4, 15) are left unconnected (no-connect flags).

## Notes for reusing this on the new satellite
- **VCC range:** the datasheet recommends **5.0–6.0 V** on VCC (abs. max 6 V). SAMWISE ran it from
  ~4.88 V (TPS7A4501 with 10 k/3.3 k), slightly under the minimum — consider ~5.2 V.
- **Pin 9 is an output:** HopeRF lists pin 9 ("3.3V") as the module's *internal 3.3 V regulator
  output* ("for MCU VCC"), not an input. SAMWISE left JP4 open (the safe default). Don't short JP4
  and JP6 at the same time (the original schematic note says the same).
- Digital pins are **3.3 V logic** (abs. max 3.6 V).
- Rated **–20 °C to +70 °C** (commercial part) — check against the thermal analysis.
- The `50ohm` net class on the antenna trace isn't defined in a fresh project; add it (or delete the
  directive label) and lay the trace out as a 50 Ω controlled-impedance line.
