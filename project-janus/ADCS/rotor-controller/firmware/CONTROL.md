# Bench control interface

The application starts disarmed with DRV8311 nSLEEP low. Calibration lives in RAM and must be recommissioned after reset. Power the controller with the qualified, protected 2S bridge supply and regulated 3.3 V logic rail. Connect a CAN adapter and terminate each end of the bus. Use SWD for programming and recovery.

The default image uses Classical CAN at 500 kbit/s with standard 11-bit identifiers. The build sets the bitrate and node number. Node 0 receives commands on `0x300` and transmits replies on `0x380`. Add the node number to each base identifier. Use one command source on an isolated bench bus. GP2 is CAN TX, GP3 is CAN RX, and the implementation uses all four state machines of PIO0. Frames with an extended identifier, RTR flag, or empty payload are ignored.

## Commands

Every payload begins with one opcode. Multibyte fields are little-endian. Lengths include the opcode. Wait for each commissioning command's success reply before sending the next.

| Opcode | Bytes | Payload after opcode |
| --- | ---: | --- |
| `00` | 1 | Read controller status. |
| `01` | 1 | Read speed, q-axis current, and board temperature. |
| `02` | 1 | Read the latest inline phase-current ADC samples while running. |
| `10` | 1 | Disarm and coast. Acknowledge a latched fault after its cause has cleared. |
| `11` | 2 | Arm with confirmation byte `A5`. The shaft must be stopped with a valid Hall state and committed configuration. |
| `12` | 3 | Command signed integer rpm as `int16`, within the configured speed ceiling and the absolute ±3,000 rpm limit. Zero disarms and coasts. |
| `20` | 1 | Begin a fresh configuration while disarmed. This removes permission to arm until the next successful commit. |
| `21` | 8 | Set a pair of Hall boundaries. Supply pair index `0`, `1`, or `2`, then two records of `uint8 state, uint16 angle`. |
| `22` | 6 | Set one gain or limit. Supply parameter index followed by four bytes of IEEE 754 binary32. |
| `23` | 1 | Validate and commit all staged fields. |

Hall A is state bit 0, B is bit 1, and C is bit 2. Enter all six legal states in order of positive electrical rotation, starting at any one boundary. Each angle is the rotor flux angle at which the Hall signal **enters** that state in positive rotation. Encode it as `round((angle mod 2π) × 65536 / 2π) mod 65536`. Temporarily turn the shaft in the bench fixture with the bridge asleep. Use a shaft reference or scope the Hall signals and the motor's open-circuit phase voltages to establish direction, absolute electrical zero, and each boundary. Confirm 12 transitions per mechanical revolution in both directions. The distinct states and measured angular order are validated by the drive.

| Parameter | Units |
| --- | --- |
| 0 | Current-loop proportional gain, fraction of DC bus per ampere |
| 1 | Current-loop integral gain, fraction of DC bus per ampere-second |
| 2 | Speed-loop proportional gain, ampere per rpm |
| 3 | Speed-loop integral gain, ampere per rpm-second |
| 4 | Phase peak current limit in amperes, at most 0.100 A |
| 5 | Speed ceiling in rpm, at most 3,000 rpm |

Set positive, bench-validated gains. Begin with the shaft guarded, a low speed ceiling and current limit, and a current-limited motor supply with known reverse-current behavior. The ARM command calibrates the inline ADC zero with the bridge asleep after the Hall signals have been quiet. Validate both phase current signs and gain against an external measurement, including while PWM is running. Verify the Hall angle and running current at low speed and limit before raising them. The PCB temperature does not establish winding temperature or the tested motor's safe current limit.

## Replies

The board responds on its reply ID with 8 data bytes. Status and acknowledgments use this layout.

| Byte | Meaning |
| ---: | --- |
| 0 | Echoed request opcode |
| 1 | Result. `0` accepted, `1` format, `2` invalid state, `3` range or invalid calibration, `4` incomplete configuration, `5` inhibited |
| 2 | Drive state. `0` disarmed, `1` armed idle, `2` running, `3` faulted |
| 3 | Drive fault. `0` none, `1` bridge, `2` SPI, `3` Hall, `4` ADC, `5` current, `6` overspeed, `7` timing, `8` lease |
| 4 | Application fault. `0` none, `1` initialization, `2` I²C or invalid temperature, `3` board overtemperature, `4` CAN receive overflow, `5` command lease |
| 5 | Hall state in bits 0–2, active drive calibration in bit 7 |
| 6–7 | Drive bridge status word |

A valid `02` response uses byte 0 for opcode, byte 1 bit 0 for sample valid, bytes 2–3 for raw ADC A, bytes 4–5 for raw ADC B, and bytes 6–7 for sample age in microseconds. Invalid data fields are `0xFFFF`.

A valid `01` telemetry response uses byte 0 for opcode, byte 1 for signed board temperature in whole °C, bytes 2–3 for signed measured rpm, bytes 4–5 for signed requested rpm, and bytes 6–7 for signed q-axis current in mA. `0x80` temperature or signed `0x8000` data indicate unavailable values. Use status frames to read fault codes. If the transmit queue is full, a reply may be dropped. Query status to verify the state before resuming.

## Running and fault recovery

- On Linux SocketCAN, configure `can0` at 500 kbit/s and monitor replies with `candump can0`. `cansend can0 300#00` queries state. For node 0, after a successful commit send `300#11A5` to arm, then repeat valid speed frames at 20 Hz. For example, the frame for +100 rpm is `300#126400`. Issue `cansend can0 300#10` to disarm.
- The command lease is 250 ms from ARM or the latest accepted speed command. Status, telemetry, and rejected commands never renew it. Confirm that unplugging CAN causes coast. Following a fault, restore the bus, clear the underlying cause, send DISARM, check status, then ARM and resume commands. To reverse, first command zero, wait for the shaft to stop, then re-arm and command the other direction. A direction change requested while running forces coast.
- The TMP100 at address `0x48` uses GP4/GP5. The bench PCB temperature interlock trips at 65 °C. The reading must be valid and below 60 °C before DISARM can clear an application fault. The GP6 watchdog is driven by the foreground loop with a falling edge every 100 ms. Confirm that it resets the MCU when servicing stops and that the bridge remains asleep through reset. Use the normally open JP1 service jumper to inhibit the watchdog while programming. Clear the solder bridge and verify JP1 is open before running.
- The driver and can2040 IRQ both have real-time deadlines. Exercise the active drive under full expected CAN load while scoping PWM and ADC timing. Verify that a timing or ADC fault forces coast, the intended steady-state speed is achievable at the minimum loaded bus voltage, and a coasting rotor does not produce a bus overvoltage. The CAN lease acts independently of CAN controller fault states.

## CAN dependency

The normal firmware build includes [can2040 v1.7.0](https://github.com/KevinOConnor/can2040/tree/90515f53ce89442f1bcc3033aae222e9eb77818c), pinned by commit. It supports CAN 2.0B on RP2350. It is GNU GPLv3 software. Distribution of the combined CAN firmware requires GPLv3-compatible terms, the required notices and license text, and corresponding source including the pinned library and build scripts. The existing hardware design files are separate from that firmware. The optional build with `ROTOR_USE_CAN2040=OFF` remains idle.

The CAN build runs can2040 and its PIO0 IRQ exclusively on core 1. Core 0 owns the Hall sensing, PWM, ADC, drive state and watchdog. Two SRAM rings carry up to seven pending commands and seven pending replies across cores. Each ring has one writer and one reader using acquire/release atomics. CAN backlog or receive overflow disarms the drive. Verify ADC aperture and PWM timing with the CAN bus heavily loaded as well as idle. The cores still share SRAM and peripheral buses.

can2040 receives error frames but does not send them or automatically enter the CAN error-passive or bus-off states. The command lease and manual re-arm govern motor behavior during communication loss. Verify the required network error confinement before connecting this bench image to the vehicle network. [can2040 protocol limitations](https://github.com/KevinOConnor/can2040/blob/90515f53ce89442f1bcc3033aae222e9eb77818c/docs/Features.md)
