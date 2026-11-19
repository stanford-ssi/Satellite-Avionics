# Battery Board System (BBS)

> This README mirrors the Battery Board System (BBS) section of PJ-100002 (PDU Architecture & Design). Both are generated from `docs/build/make_section.js`; edit that file and rebuild so they stay in sync.

**Responsible Engineer:  Alessandro Gregori**

**Requirements:** [H-05] [H-11] [H-12]

**Topology:** 2× 2S 18650 strings → polyfuse per string → LTC4353 ideal-diode OR (one SQS460EN per string) → VBAT_RAW → J_EXT1 to PDU

**Heater loop (per string):** NTC divider → MCP65R46 comparator (with hysteresis) → FPF2700 ON pin → heater on J_Heat

## Board Function

The battery board is the satellite's energy store. It holds four 18650 Li-ion cells as two independent 2S strings (7.4 V nominal, 8.4 V full, 6.0 V cutoff) and delivers one combined battery rail, **VBAT_RAW**, to the PDU, which charges the pack (SACD/BCDR) and distributes it to loads (VLSA).

The board does three things on its own, with no software:

- **Stores energy and protects each string.** Each string has its own resettable fuse, so a hard short inside one string is cut off from the rest of the board.
- **Combines the strings without letting them fight.** An ideal-diode controller passes current from whichever string is higher onto VBAT_RAW, and blocks current from flowing back into a string. A weak, shorted or disconnected string simply drops out, and the healthy string keeps the satellite running. This is why the two strings are ORed instead of wired directly in parallel (the same reasoning OreSat uses for its separate 2S packs [2]).
- **Keeps the cells warm enough to charge.** Li-ion cells must not be charged below about 0 °C. Each string has a thermistor and a comparator thermostat that switch a Kapton film heater, wrapped directly on that string's cells, on below about 5.7 °C and off above about 14.7 °C. The heater is powered from its own string and current-limited, so a heater fault can't drain the pack.

### How it behaves

- **Normal:** both strings share the load; the ideal diodes keep the drop to tens of millivolts.
- **One string low or failed open:** its MOSFET turns off and the other string carries the bus alone.
- **Short inside a string:** the polyfuse trips, and the ideal diode stops the good string from feeding the short.
- **Cold pack:** the thermostat turns that string's heater on below ~5.7 °C and back off above ~14.7 °C.
- **Shorted heater:** the FPF2700 limits current to ~0.5 A and auto-restarts, so the string keeps powering the bus.
- **PDU MCU off or resetting:** heaters and ORing keep working; only the 3.3 V thermostat supply comes from the PDU.

![Battery board block diagram](docs/block_diagram.png)

*Battery board block diagram: power path in blue, ORing in red, heater control in orange.*

### Board build

- 2-layer FR-4, 1.6 mm, 99.5 × 140.5 mm outline; all 40 parts on the top side
- Channel A and channel B (strings, heater switches, thermostats) are laid out as mirror images about the board centre line, so both channels see the same trace lengths and thermal environment
- Cells sit in four Keystone 1042 surface-mount 18650 holders; ground and power use copper pours (2 zones), 282 track segments, 171 vias
- Connectors: J_EXT1 (Molex Micro-Fit 3.0, VBAT_RAW / 3.3 V / GND) to the PDU; J_Heat_A and J_Heat_B (JST PH) to the heaters

### Ideal diode controller: LTC4353IMS#PBF

<https://www.analog.com/media/en/technical-documentation/data-sheets/4353f.pdf>

- Dual controller, 0–18 V ORing, so one IC covers both strings; −40 to 85 °C (I-grade); MSOP-16
- Gate clamped 12 V above input, so the FETs are fully enhanced at 2S; tens of mV drop vs ~0.4 V for a Schottky
- **Heritage:** no record of the LTC4353 itself flying. Its single-channel sibling, the LTC4352, flew on Quetzal-1 (1U, 2020) as the battery-path ideal diode [1]
- Not stocked at LCSC (DigiKey/Mouser); confirm it's still active before freezing the design

### ORing MOSFET: SQS460EN-T1_GE3 (Vishay, AEC-Q101)

<https://www.vishay.com/docs/72642/sqs460en.pdf>

- 60 V N-channel, 36 mΩ max @ 10 V (30 mΩ typ), C_iss 603 pF typ / 755 pF max, PowerPAK 1212-8; replaces the Si4126DY for its radiation data
- **Heritage:** NASA GSFC heavy-ion single-event testing (NSREC 2017) [15]; failures (burnout) only at drain voltages far above our 8.4 V bus. NASA also notes large part-to-part variation, so screen a sample
- Conduction loss: (2 A)² × 36 mΩ = **0.14 W**; (3 A)² × 36 mΩ = **0.32 W**; at 125 °C R_DS(on) rises to 66 mΩ. Keep each string at about **3 A or less**; the Si4126DY (2.75 mΩ) is the low-loss fallback if the load budget needs more
- Schematic symbol Transistor_FET:SiS454DN with the stock footprint Package_SO:Vishay_PowerPAK_1212-8_Single: pins 1-3 = S, 4 = G, 5 (pins 5-8 + exposed pad) = D, the same pinout as the SQS460EN

### Heater switch: FPF2700MX (onsemi)

<https://www.onsemi.cn/pub/Collateral/FPF2702CN-D.pdf>

- 2.8–36 V load switch, current limit set by R_SET (0.4–2 A), 88 mΩ, SOIC-8; ON is active-LOW
- Auto-restart after a fault (FPF2701 latches off), so a heater fault recovers without software
- R_SET = 549 kΩ → I_LIM = 277.5 / 549 = **0.51 A typ / 0.40 A min** (datasheet table value, 1 %)
- **Heritage:** flew on MIT's MicroMAS CubeSat and was total-dose tested to 8 and 24 krad(Si), far above a typical 1.2 krad LEO dose [4]

### Thermostat: MCP65R46T-1202E/CHY + NASA 44907 NTC

- ~3 µA open-drain comparator on 3.3 V, SOT-23-6; threshold set by a divider so it's ratiometric with the NTC divider
- R_NTC = 10 kΩ (= NTC at 25 °C) → 1.65 V at 25 °C, most sensitive point; 165 µA
- Threshold: 150k / 300k → V+ = 2.20 V → trips at 20 kΩ ≈ **8.7 °C**
- Thermistor: YSI/TE **44907 = NASA GSFC S-311-P-18/07S7R6**, 10 kΩ at 25 °C, β = 3574 K, ±0.2 °C, −55 to +90 °C, outgassing 0.66 % TML / 0.01 % CVCM [16][17]. Leaded: the bead is bonded to the string's cells and the leads solder to two pads on the board, so it reads cell temperature
- 1.0 MΩ feedback adds hysteresis: heater ON below ≈ **5.7 °C** (V+ = 2.30 V, R_th > 23.0 kΩ), OFF above ≈ **14.7 °C** (V+ = 2.00 V, R_th < 15.4 kΩ). 1.0 MΩ was chosen over 1.2 MΩ because TNPW0805 tops out at 1 MΩ
- 10 kΩ pull-up holds ON high (heater off) until the comparator sinks it; standby ≈ **0.18 mA per channel** on 3.3 V
- **Heritage:** the 44907 is a NASA-qualified (S-311-P-18 QPL) part [16]. No flight or radiation data found for the MCP65R46; keep it in the radiation/TVAC test plan (TI TLV1704-SEP is a radiation-tolerant alternative if the comparator is ever changed)

### Per-string fuse: Littelfuse 1206L500/12SLPR

- 5 A hold, 12 V, 1206 PPTC; the same part OreSat0 flew on its 2S battery discharge path [18]
- Clears a hard short inside a string; the ideal diodes keep the other string on the bus. PPTC trip current shifts with temperature, so check it across −40 to +80 °C

### Cells: LG INR18650-MJ1 (3,500 mAh)

- NASA JPL/JSC/KSC testing found MJ1 had the highest specific energy of the cells tested (>230 Wh/kg at 20 °C), ~90 % capacity after 1,100 cycles, and was the best performer at 0 °C [5]
- Flight heritage on NASA's PACE mission (NASA SmallSat State-of-the-Art) [6]; selected for Europa Clipper [5]
- Standard cell in Pumpkin's BM 2 CubeSat battery module, which meets JSC EP-WI-032 for ISS deployment [7]; also used on the PyCubed battery board [8]
- At −20 °C its output drops to 30–70 Wh/kg [5], which is why the heaters matter

### LTC4353 support caps

- C_CPO = 10 nF (CGA3E2X7R1H103K080AA): datasheet says ~10× MOSFET C_iss; 10 nF ≈ 13× the SQS460EN's 755 pF max
- C_VCC = 0.1 µF (required); C_V_OUT = 10 µF on VBAT_RAW (datasheet recommended, limits switchover droop)

## Flight Heritage Summary

The architecture (battery board with its own heater and autonomous thermostat) is standard on flown CubeSat batteries. The ORing controller, MOSFET and thermostat parts are commercial parts without direct heritage.

| Part / feature | Heritage | Status |
| --- | --- | --- |
| Autonomous battery heater + thermostat | ISIS ICEPS2 (PEASSS 2016, Hiber 1/2 2018) [9]; GomSpace P31u/BP4 (GomX-1, FUNcube, Triton-1) [10]; AAC Clyde Space Optimus, >100 missions [11]; Quetzal-1 on-orbit [1] | Flown |
| 2S 18650 strings kept separate | OreSat 2× 2S1P packs [2]; ISIS ICEPS2 2S1P [9] | Flown / vendor |
| LG INR18650-MJ1 cells | NASA PACE [6]; Pumpkin BM 2 [7]; NASA cell testing [5] | Flown |
| FPF2700 load switch | MIT MicroMAS, TID tested to 24 krad [4] | Flown |
| LTC4353 ideal diode | Sibling LTC4352 flew on Quetzal-1 [1] | Family flown |
| SQS460EN MOSFET | NASA GSFC heavy-ion SEE test data [15] | Radiation-tested |
| 44907 thermistor | NASA GSFC S-311-P-18 qualified parts list [16] | NASA-qualified |
| MCP65R46 comparator | None found | Not flown |
| Kapton film heater on the cells | Pumpkin BM 2 [7]; OreSat battery board [2]; Quetzal-1 on-orbit [1]; most common small-spacecraft heater per NASA [13] | Flown |
| 1206L500 PPTC fuse | OreSat0 2S battery discharge path [18] | Flown |

## Battery Heater: Kapton Polyimide Film

**Decision:** each 2S string gets its own Kapton (polyimide) etched-foil film heater, wrapped directly on that string's cells and plugged into J_Heat_A / J_Heat_B. It is shown on the schematic as HTR_A1 / HTR_B1 (BOM only, excluded from the PCB).

### Why Kapton

- Most flight heritage of any heater type: NASA's SmallSat State-of-the-Art calls Kapton heaters the most common on small spacecraft [13]
- Same approach as flown and vendor battery packs: Pumpkin BM 2 wraps a Kapton heater on each cell [7]; OreSat uses two 49 Ω Minco heaters in parallel (≈ 25 Ω, ≈ 2.8 W at 8.4 V) [2]; Quetzal-1 flew a 13 Ω Kapton heater between its cells and kept the pack from freezing at about a 25 % orbital duty cycle [1]
- Heat goes straight into the cell cans instead of crossing the PCB and the holder gap, which matters in vacuum where there is no air to carry heat
- Space-grade low outgassing: Minco satellite heaters are built to NASA GSFC S-311-P-841, e.g., TML 0.36 %, CVCM 0.01 % [14]

### Heater specification (per string)

| Parameter | Value | Why |
| --- | --- | --- |
| Type | Etched-foil element in polyimide (Kapton), pressure-sensitive adhesive backing; Minco HK/HAP satellite heater family or equivalent [14] | Heritage, thin (~0.3 mm), low outgassing |
| Resistance | **25 Ω ±10 %** (22.5–27.5 Ω): one ~25 Ω element per string, or two ~49 Ω in parallel like OreSat [2] | Worst case 22.5 Ω still stays under the FPF2700's 0.40 A minimum limit |
| Current at 8.4 V | 0.34 A nominal, **0.37 A max** (at 22.5 Ω) | Below the 0.40 A min / 0.51 A typ limit, so the switch never cycles |
| Power (25 Ω) | **2.8 W** at 8.4 V, 2.2 W at 7.4 V, 1.4 W at 6.0 V | P = V² / R |
| Size | ≈ 12.7 mm wide, length to wrap both cells of a string (e.g., 12.7 × 100 mm as on OreSat [2]) | Fits along the 18650 cans |
| Watt density | 2.8 W / 12.7 cm² ≈ **0.22 W/cm² (1.4 W/in²)** | Far below Minco's 33 W/in² rating [14], so no hot spots |
| Temperature range | −32 to +100 °C (set by the adhesive) [14] | Covers the ~5–14 °C control band with margin |
| Connection | Leads crimped into a JST PH 2-pin housing (PHR-2) mating J_Heat_A / J_Heat_B; heater + to pin 1 (HEATER_A/B), return to pin 2 (GND) | Removable for assembly and test |

### Integration on the board

- Wrap the heater around the middle of each string's two cells before seating them in the Keystone 1042 holders; confirm the extra ~0.3 mm thickness still fits the holder clips, or wrap only the exposed side of the cans
- Back the heater with a thin outer wrap (Kapton tape) so the adhesive is not the only retention under vibration; strain-relieve the leads to the board
- **Thermistor placement:** TH1/TH2 are leaded NASA 44907 parts. Bond each bead to its string's cells (away from the heater element, so it reads the cell, not the heater) and solder the leads to the TH1/TH2 pads
- Each heater is powered from its own string through its FPF2700, so a shorted heater only affects that string, and the switch limits it to ~0.5 A

### Power budget (estimate)

At 7.4 V each heater draws 2.2 W while on. If it runs about 25 % of the orbit (what Quetzal-1 saw [1]), that is ≈ 0.55 W orbit-average per string, ≈ 1.1 W for both. Worst case, both heaters fully on at 8.4 V draw **5.6 W**. The real duty cycle depends on how well the battery is insulated and should come from the thermal model.

**Alternatives considered:** on-board 2512 resistors or an inner-layer copper trace heater would keep the heater on the PCB, but neither has flight heritage for batteries and both must push heat across the board and holder gap, so they were rejected. A hermetic bimetal thermostat in series with each heater is still an option as an independent over-temperature cutout.

**Passives (flight build, CL-000001):** Vishay TNPW e3 thin-film resistors, 0805, ±0.1 %, 25 ppm/K (TNPW080510K0BEEA, TNPW0805150KBEEA, TNPW0805300KBEEA, TNPW0805549KBEEA, TNPW08051M00BEEA); MLCCs from the CL-000001 flight list (GCM155R71H104KE02D 100 nF 0402, CGA3E3X7R1H105K080AB 1 µF 0603, C2012X7S1E106K125AE 10 µF 0805, GRM31CC71E226ME15L 22 µF 1206) plus CGA3E2X7R1H103K080AA 10 nF 0603 for CPO. All caps run at ≤ 50 % of rating (8.4 V on 25 V parts, 12 V on 50 V), inside the 60 % derating rule. Pre-flight part numbers are kept in each symbol's MPN_PreFlight field. The MOSFETs, thermistors and fuses use the higher-heritage parts in both builds, since they set the footprint.

**PDU interface:** J_EXT1 = VBAT_RAW, 3.3 V (thermostat only), GND. LTC4353 ONST1/ONST2 (which string is active) are unconnected for now; could go to the PDU MCU later.

**Fault handling [H-05]:** polyfuse per string for hard shorts; ideal diodes isolate a failed string from the bus; FPF2700 current-limits each heater and auto-restarts.

### Open items

- **No charge path yet:** the LTC4353 ideal diodes only let current out of the strings, so nothing can charge the cells through VBAT_RAW. Add a charge path (e.g., OreSat0-style second ideal diode per string, bus to pack) before freezing the layout
- **PCB update:** Q1/Q2 (PowerPAK 1212-8), TH1/TH2 (wire pads) and F1/F2 (1206) changed footprint; run Update PCB from Schematic and re-place/re-route those six parts
- **String current:** keep each string at about 3 A or less for the SQS460EN (0.32 W at 3 A); confirm against the VLSA load budget
- Pick the exact Minco heater (catalog or custom, 25 Ω ±10 %), check it fits inside the Keystone 1042 holders, and decide on a bimetal backup cutout
- Set the VBAT_RAW load budget with VLSA, then confirm the 5 A polyfuse (check its trip current over −40 to +80 °C) and J_EXT1 rating
- Block charging below 0 °C (PDU/BCDR side) using the battery thermistors
- Board is 140.5 mm long: confirm it fits the structure
- Decide if ONST1/2 and FPF2700 FLAGB get routed to the MCU for telemetry
- Radiation/TVAC test plan for the parts without heritage (LTC4353, MCP65R46) and a screening sample of SQS460EN

### Sources

1. [Quetzal-1 EPS design and on-orbit performance (JoSS 2023)](https://jossonline.com/storage/2023/05/Final-Aguilar-Nadalini-Design-and-On-Orbit-Performance-of-the-Electrical-Power-System-for-the-Quetzal-1-CubeSat.pdf)
2. [OreSat battery board README](https://github.com/oresat/oresat-batteries/blob/master/README.md)
3. [NASA GSFC SEE testing of commercial TrenchFETs (2017)](https://ntrs.nasa.gov/citations/20170009000)
4. [TID tolerance of popular CubeSat components (MicroMAS)](https://www.scribd.com/document/516727983/TID-TOLERANCE-OF-POPULAR-CUBESAT-COMPONENTS)
5. [Krause, Darcy et al., J. Electrochem. Soc. 168 (2021), 18650 cell testing](https://iopscience.iop.org/article/10.1149/1945-7111/abf05f)
6. [NASA SmallSat State-of-the-Art: Power](https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/)
7. [Pumpkin BM 2 battery module datasheet](https://www.pumpkininc.com/space/datasheet/710-01640-F_DS_BM_2.pdf)
8. [PyCubed battery board v01b](https://github.com/pycubed/hardware/tree/master/batteryboard-v01b)
9. [ISIS ICEPS2 datasheet](https://isispace.nl/wp-content/uploads/2025/01/ISIS-ICEPS2-DSH-0001-ICEPS2_Datasheet-01_02.pdf)
10. [GomSpace NanoPower P31u datasheet](https://bytebucket.org/bbruner0/albertasat-on-board-computer/wiki/1.%20Resources/1.1.%20DataSheets/EPS/gs-ds-nanopower-p31u-9.0.pdf?rev=316ebd49bed49fdbb1d74efdeab74430e7cc726a)
11. [AAC Clyde Space Optimus datasheet](https://www.aac-clyde.space/wp-content/uploads/2021/10/AAC_DataSheet_Optimus.pdf)
12. [CubeSat Resources: EPS development](https://cubesat-resources.space/development/eps/)
13. [NASA SmallSat State-of-the-Art: Thermal Control](https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/)
14. [Minco HAP6731 satellite heater](https://www.minco.com/catalog/?catalogpage=product&id=HAP6731&cid=satellite-heaters)
15. [Lauenstein et al., NASA GSFC SEE testing incl. SQS460EN (NSREC 2017)](https://ntrs.nasa.gov/api/citations/20170007314/downloads/20170007314.pdf)
16. [NASA NEPP parts list: S-311-P-18 thermistors](https://nepp.nasa.gov/npsl/Thermistors/311p18/18.htm)
17. [YSI 44900 series (S-311-P-18) thermistor datasheet](https://instrumentation.obs.carnegiescience.edu/ccd/parts/YSI44900.pdf)
18. [OreSat battery board repo, flown v3.0 schematic](https://github.com/oresat/oresat-batteries)

## Repository contents

| Path | What it is |
| --- | --- |
| `Battery Board.kicad_sch` / `.kicad_pcb` / `.kicad_pro` | KiCad 10 schematic, PCB and project |
| `Battery_Board_Library.kicad_sym` | Project symbols (LTC4353, FPF2700) |
| `Battery_Board_Footprints.pretty/` + `fp-lib-table` | Project footprints from earlier revisions (S/G/D-named MOSFET pads); no longer used now that Q1/Q2 use `Transistor_FET:SiS454DN` + the stock PowerPAK footprint |
| `tools/` | Placement / routing / mirroring scripts |
| `docs/block_diagram.png` | Block diagram used above and in the Word section |
| `docs/oresat0_channel.png` | Reference: one OreSat0 pack channel (discharge + charge ideal diodes), redrawn from their flown v3.0 schematic; `docs/build/oresat_diag.js` draws it |
| `docs/build/` | Generators: `make_section.js` (Word section + this README), `diagram.js` (block diagram), Lexend fonts |

Rebuild: `cd docs/build && npm install docx canvas && node diagram.js ../block_diagram.png && node make_section.js "../../../PJ-100002 Battery Board Section.docx" ../../README.md`
