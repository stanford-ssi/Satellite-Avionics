# LoRa1280F27-TCXO — 2.4 GHz, 500 mW LoRa radio module

**Datasheet:** [`datasheets-only/ICs/TT&C/LoRa1280F27-TCXO/`](../../../../../datasheets-only/ICs/TT%26C/LoRa1280F27-TCXO/) (NiceRF LoRa128XF27 + Semtech SX1280)
**Extracted from:** `samwise-avionics/RPi_Interface/RPi_interface.kicad_sch` (U2, the "2400 MHz Radio Module" section)

## What it is, in basic terms
A small shielded module from NiceRF built around Semtech's **SX1280** 2.4 GHz transceiver, plus an
external **power amplifier and LNA** that push it to **+27 dBm (500 mW)** and about **–132 dBm**
sensitivity. The "-TCXO" version has a **0.5 ppm temperature-compensated crystal**, so the radio
frequency stays put over big temperature swings (important in orbit, and for narrow LoRa channels).
It supports LoRa (0.476–202 kbps), FLRC (up to 1.3 Mbps) and FSK. You control it over **SPI**,
watch the **BUSY** pin before each command, and get interrupts on DIO1–DIO3. Two extra pins,
**TXEN** and **RXEN**, flip the module's internal RF switch / PA / LNA between transmit and receive.
Supply is **2.0–5.5 V** (full power at 5 V, <600 mA in TX); all I/O is **3.3 V logic**. Rated –40 to +85 °C.

## What it did on SAMWISE
This was SAMWISE's **2.4 GHz (S-band) link**, a faster channel than the 433 MHz UHF radio, used
alongside the Raspberry Pi + camera payload. It sits on the **RPi Interface board**, is controlled
directly by the Raspberry Pi over SPI, gets power from its own switchable
[TPS7A4501](../TPS7A4501.kicad_block/README.md) (`V_RF` ≈ 4.9 V, turned on by `ENAB_RF`), and its SMA (J4)
is cabled to a **patch antenna**. The same module, wired the same way, is the radio on the
**2400 MHz ground-station HAT** (`Groundstation_2400_Hat`) at the other end of the link.

## What is in the block
| Ref | Value | Job |
|-----|-------|-----|
| U2 | LoRa1280F27-TCXO | The radio module |
| C9 | 10 µF | Bulk decoupling on `V_RF` — **DNP on SAMWISE** (the LDO's output caps are right there) |
| C10 | 0.1 µF | High-frequency decoupling on `V_RF` |
| R12 | 10 kΩ | Pull-up from TCXO_EN to +3V3 so the TCXO runs whenever the board is powered — **DNP for flight** (software drives `TCXO_EN` instead) |
| J4 | Amphenol 901-144 SMA | 50 Ω antenna output (`50Ω` net class) |
| Q2 | IRLML2803 N-MOSFET | TX monitor LED driver, gate on `RF_TX_EN` — **DNP for flight** |
| R10 | 330 Ω | LED current limit from 5 V — **DNP for flight** |
| D1 | LTST-C191KGKT (green LED) | Lights while the radio is transmitting — bench debugging only, **DNP for flight** |

## How it is wired (block interface)
| Net | Module pin | Goes to on SAMWISE |
|-----|-----------|---------------------|
| `V_RF` | 1 (VCC) | TPS7A4501 output |
| `TCXO_EN` | 2 (TCXOEN) | RPi header pin 22 (GPIO25) |
| `RF_RST` | 3 (NRESET) | RPi GPIO22 (header 15) |
| `RF_BUSY` | 4 (BUSY) | RPi GPIO26 (header 37) |
| `RF_IO1` / `RF_IO2` / `RF_IO3` | 5 / 6 / 7 | RPi GPIO19 / 20 / 21 |
| `RF_CS` | 8 (NSS) | RPi GPIO5 (header 29) |
| `SCLK` / `MOSI` / `MISO` | 9 / 10 / 11 | RPi SPI0 (GPIO11 / 10 / 9) |
| `RF_TX_EN` | 13 (TXEN) | RPi GPIO23 (header 16) |
| `RF_RX_EN` | 14 (RXEN) | RPi GPIO24 (header 18) |
| — | 17 (ANT) | J4 SMA |
| GND | 12, 15, 16, 18, 19 | Ground |

## Notes for reusing this
- **TCXO start-up order (from the datasheet):** drive `TCXO_EN` high *before* releasing NRESET,
  wait **≥3 ms** for the TCXO to settle, and keep it high the whole time the radio is in use.
- Never assert TXEN and RXEN together. The **2400 ground-station HAT** added **10 kΩ pull-downs on
  TXEN and RXEN** (and 10 µF + 0.1 µF decoupling ×2 on 5 V) so the PA stays off while the Pi boots —
  worth adding to the flight version too.
- 600 mA TX bursts: keep the TPS7A4501 output caps close and the ground return short.
- Route `ANT` → SMA as a 50 Ω line; define the `50Ω` net class in the new project.
