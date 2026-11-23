#include "drive.h"

#include <limits.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "hardware/irq.h"
#include "hardware/sync.h"
#include "pico/stdlib.h"

#if ROTOR_USE_CAN2040
#include <stdatomic.h>
#include "can2040.h"
#include "pico/multicore.h"
#endif

enum {
    PIN_CAN_TX = 2,
    PIN_CAN_RX = 3,
    PIN_TEMP_SDA = 4,
    PIN_TEMP_SCL = 5,
    PIN_WATCHDOG = 6,
    PIN_BRIDGE_SLEEP_N = 21,
    TEMP_ADDR = 0x48,
    TEMP_READ_INTERVAL_US = 150000,
    TEMP_BUS_TIMEOUT_US = 1000,
    WATCHDOG_EDGE_INTERVAL_US = 50000,
    DRIVE_STATUS_INTERVAL_US = 1000,
    // TMP100 is on the PCB. These are bench interlocks on the PCB temperature.
    TEMP_TRIP_HALF_C = 130,
    TEMP_REARM_HALF_C = 120,
};

typedef enum {
    APP_FAULT_NONE = 0,
    APP_FAULT_INIT,
    APP_FAULT_TEMP_IO,
    APP_FAULT_TEMP_HIGH,
    APP_FAULT_CAN_OVERFLOW,
    APP_FAULT_LEASE,
} app_fault_t;

static bool drive_ready;
static app_fault_t app_fault;
static bool armed;
static uint32_t last_command_us;
static bool temperature_configured;
static bool temperature_valid;
static int16_t temperature_half_c;
static uint32_t last_temperature_us;
static uint32_t last_watchdog_edge_us;
static uint32_t last_drive_status_us;
static bool watchdog_level;

static void trip(app_fault_t cause)
{
    if (app_fault == APP_FAULT_NONE) {
        app_fault = cause;
    }
    if (armed) {
        drive_arm(false);
        armed = false;
    }
}

static void service_temperature(uint32_t now)
{
    if (now - last_temperature_us < TEMP_READ_INTERVAL_US) {
        return;
    }
    last_temperature_us = now;

    if (!temperature_configured) {
        // Continuous conversions, 9-bit (0.5 °C) resolution.
        const uint8_t config[] = {1, 0};
        temperature_configured =
            i2c_write_timeout_us(i2c0, TEMP_ADDR, config, sizeof(config), false,
                                 TEMP_BUS_TIMEOUT_US) == sizeof(config);
        if (!temperature_configured) {
            trip(APP_FAULT_TEMP_IO);
        }
        return;
    }

    const uint8_t reg = 0;
    uint8_t data[2];
    if (i2c_write_timeout_us(i2c0, TEMP_ADDR, &reg, 1, true, TEMP_BUS_TIMEOUT_US) != 1 ||
        i2c_read_timeout_us(i2c0, TEMP_ADDR, data, sizeof(data), false,
                            TEMP_BUS_TIMEOUT_US) != sizeof(data)) {
        temperature_valid = false;
        temperature_configured = false;
        // Reset the controller state after a timeout during a repeated start.
        i2c_deinit(i2c0);
        i2c_init(i2c0, 100000);
        trip(APP_FAULT_TEMP_IO);
        return;
    }

    int raw = (data[0] << 1) | (data[1] >> 7);
    temperature_half_c = (int16_t)(raw >= 256 ? raw - 512 : raw);
    temperature_valid = temperature_half_c >= -80 && temperature_half_c <= 250;
    if (!temperature_valid) {
        trip(APP_FAULT_TEMP_IO);
    } else if (temperature_half_c >= TEMP_TRIP_HALF_C) {
        trip(APP_FAULT_TEMP_HIGH);
    }
}

static void service_watchdog(uint32_t now)
{
    if (now - last_watchdog_edge_us >= WATCHDOG_EDGE_INTERVAL_US) {
        watchdog_level = !watchdog_level;
        gpio_put(PIN_WATCHDOG, watchdog_level);
        last_watchdog_edge_us = now;
    }
}

#if ROTOR_USE_CAN2040
enum {
    CAN_COMMAND_ID = 0x300 + ROTOR_CAN_NODE_ID,
    CAN_REPLY_ID = 0x380 + ROTOR_CAN_NODE_ID,
    CAN_QUEUE_SIZE = 8,
    CMD_STATUS = 0x00,
    CMD_TELEMETRY = 0x01,
    CMD_PHASE_SAMPLE = 0x02,
    CMD_DISARM = 0x10,
    CMD_ARM = 0x11,
    CMD_SPEED = 0x12,
    CMD_CONFIG_RESET = 0x20,
    CMD_CONFIG_HALL = 0x21,
    CMD_CONFIG_PARAMETER = 0x22,
    CMD_CONFIG_COMMIT = 0x23,
    REPLY_OK = 0,
    REPLY_FORMAT,
    REPLY_STATE,
    REPLY_RANGE,
    REPLY_INCOMPLETE,
    REPLY_INHIBITED,
};

_Static_assert(ROTOR_CAN_NODE_ID >= 0 && ROTOR_CAN_NODE_ID <= 0x7f, "CAN node ID 0–127");
_Static_assert(ROTOR_CAN_BITRATE > 0 && ROTOR_CAN_BITRATE <= 1000000, "Classical CAN bitrate");
_Static_assert(sizeof(float) == sizeof(uint32_t), "CAN parameters use binary32");

typedef struct {
    struct can2040_msg frame;
    uint32_t received_us;
} command_t;

static struct can2040 can;
// Single producer and single consumer per ring. Each publishes its own
// index after writing or reading a slot. No locks or cross-core IRQs.
_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "CAN rings require lock-free unsigned atomics");
static command_t commands[CAN_QUEUE_SIZE];
static struct can2040_msg replies[CAN_QUEUE_SIZE];
static _Atomic unsigned rx_head, rx_tail, tx_head, tx_tail;
static _Atomic unsigned rx_overflow_epoch;
static unsigned handled_rx_overflow;
static drive_calibration_t staged;
static uint8_t staged_hall;
static uint8_t staged_parameters;
static bool staging_open;
static bool configuration_committed;

static void on_can_event(struct can2040 *device, uint32_t event, struct can2040_msg *frame)
{
    (void)device;
    if (event == CAN2040_NOTIFY_ERROR) {
        // Only core 1's IRQ writes the epoch. Core 0 records what it handled.
        unsigned epoch = atomic_load_explicit(&rx_overflow_epoch, memory_order_relaxed);
        atomic_store_explicit(&rx_overflow_epoch, epoch + 1u, memory_order_release);
        return;
    }
    if (event != CAN2040_NOTIFY_RX || frame->id != CAN_COMMAND_ID || !frame->dlc ||
        frame->dlc > sizeof(frame->data)) {
        return;
    }

    unsigned head = atomic_load_explicit(&rx_head, memory_order_relaxed);
    unsigned next = (head + 1) % CAN_QUEUE_SIZE;
    if (next == atomic_load_explicit(&rx_tail, memory_order_acquire)) {
        unsigned epoch = atomic_load_explicit(&rx_overflow_epoch, memory_order_relaxed);
        atomic_store_explicit(&rx_overflow_epoch, epoch + 1u, memory_order_release);
        return;
    }
    commands[head] = (command_t){.frame = *frame, .received_us = time_us_32()};
    atomic_store_explicit(&rx_head, next, memory_order_release);
}

static void __not_in_flash_func(can_irq)(void)
{
    can2040_pio_irq_handler(&can);
    // A TX slot may have opened while the foreground was about to sleep.
    __sev();
}

static void can_core(void)
{
    can2040_setup(&can, 0);
    can2040_callback_config(&can, on_can_event);
    irq_set_exclusive_handler(PIO0_IRQ_0, can_irq);
    irq_set_priority(PIO0_IRQ_0, PICO_HIGHEST_IRQ_PRIORITY);
    can2040_start(&can, clock_get_hz(clk_sys), ROTOR_CAN_BITRATE, PIN_CAN_RX, PIN_CAN_TX);
    irq_set_enabled(PIO0_IRQ_0, true);

    for (;;) {
        unsigned tail = atomic_load_explicit(&tx_tail, memory_order_relaxed);
        if (tail != atomic_load_explicit(&tx_head, memory_order_acquire) &&
            can2040_transmit(&can, &replies[tail]) == 0) {
            atomic_store_explicit(&tx_tail, (tail + 1) % CAN_QUEUE_SIZE, memory_order_release);
        } else {
            __wfe();
        }
    }
}

static void queue_reply(const struct can2040_msg *frame)
{
    unsigned head = atomic_load_explicit(&tx_head, memory_order_relaxed);
    unsigned next = (head + 1) % CAN_QUEUE_SIZE;
    if (next == atomic_load_explicit(&tx_tail, memory_order_acquire)) {
        trip(APP_FAULT_CAN_OVERFLOW);
        return;
    }
    replies[head] = *frame;
    atomic_store_explicit(&tx_head, next, memory_order_release);
    // Complete publication before waking a core that may be in WFE.
    __dsb();
    __sev();
}

static uint16_t read_u16(const uint8_t *data)
{
    return (uint16_t)(data[0] | (data[1] << 8));
}

static int read_i16(const uint8_t *data)
{
    const uint16_t value = read_u16(data);
    return value >= 0x8000 ? (int)value - 0x10000 : value;
}

static void put_u16(uint8_t *data, uint16_t value)
{
    data[0] = (uint8_t)value;
    data[1] = (uint8_t)(value >> 8);
}

static uint16_t telemetry_word(float value)
{
    if (!isfinite(value)) {
        return 0x8000;
    }
    if (value < INT16_MIN + 1) {
        return (uint16_t)(INT16_MIN + 1);
    }
    if (value > INT16_MAX) {
        return INT16_MAX;
    }
    return (uint16_t)(int16_t)lroundf(value);
}

static void reply(uint8_t opcode, uint8_t result)
{
    const drive_status_t *status = drive_status();
    struct can2040_msg frame = {
        .id = CAN_REPLY_ID,
        .dlc = 8,
        .data = {opcode, result, status->state, status->fault, app_fault,
                 (uint8_t)(status->hall_state | (status->calibrated ? 0x80 : 0))},
    };
    put_u16(&frame.data[6], status->driver_status);
    queue_reply(&frame);
}

static void reply_telemetry(void)
{
    const drive_status_t *status = drive_status();
    struct can2040_msg frame = {.id = CAN_REPLY_ID, .dlc = 8, .data = {CMD_TELEMETRY}};
    frame.data[1] = temperature_valid ? (uint8_t)(temperature_half_c / 2) : 0x80;
    put_u16(&frame.data[2], telemetry_word(status->speed_rpm));
    put_u16(&frame.data[4], telemetry_word(status->target_rpm));
    put_u16(&frame.data[6], telemetry_word(status->iq_a * 1000.0f));
    queue_reply(&frame);
}

static void reply_phase_sample(void)
{
    const drive_status_t *status = drive_status();
    const uint32_t age = time_us_32() - status->sample_time_us;
    bool fresh = status->state == DRIVE_RUNNING && status->cycle_count && age < UINT16_MAX;
    struct can2040_msg frame = {
        .id = CAN_REPLY_ID,
        .dlc = 8,
        .data = {CMD_PHASE_SAMPLE, fresh ? 1 : 0},
    };
    put_u16(&frame.data[2], fresh ? status->adc_a : UINT16_MAX);
    put_u16(&frame.data[4], fresh ? status->adc_b : UINT16_MAX);
    put_u16(&frame.data[6], fresh ? (uint16_t)age : UINT16_MAX);
    queue_reply(&frame);
}

static uint8_t configure(uint8_t opcode, const uint8_t *data, uint32_t len)
{
    if (drive_status()->state != DRIVE_DISARMED ||
        (opcode != CMD_CONFIG_RESET && !staging_open)) {
        return REPLY_STATE;
    }

    switch (opcode) {
    case CMD_CONFIG_RESET:
        if (len != 1) {
            return REPLY_FORMAT;
        }
        staged = (drive_calibration_t){0};
        staged_hall = 0;
        staged_parameters = 0;
        staging_open = true;
        configuration_committed = false;
        return REPLY_OK;
    case CMD_CONFIG_HALL: {
        if (len != 8 || data[1] >= 3) {
            return REPLY_FORMAT;
        }
        const unsigned pair = data[1];
        const uint8_t first = data[2];
        const uint8_t second = data[5];
        if (first < 1 || first > 6 || second < 1 || second > 6) {
            return REPLY_RANGE;
        }
        const float radians_per_count = 6.283185307179586f / 65536.0f;
        staged.hall_order[2 * pair] = first;
        staged.hall_order[2 * pair + 1] = second;
        staged.hall_entry_rad[2 * pair] = read_u16(&data[3]) * radians_per_count;
        staged.hall_entry_rad[2 * pair + 1] = read_u16(&data[6]) * radians_per_count;
        staged_hall |= (uint8_t)(1u << pair);
        return REPLY_OK;
    }
    case CMD_CONFIG_PARAMETER: {
        float *const parameters[] = {
            &staged.current_kp_per_a, &staged.current_ki_per_a_s,
            &staged.speed_kp_a_per_rpm, &staged.speed_ki_a_per_rpm_s,
            &staged.phase_peak_limit_a, &staged.max_speed_rpm,
        };
        if (len != 6 || data[1] >= sizeof(parameters) / sizeof(parameters[0])) {
            return REPLY_FORMAT;
        }
        const uint32_t bits = (uint32_t)read_u16(&data[2]) |
                              ((uint32_t)read_u16(&data[4]) << 16);
        float value;
        memcpy(&value, &bits, sizeof(value));
        if (!isfinite(value) || value <= 0.0f) {
            return REPLY_RANGE;
        }
        *parameters[data[1]] = value;
        staged_parameters |= (uint8_t)(1u << data[1]);
        return REPLY_OK;
    }
    case CMD_CONFIG_COMMIT:
        if (len != 1) {
            return REPLY_FORMAT;
        }
        if (staged_hall != 0x07 || staged_parameters != 0x3f) {
            return REPLY_INCOMPLETE;
        }
        if (!drive_set_calibration(&staged)) {
            return REPLY_RANGE;
        }
        staging_open = false;
        configuration_committed = true;
        return REPLY_OK;
    default:
        return REPLY_FORMAT;
    }
}

static uint8_t process_command(const command_t *command)
{
    const struct can2040_msg *frame = &command->frame;
    const uint8_t opcode = frame->data[0];
    switch (opcode) {
    case CMD_STATUS:
        return frame->dlc == 1 ? REPLY_OK : REPLY_FORMAT;
    case CMD_TELEMETRY:
    case CMD_PHASE_SAMPLE:
        return REPLY_FORMAT;
    case CMD_DISARM:
        if (frame->dlc != 1) {
            return REPLY_FORMAT;
        }
        if (drive_ready) {
            drive_arm(false);
        }
        armed = false;
        if (drive_ready && temperature_valid && temperature_half_c < TEMP_REARM_HALF_C) {
            app_fault = APP_FAULT_NONE;
        }
        return REPLY_OK;
    case CMD_ARM:
        if (frame->dlc != 2 || frame->data[1] != 0xa5) {
            return REPLY_FORMAT;
        }
        if (!drive_ready || !temperature_valid || app_fault != APP_FAULT_NONE) {
            return REPLY_INHIBITED;
        }
        if (armed || !configuration_committed || !drive_arm(true)) {
            return REPLY_STATE;
        }
        armed = true;
        last_command_us = command->received_us;
        return REPLY_OK;
    case CMD_SPEED: {
        if (frame->dlc != 3) {
            return REPLY_FORMAT;
        }
        const int rpm = read_i16(&frame->data[1]);
        if (!armed) {
            return REPLY_STATE;
        }
        if ((float)rpm < -DRIVE_MAX_RPM || (float)rpm > DRIVE_MAX_RPM) {
            return REPLY_RANGE;
        }
        const bool accepted = drive_set_speed_rpm((float)rpm);
        const drive_state_t state = drive_status()->state;
        if (state != DRIVE_ARMED_IDLE && state != DRIVE_RUNNING) {
            armed = false;
        }
        if (!accepted) {
            return armed ? REPLY_RANGE : REPLY_STATE;
        }
        last_command_us = command->received_us;
        return REPLY_OK;
    }
    default:
        return drive_ready ? configure(opcode, frame->data, frame->dlc) : REPLY_INHIBITED;
    }
}

static void service_can(void)
{
    unsigned epoch = atomic_load_explicit(&rx_overflow_epoch, memory_order_acquire);
    unsigned head = atomic_load_explicit(&rx_head, memory_order_acquire);
    if (epoch != handled_rx_overflow) {
        handled_rx_overflow = epoch;
        atomic_store_explicit(&rx_tail, head, memory_order_release);
        trip(APP_FAULT_CAN_OVERFLOW);
        return;
    }

    unsigned tail = atomic_load_explicit(&rx_tail, memory_order_relaxed);
    if (tail == head) {
        return;
    }
    command_t command = commands[tail];
    atomic_store_explicit(&rx_tail, (tail + 1) % CAN_QUEUE_SIZE, memory_order_release);

    const uint8_t opcode = command.frame.data[0];
    if (time_us_32() - command.received_us >= DRIVE_COMMAND_LEASE_MS * 1000u &&
        opcode != CMD_DISARM) {
        reply(opcode, REPLY_INHIBITED);
    } else if (opcode == CMD_TELEMETRY && command.frame.dlc == 1) {
        reply_telemetry();
    } else if (opcode == CMD_PHASE_SAMPLE && command.frame.dlc == 1) {
        reply_phase_sample();
    } else {
        reply(opcode, process_command(&command));
    }
}
#endif

int main(void)
{
    // A reset or early boot never enables the bridge.
    gpio_init(PIN_BRIDGE_SLEEP_N);
    gpio_put(PIN_BRIDGE_SLEEP_N, false);
    gpio_set_input_enabled(PIN_BRIDGE_SLEEP_N, false);
    gpio_set_dir(PIN_BRIDGE_SLEEP_N, GPIO_OUT);
    gpio_init(PIN_WATCHDOG);
    gpio_put(PIN_WATCHDOG, false);
    gpio_set_dir(PIN_WATCHDOG, GPIO_OUT);

    // Hold the CAN transceiver recessive until the PIO state machines take over.
    gpio_init(PIN_CAN_TX);
    gpio_put(PIN_CAN_TX, true);
    gpio_set_dir(PIN_CAN_TX, GPIO_OUT);

    i2c_init(i2c0, 100000);
    gpio_set_function(PIN_TEMP_SDA, GPIO_FUNC_I2C);
    gpio_set_function(PIN_TEMP_SCL, GPIO_FUNC_I2C);
    last_temperature_us = time_us_32() - TEMP_READ_INTERVAL_US;

    drive_ready = drive_init();
    if (!drive_ready) {
        trip(APP_FAULT_INIT);
    }
#if ROTOR_USE_CAN2040
    // Complete the SDK launch handshake while the drive is disarmed.
    // PIO0_IRQ_0 is enabled only on core 1.
    multicore_launch_core1(can_core);
#endif

    for (;;) {
        const uint32_t now = time_us_32();
        if (drive_ready) {
            drive_service();
            if (armed && now - last_drive_status_us >= DRIVE_STATUS_INTERVAL_US) {
                last_drive_status_us = now;
                const drive_state_t state = drive_status()->state;
                if (state != DRIVE_ARMED_IDLE && state != DRIVE_RUNNING) {
                    armed = false;
                }
            }
        }
        if (armed && now - last_command_us >= DRIVE_COMMAND_LEASE_MS * 1000u) {
            trip(APP_FAULT_LEASE);
        }
        service_temperature(now);
#if ROTOR_USE_CAN2040
        service_can();
#endif
        service_watchdog(time_us_32());
        tight_loop_contents();
    }
}
