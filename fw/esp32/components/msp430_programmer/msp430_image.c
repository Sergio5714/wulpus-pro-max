/* Copyright (C) 2026 Sergei Vostrikov, SPDX-License-Identifier: Apache-2.0 */

/**
 * @file msp430_image.c
 * @brief Staged MSP430 image parsing, range validation, and CRC checking.
 */

#include "msp430_image.h"
#include <string.h>
#include "esp_check.h"
#define MSP430FR5043_TARGET_ID 0x00005043U

uint32_t msp430_crc32(uint32_t crc, const void* data, size_t length)
{
    const uint8_t* p = data;
    crc = ~crc;
    while (length--) {
        crc ^= *p++;
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320U & (uint32_t)-(int32_t)(crc & 1));
    }
    return ~crc;
}

/**
 * @brief Check that an aligned, nonempty range lies in application FRAM outside signature words.
 */
static bool allowed(uint32_t address, uint32_t length)
{
    if (!length || (address & 1) || (length & 1) || address + length < address)
        return false;
    uint32_t end = address + length;
    /* Application FRAM is continuous across the 0xffff/0x10000 boundary.
     * Keep the JTAG/BSL signature words at 0xff80..0xff8f protected while
     * allowing the interrupt vectors above them. */
    bool overlaps_signatures = address < 0xff90 && end > 0xff80;
    return address >= 0x6000 && end <= 0x15ff8 && !overlaps_signatures;
}

esp_err_t msp430_image_open(const esp_partition_t* partition, uint32_t staged_size,
                            msp430_image_t* image)
{
    if (!partition || !image || staged_size < sizeof(image->header))
        return ESP_ERR_INVALID_ARG;
    memset(image, 0, sizeof(*image));
    image->partition = partition;
    ESP_RETURN_ON_ERROR(esp_partition_read(partition, 0, &image->header, sizeof(image->header)),
                        "msp_image", "header read");
    const msp430_image_header_t* h = &image->header;
    if (h->magic != MSP430_IMAGE_MAGIC || h->version != MSP430_IMAGE_VERSION ||
        h->header_size != sizeof(*h) || h->total_size != staged_size ||
        h->target_id != MSP430FR5043_TARGET_ID || !h->section_count ||
        h->section_count > MSP430_IMAGE_MAX_SECTIONS)
        return ESP_ERR_INVALID_ARG;
    uint32_t table_size = h->section_count * sizeof(msp430_image_section_t);
    if (sizeof(*h) + table_size > staged_size)
        return ESP_ERR_INVALID_SIZE;
    ESP_RETURN_ON_ERROR(esp_partition_read(partition, sizeof(*h), image->sections, table_size),
                        "msp_image", "table read");
    uint32_t offset = sizeof(*h) + table_size;
    for (unsigned i = 0; i < h->section_count; ++i) {
        const msp430_image_section_t* s = &image->sections[i];
        if (!allowed(s->address, s->length) || offset + s->length < offset ||
            offset + s->length > staged_size)
            return ESP_ERR_INVALID_ARG;
        for (unsigned j = 0; j < i; ++j) {
            uint32_t a0 = image->sections[j].address;
            uint32_t a1 = a0 + image->sections[j].length;
            if (s->address < a1 && a0 < s->address + s->length)
                return ESP_ERR_INVALID_ARG;
        }
        image->data_offsets[i] = offset;
        offset += s->length;
    }
    if (offset != staged_size)
        return ESP_ERR_INVALID_SIZE;
    uint8_t buffer[256];
    uint32_t payload_crc = 0;
    for (unsigned i = 0; i < h->section_count; ++i) {
        uint32_t section_crc = 0;
        for (uint32_t position = 0; position < image->sections[i].length;) {
            size_t count = image->sections[i].length - position;
            if (count > sizeof(buffer))
                count = sizeof(buffer);
            ESP_RETURN_ON_ERROR(msp430_image_read(image, i, position, buffer, count), "msp_image",
                                "section read");
            section_crc = msp430_crc32(section_crc, buffer, count);
            payload_crc = msp430_crc32(payload_crc, buffer, count);
            position += count;
        }
        if (section_crc != image->sections[i].data_crc32)
            return ESP_ERR_INVALID_CRC;
    }
    return payload_crc == h->image_crc32 ? ESP_OK : ESP_ERR_INVALID_CRC;
}

esp_err_t msp430_image_read(const msp430_image_t* image, unsigned section, uint32_t offset,
                            void* data, size_t length)
{
    if (!image || section >= image->header.section_count ||
        offset + length > image->sections[section].length)
        return ESP_ERR_INVALID_ARG;
    return esp_partition_read(image->partition, image->data_offsets[section] + offset, data,
                              length);
}
