/* Copyright (C) 2026 Sergei Vostrikov, SPDX-License-Identifier: Apache-2.0 */

/**
 * @file msp430_image.h
 * @brief Staged MSP430 image parsing, range validation, and CRC checking.
 */

#pragma once
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "esp_partition.h"

#define MSP430_IMAGE_MAGIC 0x3150534dU /* MSP1 */
#define MSP430_IMAGE_VERSION 1
#define MSP430_IMAGE_MAX_SECTIONS 64

typedef struct __attribute__((packed)) {
    uint32_t magic;
    uint16_t version;
    uint16_t header_size;
    uint32_t target_id;
    uint32_t total_size;
    uint32_t image_crc32;
    uint16_t section_count;
    uint16_t flags;
} msp430_image_header_t;

typedef struct __attribute__((packed)) {
    uint32_t address;
    uint32_t length;
    uint32_t data_crc32;
} msp430_image_section_t;

typedef struct {
    const esp_partition_t* partition;
    msp430_image_header_t header;
    msp430_image_section_t sections[MSP430_IMAGE_MAX_SECTIONS];
    uint32_t data_offsets[MSP430_IMAGE_MAX_SECTIONS];
} msp430_image_t;

/**
 * @brief Update a reflected CRC-32 using polynomial 0xedb88320.
 *
 * @param crc Previous CRC result, or zero to start a new calculation.
 * @param data Input bytes.
 * @param length Input size in bytes.
 * @return Updated CRC value.
 */
uint32_t msp430_crc32(uint32_t crc, const void* data, size_t length);
/**
 * @brief Read and validate a staged image's metadata, section ranges, and payload CRCs.
 *
 * @param partition Partition containing the staged image.
 * @param staged_size Total staged image size in bytes.
 * @param image Receives the validated image description.
 * @return ESP_OK, an argument/size/CRC validation error, or a partition read error.
 */
esp_err_t msp430_image_open(const esp_partition_t* partition, uint32_t staged_size,
                            msp430_image_t* image);
/**
 * @brief Read bytes from a selected section of an opened image.
 *
 * @param image Image description produced by msp430_image_open().
 * @param section Zero-based section index.
 * @param offset Byte offset within the section.
 * @param data Destination buffer.
 * @param length Bytes to read.
 * @return ESP_OK, ESP_ERR_INVALID_ARG for an invalid range, or a partition read error.
 */
esp_err_t msp430_image_read(const msp430_image_t* image, unsigned section, uint32_t offset,
                            void* data, size_t length);
