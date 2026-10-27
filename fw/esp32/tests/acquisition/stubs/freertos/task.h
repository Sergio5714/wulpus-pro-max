#pragma once
#include "FreeRTOS.h"
typedef void* TaskHandle_t;
TickType_t xTaskGetTickCount(void);
void vTaskDelay(TickType_t ticks);
uint32_t ulTaskNotifyTake(BaseType_t clear, TickType_t timeout);
void vTaskNotifyGiveFromISR(TaskHandle_t task, BaseType_t* wake);
void xTaskNotifyGive(TaskHandle_t task);
BaseType_t xTaskCreate(void (*fn)(void*), const char* name, unsigned stack,
                       void* arg, unsigned priority, TaskHandle_t* task);
