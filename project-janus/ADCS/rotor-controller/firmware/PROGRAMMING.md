# Build and program Finertia

The RP2350A boots an Arm Secure image from the board’s 512 KiB MR25H40. Boot ROM scans for an `IMAGE_DEF` within the first 4 KiB and supports the MRAM’s `03h` 24-bit single-SPI read. The application includes an SRAM-executed XIP setup routine that sets SCK to `clk_sys / 8` before the SDK switches clocks. At 150 MHz that is 18.75 MHz, with at least 60 ns between chip-select assertions. Startup copies the control and CAN code into SRAM. The board’s USB data pins are unconnected.

## Build

Install CMake, Ninja, the Pico SDK 2.2.0, an Arm GNU `arm-none-eabi` toolchain including newlib, Python 3, `arm-none-eabi-gdb`, and a Pico-compatible OpenOCD with `target/rp2350.cfg`. On the tested host, the compiler with newlib was the Arm GNU 14.2.Rel1 bundle under the Pico VS Code extension. [Pico SDK](https://github.com/raspberrypi/pico-sdk/tree/2.2.0) · [Pico OpenOCD](https://github.com/raspberrypi/openocd)

From the controller’s `firmware/` directory, with the compiler on `PATH`:

    cmake -S . -B build -G Ninja -DPICO_SDK_PATH=/path/to/pico-sdk
    cmake --build build

This produces `build/bleps_wheel.bin`, `build/bleps_wheel.elf` and `build/mram_programmer.elf`. The normal build fetches can2040 v1.7.0, which is GPLv3. Configure the vehicle bitrate and wheel node with `-DROTOR_CAN_BITRATE=500000 -DROTOR_CAN_NODE_ID=0`, replacing those defaults as needed. For a build without CAN, pass `-DROTOR_USE_CAN2040=OFF`. To compile just the programmer, pass `-DROTOR_PROGRAMMER_ONLY=ON`. [can2040](https://github.com/KevinOConnor/can2040/tree/v1.7.0)

## First programming and recovery

1. Leave J201.1 motor VBATT disconnected. Supply regulated 3.3 V to J201.4 with return to J201.2 or J201.5. With logic power off and the motor detached, solder-bridge the normally open rear JP201 (WD PROG) to inhibit the external watchdog. Seat a TC2030-CTX-NL cable on J101 on the rear of the bare board. Use the normal Cortex orientation from the cable drawing. The fixture contacts are numbered as follows. [Tag-Connect cable drawing](https://www.tag-connect.com/wp-content/uploads/bsk-pdf-manager/TC2030-CTX_1.pdf)

   | J101 pin | Signal |
   | --- | --- |
   | 1 | 3.3 V target reference |
   | 2 | SWDIO |
   | 3 | Active-low RUN |
   | 4 | SWCLK |
   | 5 | GND |
   | 6 | Unconnected |

   For a Raspberry Pi Debug Probe, use an adapter from its three-wire debug port to SWCLK, GND and SWDIO on the cable. With a probe that exposes VTref, use J101.1 for the reference. The board’s separate supply provides target power.
2. Start OpenOCD for Arm core 0. This example uses the Raspberry Pi Debug Probe (CMSIS-DAP). Adjust the interface file for your probe. Supply `-s /path/to/openocd/scripts` if your installation requires a script path.

       openocd -f interface/cmsis-dap.cfg -c 'transport select swd' \
         -c 'set USE_CORE { cm0 }' -f target/rp2350.cfg -c 'adapter speed 1000' \
         -c 'gdb memory_map disable' -c 'gdb flash_program disable'

3. In a second terminal, load the programmer ELF through SWD and send the application as data.

       python3 programmer/program_mram.py --programmer build/mram_programmer.elf \
         --image build/bleps_wheel.bin --readback build/wheel-readback.bin

   The script works with blank MRAM. It resets and halts the core, loads the programmer into SRAM, and uses `06h`/`05h`/`02h`/`04h`/`03h` to enable, check, write, disable and read back. It invalidates the old boot search window, verifies the new image body and header, then writes the new IMAGE_DEF start marker as the final write. It compares a separate readback to the entire image and prints the SHA-256. Keep 3.3 V on until verification succeeds. If interrupted, rerun from step 3. A status of 2 means the memory did not report WEL set with block protection clear. A status of 3 means the reported address failed the immediate byte comparison. Resolve wiring, supply, or protection before retrying. The tool leaves protection bits and OTP untouched. Use this programmer for MRAM rather than the OpenOCD NOR programming flow.
4. Stop OpenOCD, remove the probe, disconnect logic power, clear the solder bridge from JP201, and verify the jumper is open. Power-cycle logic and verify watchdog operation before installing the motor. Confirm autonomous cold boot with VBATT still disconnected before starting powered commissioning. For a failed cold boot, check RUN_N at J101.3, logic at U101, and MRAM CS/SCK. The MRAM needs at least 400 µs after its rail reaches 3.0 V before selection. The fitted supervisor provides a nominal 200 ms delay. Verify it on the actual rail, and check reset and startup with both rail orders before energizing the bridge.

[RP2350 boot and QMI documentation](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf) · [Everspin MR25H40 command and timing tables](https://www.everspin.com/sites/default/files/EST00459_MR2xH40_Datasheet_Rev12.6_08092020.pdf)
