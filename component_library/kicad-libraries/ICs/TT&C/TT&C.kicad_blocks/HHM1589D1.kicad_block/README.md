# HHM1589D1 — RF balun for the UHF dipole antenna

**Datasheet:** [`datasheets-only/ICs/TT&C/HHM1589D1/`](../../../../../datasheets-only/ICs/TT%26C/HHM1589D1/) (TDK multilayer balun)
**Extracted from:** `samwise-avionics/ZPlus_Panel/ZPlus_Panel.kicad_sch` (U2, with J1 SMA and AE1 dipole)

## What it is, in basic terms
A **balun** ("balanced–unbalanced") is a tiny RF transformer. A coax cable / SMA connector is
*unbalanced* (signal on the center pin, ground on the shield), but a dipole antenna is *balanced*
(two equal arms driven in opposite phase). Connecting coax straight to a dipole makes RF current run
back down the outside of the cable and distorts the antenna pattern. The balun sits in between and
converts one to the other. The HHM1589D1 is a 2.0 × 1.25 mm (0805) part from TDK covering
**350–950 MHz**, with a **50 Ω unbalanced port** and a **200 Ω balanced port** (4:1 impedance), up
to **3 W**, about **2 dB** insertion loss (2.6 dB max), –40 to +85 °C.

## What it did on SAMWISE
It lives on the **Z+ solar panel**, next to the deployable **UHF dipole antenna (AE1)**. The 433 MHz
signal from the [RFM98PW](../RFM98PW.kicad_block/README.md) on PiCubed arrives by coax at the SMA (J1);
the balun turns it into the balanced feed for the two dipole arms. It is the last part in the 433 MHz
TT&C chain before the antenna.

## What is in the block
| Ref | Value | Job |
|-----|-------|-----|
| U2 | HHM1589D1 | Balun |
| J1 | Amphenol 901-144 SMA | 50 Ω coax input from the radio |
| AE1 | UHF_Dipole_Antenna | The two dipole arms (mechanical mount + pads) |

## How it is wired
| Balun pin | Connects to |
|-----------|-------------|
| 1 — Unbalanced port | J1 center pin (50 Ω net class) |
| 2 — GND / DC feed | GND |
| 5 — GND | GND (and J1 shield) |
| 3, 4 — Balanced port | AE1 pad 1 and pad 2 (dipole arms) |
| 6 — N.C. | No-connect |

There are no other passives — the 50 Ω nets are marked with `50Ω` net-class directives.

## Notes for reusing this
- ⚠️ **TDK marks the HHM1589D1 "not recommended for new design"** in this datasheet (2015). Check
  stock/lifecycle before committing; look for a current 350–950 MHz balun as a backup.
- ~2 dB insertion loss means roughly a third of the transmit power is lost in the balun — worth a
  look in the link budget.
- 4:1 (50 → 200 Ω) suits a folded dipole or a dipole with its own matching; for a plain half-wave
  dipole (~73 Ω) check the actual match with a VNA.
- Define the `50Ω` net class in the new project and route as 50 Ω controlled impedance.
