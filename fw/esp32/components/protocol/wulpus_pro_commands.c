/*
Copyright (C) 2026 Sergei Vostrikov

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

/**
 * @file wulpus_pro_commands.c
 * @brief Wire command identifiers and printable command names.
 */

#include "wulpus_pro_commands.h"
const char* wulpus_pro_command_name(wulpus_pro_command_t command)
{
    switch (command) {
    case WULPUS_PRO_SET_ACQ_CONFIG:
        return "SET_ACQ_CONFIG";
    case WULPUS_PRO_GET_DATA:
        return "GET_DATA";
    case WULPUS_PRO_PING:
        return "PING";
    case WULPUS_PRO_PONG:
        return "PONG";
    case WULPUS_PRO_RESET:
        return "RESET";
    case WULPUS_PRO_RESET_MSP:
        return "RESET_MSP";
    case WULPUS_PRO_CLOSE:
        return "CLOSE";
    case WULPUS_PRO_START_RX:
        return "START_RX";
    case WULPUS_PRO_STOP_RX:
        return "STOP_RX";
    case WULPUS_PRO_BUSY:
        return "BUSY";
    case WULPUS_PRO_GET_STATUS:
        return "GET_STATUS";
    case WULPUS_PRO_STATUS:
        return "STATUS";
    case WULPUS_PRO_CLEAR_STATUS:
        return "CLEAR_STATUS";
    case WULPUS_PRO_GET_DEVICE_CONFIG:
        return "GET_DEVICE_CONFIG";
    case WULPUS_PRO_DEVICE_CONFIG:
        return "DEVICE_CONFIG";
    case WULPUS_PRO_SET_DEVICE_CONFIG:
        return "SET_DEVICE_CONFIG";
    case WULPUS_PRO_GET_WIFI_STATUS:
        return "GET_WIFI_STATUS";
    case WULPUS_PRO_WIFI_STATUS:
        return "WIFI_STATUS";
    case WULPUS_PRO_SET_WIFI_CREDENTIALS:
        return "SET_WIFI_CREDENTIALS";
    case WULPUS_PRO_CLEAR_WIFI_CREDENTIALS:
        return "CLEAR_WIFI_CREDENTIALS";
    case WULPUS_PRO_ERROR:
        return "ERROR";
    case WULPUS_PRO_MSP_UPDATE_BEGIN:
        return "MSP_UPDATE_BEGIN";
    case WULPUS_PRO_MSP_UPDATE_DATA:
        return "MSP_UPDATE_DATA";
    case WULPUS_PRO_MSP_UPDATE_COMMIT:
        return "MSP_UPDATE_COMMIT";
    case WULPUS_PRO_MSP_UPDATE_ABORT:
        return "MSP_UPDATE_ABORT";
    case WULPUS_PRO_MSP_UPDATE_GET_STATUS:
        return "MSP_UPDATE_GET_STATUS";
    case WULPUS_PRO_MSP_UPDATE_STATUS:
        return "MSP_UPDATE_STATUS";
    case WULPUS_PRO_MSP_UPDATE_GET_DIAGNOSTICS:
        return "MSP_UPDATE_GET_DIAGNOSTICS";
    case WULPUS_PRO_MSP_UPDATE_DIAGNOSTICS:
        return "MSP_UPDATE_DIAGNOSTICS";
    case WULPUS_PRO_GET_FIRMWARE_INFO:
        return "GET_FIRMWARE_INFO";
    case WULPUS_PRO_FIRMWARE_INFO:
        return "FIRMWARE_INFO";
    default:
        return "UNKNOWN";
    }
}
