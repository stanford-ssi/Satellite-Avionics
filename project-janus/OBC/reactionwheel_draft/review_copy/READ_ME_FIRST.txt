JANUS REACTION-WHEEL REVIEW COPY - 2026-11-20

Open reactionwheel_review.kicad_pro, then its schematic.
Original project files were not changed. All original symbols retain their positions and rotations.
The PCB file remains the original empty board; no physical PCB layout was created.

CHANGES
- Corrected VM / VM RW and HALL 5V / HALL_5V mismatches.
- Removed redundant Gnd label; motor and harness grounds connect to GND.
- Added R1=22ohm and C6=22uF for the unloaded internal buck (TI section 9.3.1.1.4).
- Added local AVDD pull-ups: fault 5.1k; FG/SDO/CS/DRVOFF 10k.
- Added 10k pulldowns on PWM, sleep and brake. These are PROVISIONAL.
- Added Hall 100nF decoupling. Added current-limit divider topology with R9/R10 both TBD.
- Kept J2 pin assignments 1-13; pins 14-16 reserved/unconnected in this candidate.
- Added digital-Hall negative-input no-connects, standard C references, notes and supply-source declarations.
- Added project-local symbol libraries. Corrected symbol electrical types for open-drain outputs, SDO, charge-pump capacitor terminals and duplicate half-bridge pads (one output plus one passive pad per phase). Physical pin numbering is unchanged.

VALIDATION
KiCad 10.0.7 loaded and exported the schematic. ERC: zero errors, one warning.
Remaining warning: original ssi_IC:MCT8316Z-Q1 footprint library was not provided.
27 connectivity/preservation checks passed; see connectivity-checks.txt.
Preview rendered and visually inspected. ERC does not validate resistor sizing, current limits or flight suitability.

REQUIRED BEFORE POWERING / FABRICATION
1. Select 2610T006B vs 2610T012B and exact vacuum-bearing option; agree actual VM min/max.
2. Confirm MCT vs FOC choice, Hall output type/supply specification and direct-OBC harness architecture.
3. Calculate R9/R10 from approved phase current, selected CSA gain, offsets and tolerances. DO NOT POWER WITH TBD VALUES.
4. Validate local AVDD pull-ups vs OBC-off/wheel-off states. This copy has no powered-off isolation buffers. Prevent back-powering before use.
5. Confirm Hall pull-ups if motor outputs require them; they are not included until output electrical data are established.
6. Confirm reset/wake sequencing: keep sleep low, PWM low and outputs disabled; configure digital Hall mode and required registers before enabling drive.
7. Buck node is UNLOADED. HALL_5V is EXTERNAL. Firmware must set BUCK_DIS; do not feed Hall load from C6 node without redesign.
8. Confirm current rating, orientation and footprint of both connectors, and Structures' board outline/mounting/height.
9. Provide and verify U1 footprint. All passive footprints are provisional 0603; select exact parts, capacitor effective values/voltage ratings and resistor ratings.
10. Confirm bypass quantity/placement, bulk capacitance, EPS protection, harness return paths, braking-energy handling and thermal path.
11. Review SPI clock speed/rise times, motor phase/Hall sequence, wheel speed limits, jitter, radiation and saturation/desaturation analysis.

Sources:
https://www.ti.com/lit/ds/symlink/mct8316z-q1.pdf
https://www.faulhaber.com/fileadmin/Import/Media/EN_2610_B_DFF.pdf
https://ssi-teams.slack.com/archives/C2L1US532/p1795150007245829
https://ssi-teams.slack.com/archives/C0C80EVGP9V/p1795211629678009

This is an engineering review draft, not a fabrication or flight release.
