#pragma once
#include "FreeRTOS.h"
typedef void* QueueHandle_t;
QueueHandle_t xQueueCreate(unsigned depth, unsigned size);
BaseType_t xQueueSend(QueueHandle_t q, const void* item, TickType_t timeout);
BaseType_t xQueueReceive(QueueHandle_t q, void* item, TickType_t timeout);
void vQueueDelete(QueueHandle_t q);
