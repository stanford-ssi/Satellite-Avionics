# RM3100 magnetometer board (Janus)

Primary magnetometer for ADCS: PNI RM3100 sensor suite (MagI2C ASIC, 2x Sen-XY-f, 1x Sen-Z-f)
on a small remote board, mounted at least 8 cm from torquers and reaction wheels (location TBD with Structures).

- Power: switched, current-monitored 3V3_MAG from the OBC over the J_MAG harness (proposed).
- Connects to: OBC via 8-pin J_MAG harness: SPI mode 0, max 1 MHz, plus DRDY.
- Measures: 3-axis magnetic field for B-dot detumble and attitude determination. Backup: MMC5983MA on the OBC.

KiCad 10 project in this folder; vendor documents in `datasheets/`.
Status: schematic in progress. Owner: Marlon Moenius.
