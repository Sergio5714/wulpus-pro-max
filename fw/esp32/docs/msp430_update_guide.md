# MSP430 updater implementation

The ESP32 stages an MSP430FR5043 firmware image received over USB CDC or TCP,
then programs the MSP430 through four-wire JTAG during the next boot. Users
should follow the central
[firmware update guide](../../../docs/firmware_update_guide.md); this document
describes the ESP32 implementation.

## Contents

- [JTAG implementation](#jtag-implementation)
- [Staging and boot lifecycle](#staging-and-boot-lifecycle)
- [Failure and recovery behavior](#failure-and-recovery-behavior)
- [Image container](#image-container)

## JTAG implementation

The JTAG programmer is based on TI's
[MSP430 Programming With the JTAG Interface (SLAU320AJ)](https://www.ti.com/lit/pdf/slau320)
and its MSP430 FRAM Replicator reference implementation:
[JTAGfunc430FR.c](../components/msp430_programmer/ti/JTAGfunc430FR.c) and
[JTAGfunc430FR.h](../components/msp430_programmer/ti/JTAGfunc430FR.h).
[msp430_jtag.c](../components/msp430_programmer/msp430_jtag.c) and the adapted
[LowLevelFunc430Xv2.h](../components/msp430_programmer/ti/LowLevelFunc430Xv2.h)
provide the ESP32 GPIO interface.

The WiFi host PCB routes the ESP32-C6 JTAG GPIOs to the MSP430. A standalone
XIAO connected through the Acquisition PCB's Dupont headers cannot use the
programmer because those JTAG signals are not exposed there. An attached
MSP-FET must not drive the signals concurrently.

## Staging and boot lifecycle

The ESP32 receives the versioned section image through the update protocol and
stores it in the 256 KiB `msp_image` data partition defined by
`partitions.csv`. Each transfer is CRC checked before being accepted. Commit
persists the pending-update state and restarts the ESP32.

Early in the following boot, the programmer validates the container, enters
MSP430 JTAG, erases and writes the declared FRAM sections, reads them back for
verification, resets the target, and persists the final state and diagnostics.
Normal USB and Wi-Fi services start after this boot-time operation.

See the [MSP430 firmware update protocol](msp430_update_protocol.md) for command,
status, and diagnostic layouts.

## Failure and recovery behavior

The ESP32 temporarily disconnects from USB while it programs and verifies the
MSP430 during startup. `COMPLETE` confirms programming and readback
verification; it does not prove subsequent application behavior.

An interrupted update is not resumed automatically, and the MSP430 has no
dual-image rollback. A new complete image must be uploaded after the ESP32
returns. Identification or JTAG failures may require recovery with an external
programmer. Persisted status and diagnostics record the last stage and detected
JTAG and device identifiers.

## Image container

All integers are little-endian. TI-TXT or Intel HEX input is converted to an
`MSP1` container before upload; `.out` ELF and raw flat `.bin` files are not
accepted directly.

| Header field | Bytes | Value |
|---|---:|---|
| magic | 4 | `0x3150534D` (`MSP1`) |
| version, header_size | 2 each | `1`, `24` |
| target_id | 4 | `0x00005043` |
| total_size | 4 | Header + section table + data |
| image_crc32 | 4 | CRC of concatenated section data |
| section_count, flags | 2 each | 1-64 sections; flags zero |

The header is followed by one 12-byte `(address, length, data_crc32)` descriptor
per section, then the section data in table order. CRCs use the reflected
CRC-32 polynomial `0xEDB88320`.

Sections must be nonoverlapping and word-aligned, lie in
`[0x6000, 0x15FF8)`, and exclude `[0xFF80, 0xFF90)` (JTAG/BSL signatures).
Interrupt vectors outside that protected range are allowed. The text importer
removes erased `0xFF` signature placeholders, rejects other signature contents,
rejects odd start addresses, and pads odd data lengths with `0xFF`.
