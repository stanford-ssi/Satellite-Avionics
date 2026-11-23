#include <stdbool.h>
#include <stdint.h>
#include "hardware/gpio.h"
#include "hardware/regs/qmi.h"
#include "hardware/structs/qmi.h"
#include "pico/bootrom.h"
#include "pico/time.h"

enum {
    MRAM_SIZE = 512 * 1024,
    TRANSFER_CAPACITY = 16 * 1024,
    DRIVE_WAKE_PIN = 21,
    SPI_DIVIDER = 32,
    MRAM_CMD_READ = 0x03,
    MRAM_CMD_WRITE = 0x02,
    MRAM_CMD_READ_STATUS = 0x05,
    MRAM_CMD_ENABLE_WRITE = 0x06,
    MRAM_CMD_DISABLE_WRITE = 0x04,
    MRAM_WRITE_ENABLE = 1u << 1,
    MRAM_BLOCK_PROTECT = 3u << 2,
};

enum {
    REQUEST_READ = 1,
    REQUEST_WRITE = 2,
};

enum {
    RESULT_OK,
    RESULT_BAD_REQUEST,
    RESULT_WRITE_PROTECTED,
    RESULT_VERIFY_FAILED,
};

// SWD host mailbox. Symbols are deliberately visible in the SRAM ELF.
volatile uint32_t mram_request;
volatile uint32_t mram_result;
volatile uint32_t mram_address;
volatile uint32_t mram_size;
volatile uint32_t mram_fail_address;
volatile uint8_t mram_data[TRANSFER_CAPACITY];

__attribute__((noinline)) void mram_programmer_ready(void) {
    // Host stops here on a hardware breakpoint before each request.
    __asm volatile ("" ::: "memory");
}

static const uint32_t direct_mode =
    (SPI_DIVIDER << QMI_DIRECT_CSR_CLKDIV_LSB) | QMI_DIRECT_CSR_EN_BITS;

static void select_mram(void) {
    // The supported part requires CS high for at least 40 ns between commands.
    busy_wait_us_32(1);
    qmi_hw->direct_csr = direct_mode | QMI_DIRECT_CSR_ASSERT_CS0N_BITS;
}

static void deselect_mram(void) {
    while (qmi_hw->direct_csr & QMI_DIRECT_CSR_BUSY_BITS) {
        tight_loop_contents();
    }
    qmi_hw->direct_csr = direct_mode;
}

static uint8_t transfer(uint8_t byte) {
    // Every byte is drained from RX before the next byte is queued.
    qmi_hw->direct_tx = byte;
    while (qmi_hw->direct_csr & QMI_DIRECT_CSR_RXEMPTY_BITS) {
        tight_loop_contents();
    }
    return (uint8_t)qmi_hw->direct_rx;
}

static void command(uint8_t opcode) {
    select_mram();
    transfer(opcode);
    deselect_mram();
}

static uint8_t read_status(void) {
    select_mram();
    transfer(MRAM_CMD_READ_STATUS);
    uint8_t status = transfer(0);
    deselect_mram();
    return status;
}

static void address_command(uint8_t opcode, uint32_t address) {
    select_mram();
    transfer(opcode);
    transfer((uint8_t)(address >> 16));
    transfer((uint8_t)(address >> 8));
    transfer((uint8_t)address);
}

static uint32_t write_and_verify(uint32_t address, uint32_t length) {
    command(MRAM_CMD_ENABLE_WRITE);
    uint8_t status = read_status();
    if ((status & (MRAM_WRITE_ENABLE | MRAM_BLOCK_PROTECT)) != MRAM_WRITE_ENABLE) {
        command(MRAM_CMD_DISABLE_WRITE);
        return RESULT_WRITE_PROTECTED;
    }

    address_command(MRAM_CMD_WRITE, address);
    for (uint32_t i = 0; i < length; i++) {
        transfer(mram_data[i]);
    }
    deselect_mram();
    command(MRAM_CMD_DISABLE_WRITE);

    address_command(MRAM_CMD_READ, address);
    uint32_t result = RESULT_OK;
    for (uint32_t i = 0; i < length; i++) {
        if (transfer(0) != mram_data[i]) {
            mram_fail_address = address + i;
            result = RESULT_VERIFY_FAILED;
            break;
        }
    }
    deselect_mram();
    return result;
}

int main(void) {
    // PCB pull-down holds nSLEEP low during reset. Keep it actively low as a
    // second measure while SWD owns the MCU.
    gpio_init(DRIVE_WAKE_PIN);
    gpio_put(DRIVE_WAKE_PIN, false);
    gpio_set_input_enabled(DRIVE_WAKE_PIN, false);
    gpio_set_dir(DRIVE_WAKE_PIN, GPIO_OUT);

    // All code/data are in SRAM or ROM. Do not call the NOR flash driver.
    rom_connect_internal_flash();
    qmi_hw->direct_csr = direct_mode;
    deselect_mram();
    while (!(qmi_hw->direct_csr & QMI_DIRECT_CSR_RXEMPTY_BITS)) {
        (void)qmi_hw->direct_rx;
    }
    busy_wait_us_32(1000);

    for (;;) {
        mram_programmer_ready();
        uint32_t request = mram_request;
        uint32_t address = mram_address;
        uint32_t length = mram_size;
        mram_request = 0;
        if (request == 0) {
            continue;
        }
        mram_fail_address = address;
        if (!length || length > TRANSFER_CAPACITY || address >= MRAM_SIZE ||
            length > MRAM_SIZE - address) {
            mram_result = RESULT_BAD_REQUEST;
        } else if (request == REQUEST_WRITE) {
            mram_result = write_and_verify(address, length);
        } else if (request == REQUEST_READ) {
            address_command(MRAM_CMD_READ, address);
            for (uint32_t i = 0; i < length; i++) {
                mram_data[i] = transfer(0);
            }
            deselect_mram();
            mram_result = RESULT_OK;
        } else {
            mram_result = RESULT_BAD_REQUEST;
        }
    }
}
