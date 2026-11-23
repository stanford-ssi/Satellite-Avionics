#include "pico/asm_helper.S"
#include "hardware/regs/addressmap.h"
#include "hardware/regs/qmi.h"

pico_default_asm_setup
.section .text

// SRAM-executed before SDK clock setup. The ROM has already selected single-SPI
// 03h. Reapply that framing with a fixed timing for the application clock.
// At clk_sys=150 MHz, /8 gives 18.75 MHz SCK and 9 sysclks of deselect = 60 ns.
#define MRAM_TIMING (8 << QMI_M0_TIMING_CLKDIV_LSB | \
                     5 << QMI_M0_TIMING_MIN_DESELECT_LSB | \
                     1 << QMI_M0_TIMING_SELECT_SETUP_LSB | \
                     2 << QMI_M0_TIMING_SELECT_HOLD_LSB | \
                     2 << QMI_M0_TIMING_RXDELAY_LSB | \
                     1 << QMI_M0_TIMING_COOLDOWN_LSB)

regular_func _stage2_boot
    ldr r0, =XIP_QMI_BASE
    ldr r1, =MRAM_TIMING
    str r1, [r0, #QMI_M0_TIMING_OFFSET]
    ldr r1, =QMI_M0_RCMD_RESET
    str r1, [r0, #QMI_M0_RCMD_OFFSET]
    ldr r1, =QMI_M0_RFMT_RESET
    str r1, [r0, #QMI_M0_RFMT_OFFSET]
    // Commit the new divider before runtime_init switches to the PLL. Use the
    // no-cache XIP alias so the access must reach the QMI.
    dsb
    ldr r0, =XIP_NOCACHE_NOALLOC_BASE
    ldr r1, [r0]
    dsb
    isb
    bx lr
    .ltorg
