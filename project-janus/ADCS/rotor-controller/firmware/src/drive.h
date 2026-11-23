#ifndef BLEPS_DRIVE_H
#define BLEPS_DRIVE_H

#include <stdbool.h>
#include <stdint.h>

#define DRIVE_MAX_RPM 3000.0f
#define DRIVE_MAX_PHASE_PEAK_A 0.100f
#define DRIVE_COMMAND_LEASE_MS 250

typedef enum {
    DRIVE_DISARMED = 0,
    DRIVE_ARMED_IDLE,
    DRIVE_RUNNING,
    DRIVE_FAULTED
} drive_state_t;

typedef enum {
    DRIVE_FAULT_NONE = 0,
    DRIVE_FAULT_DRIVER,
    DRIVE_FAULT_SPI,
    DRIVE_FAULT_HALL,
    DRIVE_FAULT_ADC,
    DRIVE_FAULT_CURRENT,
    DRIVE_FAULT_OVERSPEED,
    DRIVE_FAULT_TIMING,
    DRIVE_FAULT_LEASE
} drive_fault_t;

typedef struct {
    // Forward order in electrical coordinates A/B/C. Hall A occupies bit 0.
    // Each angle is the measured boundary on ENTRY into the corresponding state
    // in the forward direction. Radians in [0, 2*pi), referred to rotor flux.
    uint8_t hall_order[6];
    float hall_entry_rad[6];

    // Bench-validated gains. Current-loop outputs are fractions of the DC bus.
    float current_kp_per_a;
    float current_ki_per_a_s;
    float speed_kp_a_per_rpm;
    float speed_ki_a_per_rpm_s;
    float phase_peak_limit_a;
    float max_speed_rpm;
} drive_calibration_t;

typedef struct {
    drive_state_t state;
    drive_fault_t fault;
    uint16_t driver_status;
    uint8_t hall_state;
    bool calibrated;
    float speed_rpm;
    float target_rpm;
    float iq_a;
    uint32_t cycle_count;
    uint32_t sample_time_us;
    uint16_t adc_a;
    uint16_t adc_b;
} drive_status_t;

// Foreground only, on one core. No API calls from interrupt handlers.
// drive_status returns a snapshot that lasts until the next drive_status call.
bool drive_init(void);
void drive_service(void);
bool drive_set_calibration(const drive_calibration_t *calibration);
bool drive_arm(bool enable);
bool drive_set_speed_rpm(float rpm);
const drive_status_t *drive_status(void);

#endif
