# Package STEP models

The origin of each model is at the package center on the PCB seating plane. Dimensions are in millimeters.

- `RP2350A_QFN60.step` is a project-generated package with a 7 × 7 × 0.85 body, sixty 0.18 × 0.40 terminals on 0.40 pitch, and a 3.40 × 3.40 exposed pad. [Raspberry Pi RP2350 datasheet §14.1](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)
- `Texas_DSG0008A_WSON-8.step` is the KiCad `WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm` model. The STEP header includes the KiCad StepUp copyright and CC BY-SA 4.0 license with its electronic-design exception. The PCB model scales the 0.82 mm stock height to TI's 0.80 mm maximum. [KiCad STEP library](https://gitlab.com/kicad/libraries/kicad-packages3D) · [TI TPS62172 datasheet, DSG0008A drawing](https://www.ti.com/lit/ds/symlink/tps62172.pdf)
- `Coilcraft_XFL2010.step` is a project-generated model with a 1.90 × 2.00 body and 1.00 maximum mounted height, with the start-lead mark at pad 1. [Coilcraft XFL2010 drawing, Document 1690-2](https://www.coilcraft.com/getmedia/50382b97-998f-4b75-b5ee-4a93b0ac4411/xfl2010.pdf)
