# RM3100 magnetometer board (Janus)

Primary magnetometer for ADCS: PNI RM3100 sensor suite (MagI2C ASIC, 2x Sen-XY-f, 1x Sen-Z-f)
on a small remote board, mounted >= 8 cm from torquers and reaction wheels (location TBD with Structures, 11/9 systems meeting allocated in the corner opposite of magnetorquers).

- Power: switched, current-monitored 3V3_MAG from the OBC over the J_MAG harness (proposed, unconfirmed).
- Connects to: OBC via 8-pin J_MAG harness: SPI mode 0, max 1 MHz, plus DRDY.
- Measures: 3-axis magnetic field for B-dot detumble and attitude determination. Backup: MMC5983MA on the OBC.

Design Master link: https://docs.google.com/spreadsheets/d/1Magy7Pv5RpWoOE26eidlDhtyJ_tfjOZqjaHxG35c-vI/edit?usp=sharing

Status: schematic in progress. Owner: Marlon Moenius.

## Datasheets

| File | Document | Doc no. | Rev | Retrieved |
|---|---|---|---|---|
| `datasheets/RM3100_1017252_r06.pdf` | RM3100 & RM2100 Sensor Suite User Manual (PNI Sensor) | 1017252 | r06 | 2026-11-11 |

Values used from this revision: R_bias = 121 Ω, R_EXT = 33 kΩ (Table 3-1, p. 5, specified at 3.0 V);
pin table (§4.3, p. 19); SPI reference schematic (Fig. 4-1, p. 15); coil orientation (§4.2.1 and Fig. 4-4, pp. 17–18);
pad layouts (Fig. 3-3 p. 9, Fig. 3-6 p. 11); MagI2C package (Fig. 3-7 p. 12).
Assembly: PNI sensor coils require halide-free solder paste and processes (§3.5, p. 13).

## Datasheets

| File | Document | Doc no. | Rev | Retrieved |
|---|---|---|---|---|
| `datasheets/RM3100_1017252_r06.pdf` | RM3100 & RM2100 Sensor Suite User Manual (PNI Sensor) | 1017252 | r06 | 2026-11-11 |

Values used from this revision: R_bias = 121 Ω, R_EXT = 33 kΩ (Table 3-1, p. 5, specified at 3.0 V);
pin table (§4.3, p. 19); SPI reference schematic (Fig. 4-1, p. 15); coil orientation (§4.2.1 and Fig. 4-4, pp. 17–18);
pad layouts (Fig. 3-3 p. 9, Fig. 3-6 p. 11); MagI2C package (Fig. 3-7 p. 12).
Assembly: PNI sensor coils require halide-free solder paste and processes (§3.5, p. 13).
