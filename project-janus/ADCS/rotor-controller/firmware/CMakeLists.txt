cmake_minimum_required(VERSION 3.17)

set(PICO_BOARD bleps_wheel)
set(PICO_PLATFORM rp2350-arm-s)
set(PICO_BOARD_HEADER_DIRS "${CMAKE_CURRENT_LIST_DIR}/boards")
if(NOT PICO_SDK_PATH)
    set(PICO_SDK_PATH "$ENV{PICO_SDK_PATH}")
endif()
if(NOT EXISTS "${PICO_SDK_PATH}/external/pico_sdk_import.cmake")
    message(FATAL_ERROR "Set PICO_SDK_PATH to a Pico SDK 2.2.0 checkout.")
endif()
include("${PICO_SDK_PATH}/external/pico_sdk_import.cmake")
project(bleps_wheel C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()
if(PICO_SDK_VERSION_STRING VERSION_LESS "2.2.0")
    message(FATAL_ERROR "Pico SDK 2.2.0 or later is required.")
endif()

option(ROTOR_PROGRAMMER_ONLY "Build only the SRAM MRAM programmer" OFF)
option(ROTOR_USE_CAN2040 "Build the Classical CAN vehicle interface" ON)
set(ROTOR_CAN_BITRATE 500000 CACHE STRING "Spacecraft CAN nominal bitrate in bits/s")
set(ROTOR_CAN_NODE_ID 0 CACHE STRING "Wheel node ID")

add_executable(mram_programmer programmer/mram_programmer.c)
pico_set_binary_type(mram_programmer no_flash)
target_link_libraries(mram_programmer PRIVATE pico_stdlib pico_bootrom)
pico_enable_stdio_uart(mram_programmer 0)
pico_enable_stdio_usb(mram_programmer 0)
pico_add_map_output(mram_programmer)

if(ROTOR_PROGRAMMER_ONLY)
    return()
endif()

add_executable(bleps_wheel src/main.c src/drive.c)
pico_set_binary_type(bleps_wheel copy_to_ram)
target_link_libraries(bleps_wheel PRIVATE pico_stdlib hardware_adc hardware_clocks
    hardware_dma hardware_gpio hardware_i2c hardware_irq hardware_pio hardware_pwm
    hardware_spi hardware_sync hardware_timer hardware_watchdog m)
target_compile_definitions(bleps_wheel PRIVATE
    PICO_EMBED_XIP_SETUP=1
    ROTOR_USE_CAN2040=$<BOOL:${ROTOR_USE_CAN2040}>
    ROTOR_CAN_BITRATE=${ROTOR_CAN_BITRATE}
    ROTOR_CAN_NODE_ID=${ROTOR_CAN_NODE_ID})
pico_define_boot_stage2(bleps_mram_xip "${CMAKE_CURRENT_LIST_DIR}/boot/mram_xip.S")
pico_set_boot_stage2(bleps_wheel bleps_mram_xip)
pico_enable_stdio_uart(bleps_wheel 0)
pico_enable_stdio_usb(bleps_wheel 0)
pico_add_bin_output(bleps_wheel)
pico_add_map_output(bleps_wheel)

if(ROTOR_USE_CAN2040)
    include(FetchContent)
    FetchContent_Declare(can2040
        GIT_REPOSITORY https://github.com/KevinOConnor/can2040.git
        GIT_TAG 90515f53ce89442f1bcc3033aae222e9eb77818c)
    FetchContent_MakeAvailable(can2040)
    add_library(bleps_can2040 STATIC "${can2040_SOURCE_DIR}/src/can2040.c")
    target_include_directories(bleps_can2040 PUBLIC "${can2040_SOURCE_DIR}/src")
    target_compile_options(bleps_can2040 PRIVATE -O2)
    target_link_libraries(bleps_can2040 PRIVATE cmsis_core_headers hardware_structs)
    target_link_libraries(bleps_wheel PRIVATE bleps_can2040 pico_multicore)
endif()
