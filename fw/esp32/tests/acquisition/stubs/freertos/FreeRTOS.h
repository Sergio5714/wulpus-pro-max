#pragma once
#include <stdint.h>
#include <stddef.h>

/* MSVC parses production headers during host tests but has no GCC attributes. */
#ifdef _MSC_VER
#define __attribute__(x)
#endif

typedef uint32_t TickType_t;
typedef int BaseType_t;
typedef int portMUX_TYPE;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
#define portENTER_CRITICAL_ISR(x) ((void)(x))
#define portEXIT_CRITICAL_ISR(x) ((void)(x))
#define portYIELD_FROM_ISR() ((void)0)
#define IRAM_ATTR
#define pdTRUE 1
#define pdFALSE 0
#define pdPASS 1
#define portMAX_DELAY UINT32_MAX
#define pdMS_TO_TICKS(x) (x)
#define CONFIG_WP_DATA_RX_LENGTH 804
#define CONFIG_WP_ACQUISITION_STACK_SIZE 4096
#define CONFIG_WP_ACQUISITION_PRIORITY 8
#define CONFIG_WP_FRAME_SLOT_COUNT 4
