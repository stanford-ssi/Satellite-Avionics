#include "drive.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#include "hardware/adc.h"
#include "hardware/clocks.h"
#include "hardware/irq.h"
#include "hardware/pwm.h"
#include "hardware/spi.h"
#include "hardware/sync.h"
#include "hardware/timer.h"
#include "pico/stdlib.h"

#ifndef DRIVE_PWM_FREQUENCY_HZ
#define DRIVE_PWM_FREQUENCY_HZ 40000
#endif
#if DRIVE_PWM_FREQUENCY_HZ != 20000 && DRIVE_PWM_FREQUENCY_HZ != 40000
#error "The drive timing supports 20 kHz and 40 kHz only"
#endif

enum {
    hall_a = 10, spi_rx = 16, spi_cs = 17, spi_sck = 18, spi_tx = 19,
    driver_sync = 20, driver_wake = 21, driver_fault = 22,
    sense_a = 26, sense_b = 27,

    reg_device_status = 0x00,
    reg_sync_counts = 0x0c,
    reg_fault_mode = 0x10,
    reg_fault_clear = 0x17,
    reg_period = 0x18,
    reg_duty_a = 0x19,
    reg_phase_state = 0x1c,
    reg_pwm_control = 0x1d,
    reg_pwm_mode = 0x20,
    reg_system_control = 0x3f,

    driver_address = 0,
    driver_reset_status = 1 << 7,
    driver_parity_enable = 0x0040,
    driver_write_key = 0x5000,
    driver_pwm_measure_sync = 1 << 5,
    driver_pwm_lock_to_sync = 2 << 5,
    driver_pwm_enable = 1 << 10,
    driver_all_high_z = 0x0000,
    driver_complementary_pwm = 0x0777,

    pwm_frequency_hz = DRIVE_PWM_FREQUENCY_HZ,
    control_frequency_hz = 5000,
    control_divider = pwm_frequency_hz / control_frequency_hz,
    sample_lead_us = 2,
    ts_frame_timeout_us = 20,
    adc_timeout_us = 5,
    stopped_us = 250000,
    stall_us = 1500000,
    alarm_us = 2000,
    maximum_control_gap_us = 1000
};

static const float two_pi = 6.28318530718f;
static const float inv_sqrt_three = 0.57735026919f;
static const float sqrt_three_half = 0.86602540378f;
static const float control_dt = 1.0f / control_frequency_hz;
static const float adc_amp_per_code = 3.3f / (4096.0f * 5.0f);
// At 40 kHz this leaves a nominal 3.4 us of all-high conduction on each
// side of the sync edge. Keep the same absolute window when using 20 kHz.
static const float min_duty = 0.27f * pwm_frequency_hz / 40000.0f;
static const float max_duty = 0.995f;
static const float speed_ramp_rpm_s = 300.0f;

static volatile drive_status_t live;
static drive_calibration_t settings;
static int8_t hall_index[8];
static bool initialized;
static bool parity_enabled;
static volatile bool spi_requires_reset;
static uint sample_slice;
static float pwm_reference_counts;
static uint32_t pwm_counts_per_us;
static uint alarm_index;
static uint32_t hall_edge_us;
static volatile uint32_t control_time_us;
static uint32_t command_time_us;
static uint32_t started_us;
static uint32_t hall_interval_us;
static uint32_t armed_us;
static int direction;
static unsigned pwm_divider_count, missed_samples;
static uint16_t last_duty[3], pending_duty[3];
static bool duty_pending;
static float adc_zero_a, adc_zero_b;
static float speed_setpoint, speed_integral, id_integral, iq_integral;

static float clamp(float value, float low, float high)
{
    return fminf(high, fmaxf(low, value));
}

static float wrap_angle(float angle)
{
    if (angle >= two_pi) {
        return angle - two_pi;
    }
    if (angle < 0.0f) {
        return angle + two_pi;
    }
    return angle;
}

static uint8_t read_hall(void)
{
    return (uint8_t)((gpio_get_all() >> hall_a) & 7u);
}

static void coast(drive_fault_t fault)
{
    gpio_put(driver_wake, false);
    live.target_rpm = 0.0f;
    live.iq_a = 0.0f;
    live.state = fault == DRIVE_FAULT_NONE ? DRIVE_DISARMED : DRIVE_FAULTED;
    live.fault = fault;
    duty_pending = false;
    speed_setpoint = 0.0f;
    speed_integral = 0.0f;
    id_integral = 0.0f;
    iq_integral = 0.0f;
}

static uint16_t ts_word(uint16_t value, unsigned parity_bit)
{
    return (uint16_t)(value | ((unsigned)__builtin_parity((unsigned)value) << parity_bit));
}

static void setup_spi(void)
{
    spi_init(spi0, 5000000);
    spi_set_format(spi0, 16, SPI_CPOL_0, SPI_CPHA_1, SPI_MSB_FIRST);
    spi_requires_reset = false;
}

static bool ts_exchange(const uint16_t *tx, uint16_t *rx, size_t count)
{
    uint32_t started = time_us_32();
    spi_hw_t *hw = spi_get_hw(spi0);
    size_t sent = 0, received = 0;
    gpio_put(spi_cs, false);
    busy_wait_at_least_cycles(8);
    while (received < count || spi_is_busy(spi0)) {
        // The maximum frame is four words, within both eight-word FIFOs.
        if (sent < count && spi_is_writable(spi0)) {
            hw->dr = tx[sent++];
        }
        if (received < count && spi_is_readable(spi0)) {
            rx[received++] = (uint16_t)hw->dr;
        }
        if (time_us_32() - started >= ts_frame_timeout_us) {
            gpio_put(driver_wake, false);
            gpio_put(spi_cs, true);
            spi_requires_reset = true;
            return false;
        }
    }
    busy_wait_at_least_cycles(8);
    gpio_put(spi_cs, true);
    busy_wait_at_least_cycles(100);
    return true;
}

static bool ts_transfer(bool read, uint8_t reg, const uint16_t *values,
                        uint16_t *result, size_t count)
{
    uint16_t tx[4] = {0};
    uint16_t rx[4] = {0};

    // TI SLVSK12 Table 7-9. Header bits are relative to the first 16 bits
    // on the wire, so 15: R/W, 14:11: ADDR, 10:3: register, and 0: parity.
    tx[0] = (uint16_t)(((unsigned)read << 15) | (driver_address << 11) | (reg << 3));
    if (parity_enabled) {
        tx[0] = ts_word(tx[0], 0);
    }
    for (size_t i = 0; values && i < count; ++i) {
        tx[i + 1] = parity_enabled ? ts_word(values[i], 15) : values[i];
    }

    // RP2350 SPI0 is Mode 1 with manually framed, MSB-first 16-bit words.
    // Consecutive words share chip select, including the three duty words.
    if (!ts_exchange(tx, rx, count + 1)) {
        return false;
    }
    if (read) {
        for (size_t i = 0; i < count; ++i) {
            if (parity_enabled && __builtin_parity((unsigned)rx[i + 1])) {
                return false;
            }
            result[i] = rx[i + 1] & 0x7fffu;
        }
    }
    return true;
}

static bool read_reg(uint8_t reg, uint16_t *value)
{
    return ts_transfer(true, reg, NULL, value, 1);
}

static bool write_reg(uint8_t reg, uint16_t value)
{
    return ts_transfer(false, reg, &value, NULL, 1);
}

static bool configure_driver(void)
{
    uint16_t value;
    const unsigned nominal_counts = 20000000 / pwm_frequency_hz;
    parity_enabled = false;
    // RESET may be set until FLT_CLR. Any other status at wake is a fault.
    if (!read_reg(reg_device_status, &value) || (value & ~driver_reset_status) ||
        !read_reg(reg_pwm_mode, &value) || value != 7u ||
        !write_reg(reg_phase_state, driver_all_high_z) ||
        !write_reg(reg_system_control, driver_write_key | driver_parity_enable)) {
        return false;
    }

    parity_enabled = true;
    if (!read_reg(reg_system_control, &value) || value != driver_parity_enable ||
        !write_reg(reg_fault_mode, 0x0125) || // OCP latches, other defaults retained
        !write_reg(reg_period, nominal_counts / 2) ||
        !write_reg(reg_pwm_control, driver_pwm_measure_sync | driver_pwm_enable)) {
        return false;
    }

    // Mode 1 reports the driver's oscillator counts per reference period.
    // Mode 2 uses the external period and resets the up/down counter on each
    // reference edge. TI specifies mode 6 only for a 20 kHz reference.
    sleep_us(1000);
    if (!read_reg(reg_sync_counts, &value) ||
        value < nominal_counts * 9 / 10 || value > nominal_counts * 11 / 10) {
        return false;
    }
    pwm_reference_counts = 0.5f * value;

    uint16_t pwm_control = driver_pwm_lock_to_sync | driver_pwm_enable;
    return write_reg(reg_pwm_control, pwm_control) &&
           write_reg(reg_fault_clear, 1) &&
           read_reg(reg_pwm_control, &value) && value == pwm_control &&
           read_reg(reg_phase_state, &value) && value == driver_all_high_z;
}

static bool update_hall(uint32_t now)
{
    uint8_t next = read_hall();
    if (next == live.hall_state) {
        if (now - hall_edge_us >= stopped_us) {
            hall_interval_us = 0;
            direction = 0;
            live.speed_rpm = 0.0f;
        }
        return hall_index[next] >= 0;
    }

    int prior_index = hall_index[live.hall_state];
    int next_index = hall_index[next];
    uint32_t interval = now - hall_edge_us;
    live.hall_state = next;
    hall_edge_us = now;
    if (prior_index < 0 || next_index < 0) {
        hall_interval_us = 0;
        direction = 0;
        live.speed_rpm = 0.0f;
        return false;
    }

    int steps = (next_index - prior_index + 6) % 6;
    if (steps != 1 && steps != 5) {
        return false;
    }

    int new_direction = steps == 1 ? 1 : -1;
    // The interval that just finished was spent in the previous state
    // in either direction. Hall sectors need not have equal widths.
    float width = wrap_angle(settings.hall_entry_rad[(prior_index + 1) % 6] -
                             settings.hall_entry_rad[prior_index]);
    if (interval && interval < stopped_us) {
        float rpm = new_direction * width * 30000000.0f / (two_pi * interval);
        live.speed_rpm = direction == new_direction ?
                         0.5f * (live.speed_rpm + rpm) : rpm;
        hall_interval_us = interval;
    }
    direction = new_direction;
    return true;
}

static float hall_angle(uint32_t now)
{
    int index = hall_index[live.hall_state];
    float entry = settings.hall_entry_rad[index];
    float exit = settings.hall_entry_rad[(index + 1) % 6];
    float width = wrap_angle(exit - entry);
    if (!hall_interval_us || !direction) {
        return wrap_angle(entry + 0.5f * width);
    }

    // Convert the Hall-based speed estimate to rad/us for two pole pairs.
    float angle_delta = fabsf(live.speed_rpm) * (two_pi / 30000000.0f) *
                        (now - hall_edge_us);
    float traveled = fminf(width, angle_delta);
    return wrap_angle(direction > 0 ? entry + traveled : exit - traveled);
}

static bool read_current_adc(uint channel, uint16_t *raw)
{
    adc_select_input(channel);
    uint32_t started = time_us_32();
    hw_set_bits(&adc_hw->cs, ADC_CS_START_ONCE_BITS);
    while (!(adc_hw->cs & ADC_CS_READY_BITS)) {
        if (time_us_32() - started >= adc_timeout_us) {
            return false;
        }
    }
    if (adc_hw->cs & ADC_CS_ERR_BITS) {
        return false;
    }
    *raw = (uint16_t)adc_hw->result;
    return true;
}

static bool sample_currents(float *a, float *b)
{
    // Figure 7-11 centers high-side PWM at the sync rising edge. A separate
    // PWM slice schedules ADC0 followed by ADC1 across that edge.
    if (pwm_get_counter(sample_slice) > pwm_counts_per_us) {
        return false;
    }
    uint16_t raw_a, raw_b;
    if (!read_current_adc(0, &raw_a) || !read_current_adc(1, &raw_b)) {
        coast(DRIVE_FAULT_ADC);
        return false;
    }
    if (pwm_get_counter(sample_slice) >= 5u * pwm_counts_per_us) {
        return false;
    }

    live.adc_a = raw_a;
    live.adc_b = raw_b;
    live.sample_time_us = time_us_32();
    *a = (raw_a - adc_zero_a) * adc_amp_per_code;
    *b = (raw_b - adc_zero_b) * adc_amp_per_code;
    return true;
}

static void compute_duty(float alpha, float beta, uint16_t duty[3])
{
    float a = alpha;
    float b = -0.5f * alpha + sqrt_three_half * beta;
    float c = -0.5f * alpha - sqrt_three_half * beta;
    float offset = min_duty - fminf(a, fminf(b, c));
    duty[0] = (uint16_t)(clamp(a + offset, min_duty, max_duty) * pwm_reference_counts + 0.5f);
    duty[1] = (uint16_t)(clamp(b + offset, min_duty, max_duty) * pwm_reference_counts + 0.5f);
    duty[2] = (uint16_t)(clamp(c + offset, min_duty, max_duty) * pwm_reference_counts + 0.5f);
}

static void current_loop(uint32_t now, float phase_a, float phase_b)
{
    if (live.adc_a < 220 || live.adc_a > 3875 ||
        live.adc_b < 220 || live.adc_b > 3875) {
        coast(DRIVE_FAULT_ADC);
        return;
    }

    float peak = fmaxf(fabsf(phase_a), fmaxf(fabsf(phase_b), fabsf(phase_a + phase_b)));
    if (peak > settings.phase_peak_limit_a * 1.20f + 0.005f) {
        coast(DRIVE_FAULT_CURRENT);
        return;
    }

    float ramp_step = speed_ramp_rpm_s * control_dt;
    speed_setpoint += clamp(live.target_rpm - speed_setpoint, -ramp_step, ramp_step);
    float sign = live.target_rpm > 0.0f ? 1.0f : -1.0f;
    float speed_error = sign * (speed_setpoint - live.speed_rpm);
    speed_integral = clamp(speed_integral + settings.speed_ki_a_per_rpm_s *
                           speed_error * control_dt, 0.0f, settings.phase_peak_limit_a);
    // The speed controller requests motoring torque only. A command for
    // active deceleration or reversal coasts and requires a stopped re-arm.
    float iq_target = sign * clamp(settings.speed_kp_a_per_rpm * speed_error +
                                  speed_integral, 0.0f, settings.phase_peak_limit_a);
    float angle = hall_angle(now);
    float sin_angle = sinf(angle);
    float cos_angle = cosf(angle);
    float beta = (phase_a + 2.0f * phase_b) * inv_sqrt_three;
    float id = phase_a * cos_angle + beta * sin_angle;
    float iq = beta * cos_angle - phase_a * sin_angle;
    live.iq_a = iq;

    float error_d = -id;
    float error_q = iq_target - iq;
    float voltage_d = settings.current_kp_per_a * error_d + id_integral;
    float voltage_q = settings.current_kp_per_a * error_q + iq_integral;
    float alpha = voltage_d * cos_angle - voltage_q * sin_angle;
    beta = voltage_d * sin_angle + voltage_q * cos_angle;

    float line_b = -0.5f * alpha + sqrt_three_half * beta;
    float line_c = -0.5f * alpha - sqrt_three_half * beta;
    float span = fmaxf(alpha, fmaxf(line_b, line_c)) - fminf(alpha, fminf(line_b, line_c));
    float span_limit = max_duty - min_duty;
    if (span > span_limit) {
        float scale = span_limit / span;
        alpha *= scale;
        beta *= scale;
        // Back-calculate both current integrators when the bridge saturates.
        id_integral += voltage_d * (scale - 1.0f);
        iq_integral += voltage_q * (scale - 1.0f);
    } else {
        id_integral += settings.current_ki_per_a_s * error_d * control_dt;
        iq_integral += settings.current_ki_per_a_s * error_q * control_dt;
    }

    id_integral = clamp(id_integral, -span_limit, span_limit);
    iq_integral = clamp(iq_integral, -span_limit, span_limit);
    compute_duty(alpha, beta, pending_duty);
    duty_pending = true;
}

static void __not_in_flash_func(on_pwm_wrap)(void)
{
    pwm_clear_irq(sample_slice);
    uint32_t now = time_us_32();

    if (!live.calibrated) {
        live.hall_state = read_hall();
        return;
    }
    bool control_cycle = ++pwm_divider_count == control_divider;
    if (control_cycle) {
        pwm_divider_count = 0;
    }
    bool running = live.state == DRIVE_RUNNING;
    // Start the conversion at the wrap before Hall estimation (which can
    // include a division) or other unscheduled work changes the sample phase.
    float phase_a = 0.0f;
    float phase_b = 0.0f;
    bool sampled = running && control_cycle && sample_currents(&phase_a, &phase_b);
    bool hall_valid = update_hall(now);
    if (live.state == DRIVE_FAULTED) {
        return;
    }
    if (!hall_valid && (running || live.state == DRIVE_ARMED_IDLE)) {
        coast(DRIVE_FAULT_HALL);
        return;
    }
    if ((running || live.state == DRIVE_ARMED_IDLE) && !gpio_get(driver_fault)) {
        coast(DRIVE_FAULT_DRIVER);
        return;
    }
    if (!running) {
        return;
    }
    if (now - command_time_us > DRIVE_COMMAND_LEASE_MS * 1000u) {
        coast(DRIVE_FAULT_LEASE);
        return;
    }
    if (fabsf(live.speed_rpm) > fminf(DRIVE_MAX_RPM * 1.05f,
                                     settings.max_speed_rpm * 1.10f)) {
        coast(DRIVE_FAULT_OVERSPEED);
        return;
    }
    if ((direction && live.target_rpm * direction < 0.0f) ||
        (now - started_us > stall_us && now - hall_edge_us >= stopped_us)) {
        coast(DRIVE_FAULT_HALL);
        return;
    }
    if (!control_cycle) {
        // Pipeline the 64-bit SPI update into a separate carrier cycle,
        // leaving the current acquisition and math their own time budget.
        if (duty_pending) {
            duty_pending = false;
            if (!ts_transfer(false, reg_duty_a, pending_duty, NULL, 3)) {
                coast(DRIVE_FAULT_SPI);
                return;
            }
            memcpy(last_duty, pending_duty, sizeof(last_duty));
            control_time_us = time_us_32();
            ++live.cycle_count;
        } else if (pwm_divider_count == 2 && live.cycle_count % 32u == 0) {
            uint16_t duty[3];
            if (!ts_transfer(true, reg_duty_a, NULL, duty, 3) ||
                memcmp(duty, last_duty, sizeof(duty)) != 0) {
                coast(DRIVE_FAULT_SPI);
            }
        } else if (pwm_divider_count == 3 && live.cycle_count % 32u == 0) {
            uint16_t status;
            if (!read_reg(reg_device_status, &status)) {
                coast(DRIVE_FAULT_SPI);
            } else {
                live.driver_status = status;
                if (status) {
                    coast(DRIVE_FAULT_DRIVER);
                }
            }
        }
        return;
    }
    if (!sampled) {
        if (++missed_samples >= 3) {
            coast(DRIVE_FAULT_TIMING);
        }
        return;
    }

    missed_samples = 0;
    current_loop(now, phase_a, phase_b);
}

static void on_control_alarm(uint alarm)
{
    uint32_t now = time_us_32();
    if (live.state == DRIVE_RUNNING && now - control_time_us > maximum_control_gap_us) {
        // This ISR preempts the PWM IRQ. Force the separate hardware sleep
        // line low even when a control SPI/ADC transaction is wedged.
        gpio_put(driver_wake, false);
        live.fault = DRIVE_FAULT_TIMING;
        live.state = DRIVE_FAULTED;
        live.target_rpm = 0.0f;
        live.iq_a = 0.0f;
    }
    hardware_alarm_set_target(alarm, make_timeout_time_us(alarm_us));
}

bool drive_init(void)
{
    if (initialized) {
        return true;
    }

    gpio_init(driver_wake);
    gpio_put(driver_wake, false);
    // gpio_init enables the pad input buffer. Keep it off on this output,
    // including on RP2350 A2 where an enabled input can source current.
    gpio_set_input_enabled(driver_wake, false);
    gpio_set_dir(driver_wake, GPIO_OUT);
    gpio_init(driver_fault);
    for (uint pin = hall_a; pin < hall_a + 3; ++pin) {
        gpio_init(pin);
    }
    live.hall_state = read_hall();
    hall_edge_us = time_us_32();

    gpio_init(spi_cs);
    gpio_put(spi_cs, true);
    gpio_set_dir(spi_cs, GPIO_OUT);
    setup_spi();
    gpio_set_function(spi_rx, GPIO_FUNC_SPI);
    gpio_set_function(spi_sck, GPIO_FUNC_SPI);
    gpio_set_function(spi_tx, GPIO_FUNC_SPI);
    adc_init();
    adc_gpio_init(sense_a);
    adc_gpio_init(sense_b);

    uint32_t sys_hz = clock_get_hz(clk_sys);
    if (sys_hz % 1000000 || sys_hz % pwm_frequency_hz ||
        sys_hz / pwm_frequency_hz > 65536) {
        return false;
    }
    int claimed = hardware_alarm_claim_unused(false);
    if (claimed < 0) {
        return false;
    }
    alarm_index = (uint)claimed;
    hardware_alarm_set_callback(alarm_index, on_control_alarm);
    irq_set_priority(hardware_alarm_get_irq_num(alarm_index), 0x40);
    hardware_alarm_set_target(alarm_index, make_timeout_time_us(alarm_us));

    pwm_counts_per_us = sys_hz / 1000000;
    uint16_t wrap = (uint16_t)(sys_hz / pwm_frequency_hz - 1u);
    uint sync_slice = pwm_gpio_to_slice_num(driver_sync);
    sample_slice = sync_slice + 1;
    pwm_config config = pwm_get_default_config();
    pwm_config_set_wrap(&config, wrap);
    pwm_init(sync_slice, &config, false);
    pwm_init(sample_slice, &config, false);
    pwm_set_counter(sample_slice, (uint16_t)(sample_lead_us * pwm_counts_per_us));
    pwm_set_gpio_level(driver_sync, (wrap + 1u) / 2u);
    gpio_set_function(driver_sync, GPIO_FUNC_PWM);
    pwm_clear_irq(sample_slice);
    pwm_set_irq_enabled(sample_slice, true);
    irq_set_exclusive_handler(PWM_IRQ_WRAP_0, on_pwm_wrap);
    irq_set_priority(PWM_IRQ_WRAP_0, 0x80);
    irq_set_enabled(PWM_IRQ_WRAP_0, true);
    hw_set_bits(&pwm_hw->en, (1u << sync_slice) | (1u << sample_slice));
    initialized = true;
    return true;
}

void drive_service(void)
{
    if (!initialized) {
        return;
    }
    uint32_t interrupts = save_and_disable_interrupts();
    if (live.state == DRIVE_ARMED_IDLE && time_us_32() - armed_us > 5000000u) {
        coast(DRIVE_FAULT_NONE);
    }
    restore_interrupts(interrupts);
}

bool drive_set_calibration(const drive_calibration_t *calibration)
{
    if (!initialized || !calibration || live.state != DRIVE_DISARMED) {
        return false;
    }
    if (!isfinite(calibration->current_kp_per_a) || calibration->current_kp_per_a <= 0.0f ||
        calibration->current_kp_per_a > 20.0f ||
        !isfinite(calibration->current_ki_per_a_s) || calibration->current_ki_per_a_s < 0.0f ||
        calibration->current_ki_per_a_s > 10000.0f ||
        !isfinite(calibration->speed_kp_a_per_rpm) || calibration->speed_kp_a_per_rpm <= 0.0f ||
        calibration->speed_kp_a_per_rpm > 0.01f ||
        !isfinite(calibration->speed_ki_a_per_rpm_s) || calibration->speed_ki_a_per_rpm_s < 0.0f ||
        calibration->speed_ki_a_per_rpm_s > 0.1f ||
        !isfinite(calibration->phase_peak_limit_a) || calibration->phase_peak_limit_a < 0.005f ||
        calibration->phase_peak_limit_a > DRIVE_MAX_PHASE_PEAK_A ||
        !isfinite(calibration->max_speed_rpm) || calibration->max_speed_rpm < 1.0f ||
        calibration->max_speed_rpm > DRIVE_MAX_RPM) {
        return false;
    }

    int8_t indices[8];
    memset(indices, -1, sizeof(indices));
    float angle_total = 0.0f;
    for (int i = 0; i < 6; ++i) {
        unsigned hall = calibration->hall_order[i];
        unsigned change = hall ^ calibration->hall_order[(i + 1) % 6];
        float angle = calibration->hall_entry_rad[i];
        if (!hall || hall >= 7 || indices[hall] >= 0 ||
            (change != 1 && change != 2 && change != 4) ||
            !isfinite(angle) || angle < 0.0f || angle >= two_pi) {
            return false;
        }
        float width = wrap_angle(calibration->hall_entry_rad[(i + 1) % 6] - angle);
        if (width < 0.5f || width > 1.7f) {
            return false;
        }
        angle_total += width;
        indices[hall] = (int8_t)i;
    }
    if (fabsf(angle_total - two_pi) > 0.001f) {
        return false;
    }

    uint32_t interrupts = save_and_disable_interrupts();
    memcpy(hall_index, indices, sizeof(hall_index));
    settings = *calibration;
    live.hall_state = read_hall();
    live.calibrated = true;
    hall_edge_us = time_us_32();
    hall_interval_us = 0;
    direction = 0;
    live.speed_rpm = 0.0f;
    restore_interrupts(interrupts);
    return true;
}

static bool measure_adc_zero(float *a, float *b)
{
    uint32_t sum_a = 0, sum_b = 0;
    for (unsigned sample = 0; sample < 64; ++sample) {
        uint16_t raw_a, raw_b;
        if (!read_current_adc(0, &raw_a) || !read_current_adc(1, &raw_b)) {
            return false;
        }
        sum_a += raw_a;
        sum_b += raw_b;
    }
    *a = sum_a / 64.0f;
    *b = sum_b / 64.0f;
    return *a > 1800.0f && *a < 2300.0f && *b > 1800.0f && *b < 2300.0f;
}

bool drive_arm(bool enable)
{
    if (!initialized) {
        return !enable;
    }
    if (!enable) {
        uint32_t interrupts = save_and_disable_interrupts();
        coast(DRIVE_FAULT_NONE);
        restore_interrupts(interrupts);
        return true;
    }
    uint32_t interrupts = save_and_disable_interrupts();
    bool ready = live.calibrated && live.state == DRIVE_DISARMED &&
                 hall_index[live.hall_state] >= 0 && time_us_32() - hall_edge_us >= stopped_us;
    restore_interrupts(interrupts);
    if (!ready) {
        return false;
    }

    // Complete sleep before subsequent wake so a previously asserted nSLEEP
    // is treated as a shutdown rather than the short fault-clear pulse.
    sleep_us(250);
    if (!measure_adc_zero(&adc_zero_a, &adc_zero_b)) {
        coast(DRIVE_FAULT_ADC);
        return false;
    }
    if (spi_requires_reset) {
        spi_deinit(spi0);
        setup_spi();
    }
    gpio_put(driver_wake, true);
    sleep_us(3000);

    if (!configure_driver()) {
        coast(DRIVE_FAULT_SPI);
        return false;
    }
    uint16_t status;
    if (!read_reg(reg_device_status, &status)) {
        coast(DRIVE_FAULT_SPI);
        return false;
    }
    live.driver_status = status;
    if (status || !gpio_get(driver_fault)) {
        coast(DRIVE_FAULT_DRIVER);
        return false;
    }

    interrupts = save_and_disable_interrupts();
    uint32_t now = time_us_32();
    if (hall_index[live.hall_state] < 0 || now - hall_edge_us < stopped_us) {
        coast(DRIVE_FAULT_HALL);
        restore_interrupts(interrupts);
        return false;
    }
    armed_us = now;
    live.state = DRIVE_ARMED_IDLE;
    restore_interrupts(interrupts);
    return true;
}

bool drive_set_speed_rpm(float rpm)
{
    if (!initialized || !isfinite(rpm)) {
        return false;
    }

    uint32_t interrupts = save_and_disable_interrupts();
    drive_state_t state = live.state;
    if (rpm == 0.0f) {
        if (state == DRIVE_ARMED_IDLE || state == DRIVE_RUNNING) {
            coast(DRIVE_FAULT_NONE);
        }
        restore_interrupts(interrupts);
        return true;
    }
    if ((state != DRIVE_ARMED_IDLE && state != DRIVE_RUNNING) ||
        fabsf(rpm) > settings.max_speed_rpm) {
        restore_interrupts(interrupts);
        return false;
    }
    uint32_t now = time_us_32();
    bool reverse = (live.target_rpm > 0.0f) != (rpm > 0.0f);
    bool decelerate = fabsf(rpm) < fabsf(live.target_rpm) &&
                      fabsf(rpm) < fabsf(live.speed_rpm);
    if ((state == DRIVE_RUNNING && (reverse || decelerate)) ||
        (state == DRIVE_ARMED_IDLE && now - hall_edge_us < stopped_us)) {
        coast(DRIVE_FAULT_NONE);
        restore_interrupts(interrupts);
        return false;
    }
    if (state == DRIVE_RUNNING) {
        live.target_rpm = rpm;
        command_time_us = now;
        restore_interrupts(interrupts);
        return true;
    }
    restore_interrupts(interrupts);

    // The output states are still high impedance at this point. Preload
    // identical duty values to start with zero differential motor voltage.
    compute_duty(0.0f, 0.0f, last_duty);
    uint16_t preload[3], phase_state;
    if (!ts_transfer(false, reg_duty_a, last_duty, NULL, 3) ||
        !ts_transfer(true, reg_duty_a, NULL, preload, 3) ||
        memcmp(preload, last_duty, sizeof(preload)) != 0 ||
        !gpio_get(driver_fault) ||
        !write_reg(reg_phase_state, driver_complementary_pwm) ||
        !read_reg(reg_phase_state, &phase_state) || phase_state != driver_complementary_pwm) {
        coast(DRIVE_FAULT_SPI);
        return false;
    }
    interrupts = save_and_disable_interrupts();
    if (live.state != DRIVE_ARMED_IDLE || !gpio_get(driver_fault)) {
        gpio_put(driver_wake, false);
        restore_interrupts(interrupts);
        return false;
    }
    now = time_us_32();
    command_time_us = now;
    control_time_us = now;
    started_us = now;
    // Do not report a sample from a preceding run as a fresh first sample.
    live.cycle_count = 0;
    live.target_rpm = rpm;
    live.state = DRIVE_RUNNING;
    missed_samples = 0;
    restore_interrupts(interrupts);
    return true;
}

const drive_status_t *drive_status(void)
{
    static drive_status_t snapshot;
    uint32_t interrupts = save_and_disable_interrupts();
    snapshot = live;
    restore_interrupts(interrupts);
    return &snapshot;
}
