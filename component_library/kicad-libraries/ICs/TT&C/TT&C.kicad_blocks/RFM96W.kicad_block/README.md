# RFM96W — 433 MHz LoRa radio for the ground station (+ PA/LNA PTT control)

**Datasheet:** [`datasheets-only/ICs/TT&C/RFM96W/`](../../../../../datasheets-only/ICs/TT%26C/RFM96W/) (HopeRF RFM95W/96W/98W + Adafruit breakout guide)
**Extracted from:** `samwise-avionics/Groundstation_433_Hat/433_hat_board.kicad_sch` (U3, C1, C2, J2, and the PTT buffer Q1, Q2, D1, R3)

## What it is, in basic terms
The RFM96W is HopeRF's 433 MHz LoRa transceiver module built on the Semtech **SX1276/77** chip —
the low-power sibling of the satellite's RFM98PW. It transmits up to **+20 dBm (100 mW)**, receives
down to about –144 dBm, and is controlled over **SPI** with DIO0–DIO5 interrupt pins. SAMWISE used
it on **Adafruit's RFM96W breakout**, which adds a 3.3 V regulator (so **Vin can be 3.3–6 V**), an
**EN** pin that cuts power to the radio when pulled low, and level shifting on the SPI pins.

## What it did on SAMWISE
This is the **ground-station end of the 433 MHz link**. The breakout plugs into the "433 HAT"
on a Raspberry Pi 4. The Pi uses it to receive SAMWISE telemetry and send commands, talking the same
LoRa settings as the RFM98PW on the satellite. Because 100 mW isn't enough to reach orbit, the
station adds an external **power amplifier (PA) and low-noise amplifier (LNA)**; the block's
**"LNA/PA Dual Control"** circuit lets one Pi GPIO (`PTT_OUT`, push-to-talk) switch them between
transmit and receive.

## What is in the block
| Ref | Value | Job |
|-----|-------|-----|
| U3 | RFM96W (Adafruit breakout) | 433 MHz LoRa radio |
| C1 | 10 µF | Bulk decoupling on +5 V at the radio |
| C2 | 0.1 µF | High-frequency decoupling on +5 V |
| J2 | Amphenol 901-144 SMA | Antenna connector — *"connect antenna to radio module directly, NOT pcb"* (marked not-on-board) |
| Q2 | 2N7002 | Inverting buffer driven by `PTT_OUT` |
| R3 | 100 kΩ | Pull-up (to +5 V) on Q2's drain / Q1's gate |
| Q1 | 2N7002 | Open-drain output to the PA's PTT/remote line (`PA_PTT`) — "buffer for PA BJT PTT control" |
| D1 | M7 (1 A, 1000 V diode) | Passes `PTT_OUT` to the LNA's PTT line (`LNA_PTT`) |

## How it is wired
| Net | Radio pin | Raspberry Pi GPIO |
|-----|-----------|-------------------|
| `SCK` / `MOSI` / `MISO` | 5 / 7 / 6 | GPIO11 / GPIO10 / GPIO9 (SPI0) |
| `CS` | 8 | GPIO7 (SPI0 CE1) |
| `RST` | 9 | GPIO6 |
| `enable` | 3 (EN) | GPIO20 |
| `DIO0`…`DIO5` | 4, 10–14 | GPIO17, 12, 13, 16, 19, 18 |
| `+5V` | 1 (Vin) | Pi 5 V |
| `PTT_OUT` | — | GPIO27 → Q2 gate and D1 |
| `PA_PTT`, `LNA_PTT` | — | Out to the PA / LNA remote wires (via header J1 on the HAT) |

PTT logic: `PTT_OUT` high → Q2 on → Q1 gate pulled low → Q1 off (`PA_PTT` released); `PTT_OUT` low →
R3 pulls Q1's gate high → Q1 sinks `PA_PTT`. D1 lets `PTT_OUT` drive `LNA_PTT` in one direction only.
Check the polarity against your actual PA/LNA's remote-input spec.

## Notes for reusing this
- The new ground station can reuse this almost as-is; just match the LoRa parameters (SF, BW, CR,
  sync word) to the flight radio.
- Real antenna/coax goes straight to the module's u.FL/SMA, not through the HAT PCB.
- The relays that switch the antenna path between TX and RX are driven by the
  [L298N block](../L298N.kicad_block/README.md).
