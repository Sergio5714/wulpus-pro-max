# MSP430 firmware update protocol

This protocol extends the [ESP32-to-PC protocol](esp32_pc_protocol.md) with commands
for staging an MSP430 image on the ESP32, programming the MSP430 after reboot,
and retrieving the saved result. It is intended for firmware and host-client
developers; users should follow the
[firmware update guide](../../../docs/firmware_update_guide.md).

## Contents

- [Upload messages](#upload-messages)
- [Upload sequence](#upload-sequence)
- [Update status](#update-status)
- [Update diagnostics](#update-diagnostics)
- [Complete command sequence](#complete-command-sequence)

All fields are packed and little-endian. Requests use the standard nine-byte
ESP32-to-PC packet header, and the maximum request payload is 804 bytes.

## Upload messages

| Command | Direction | Message | Field order (byte widths) |
|---|---|---|---|
| `MSP_UPDATE_BEGIN` (`0x6C`) | PC → ESP | Upload request | version (1, value 1), flags (1, send 0), reserved (2, zero), image_size (4), image_crc32 (4) |
| `MSP_UPDATE_BEGIN` (`0x6C`) | ESP → PC | Acknowledgement | Empty payload |
| `MSP_UPDATE_DATA` (`0x6D`) | PC → ESP | Chunk upload | offset (4), sequence (2), data_length (2), data_crc32 (4), data (1–792) |
| `MSP_UPDATE_DATA` (`0x6D`) | ESP → PC | Chunk acknowledgement | next_offset (4), accepted_sequence (2), reserved (2, zero) |

## Upload sequence

1. **Start the upload with `MSP_UPDATE_BEGIN`.**
   - Stop acquisition before sending this command and keep it stopped throughout
     the upload.
   - The ESP32 must have an available staging partition.
   - The CRC covers the complete staged container, including its header and
     section table.
2. **Transfer the image with repeated `MSP_UPDATE_DATA` commands.**
   - Each command carries one chunk and a CRC covering that chunk's data.
   - The offset must equal the number of bytes already accepted, which enforces
     chunk order.
   - The acknowledgement returns the accepted sequence value and the offset
     required for the next chunk.
3. **Finish the upload with `MSP_UPDATE_COMMIT`.**
   - The ESP32 accepts this command only after every image byte has been received.
   - This command blocks new acquisition and schedules an ESP32 reboot.
   - After reboot, the ESP32 validates the complete image and programs the
     MSP430.

See the [updater implementation](msp430_update_guide.md) for the image layout
and recovery limits.

## Update status

The 28-byte `MSP_UPDATE_STATUS` payload reports upload and programming progress:

| Offset | Size (bytes) | Field |
|---:|---:|---|
| 0 | 1 | version (1) |
| 1 | 1 | state |
| 2 | 2 | flags; bit 0 = boot update pending |
| 4 | 4 | received_bytes |
| 8 | 4 | total_bytes (container size) |
| 12 | 4 | processed_bytes (section data in current write/verify pass) |
| 16 | 4 | current_address |
| 20 | 4 | target_device_id (expected descriptor value `0x8317`) |
| 24 | 4 | error (signed ESP error code) |

The `state` field reports the current or final stage of the MSP430 firmware
update. Its numeric values are defined below:

| Value | State | Meaning |
|---:|---|---|
| 0 | `IDLE` | No update is active. |
| 1 | `RECEIVING` | The ESP32 is receiving image chunks. |
| 2 | `READY` | The complete image has been received and can be committed. |
| 3 | `VALIDATING` | The ESP32 is validating the staged image. |
| 4 | `PROGRAMMING` | The ESP32 is writing firmware to the MSP430. |
| 5 | `VERIFYING` | The ESP32 is verifying the programmed MSP430 memory. |
| 6 | `RESETTING` | Defined by the protocol but currently unused. |
| 7 | `WAITING_FOR_BOOT` | Defined by the protocol but currently unused. |
| 8 | `COMPLETE` | Programming and verification completed successfully. |
| 9 | `FAILED` | The update failed; inspect `error` and diagnostics. |
| 10 | `ABORTED` | The staged update was aborted. |

`processed_bytes` restarts from zero for verification and excludes container
metadata, so it is not directly comparable to `total_bytes`.

## Update diagnostics

The 16-byte `MSP_UPDATE_DIAGNOSTICS` response contains identifiers and control
values captured during the most recent MSP430 programming attempt:

| Offset | Size (bytes) | Field | Meaning |
|---:|---:|---|---|
| 0 | 1 | `version` | Diagnostics format version; currently `1`. |
| 1 | 1 | `stage` | Furthest diagnostic stage reached. |
| 2 | 2 | `jtag_id` | JTAG interface identifier. |
| 4 | 2 | `core_id` | MSP430 core identifier. |
| 6 | 2 | `control_signal` | Captured JTAG control-signal value. |
| 8 | 4 | `descriptor_pointer` | Address of the MSP430 device descriptor. |
| 12 | 2 | `quick_device_id` | Device identifier read through the quick-memory path. |
| 14 | 2 | `direct_device_id` | Device identifier read directly from memory. |

The `stage` field indicates how far identification progressed:

| Value | Stage | Current implementation |
|---:|---|---|
| 0 | Not started | Used |
| 1 | JTAG entry | Used |
| 2 | Core ID | Defined but not currently reported |
| 3 | Descriptor pointer | Defined but not currently reported |
| 4 | Synchronization | Defined but not currently reported |
| 5 | Device-memory read | Used |
| 6 | Device validated | Used |

`MSP_UPDATE_GET_DIAGNOSTICS` reads the stored result; it does not start a JTAG
operation.

## Complete command sequence

```text
MSP_UPDATE_BEGIN -> empty acknowledgement
MSP_UPDATE_DATA  -> next offset / accepted sequence (repeat per chunk)
MSP_UPDATE_COMMIT -> empty acknowledgement -> ESP32 reboot
                   validation / JTAG write / verification / normal startup
reconnect
MSP_UPDATE_GET_STATUS -> empty acknowledgement -> MSP_UPDATE_STATUS
MSP_UPDATE_GET_DIAGNOSTICS -> MSP_UPDATE_DIAGNOSTICS
```
