#pragma once
#include "esp_err.h"
#define ESP_RETURN_ON_ERROR(expr, tag, msg) do { esp_err_t err = (expr); if (err != ESP_OK) return err; } while (0)
