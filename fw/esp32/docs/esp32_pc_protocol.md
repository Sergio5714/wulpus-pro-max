# ESP32-to-PC protocol

The ESP32 exposes the same ordered byte-stream protocol over Wi-Fi/TCP and the
ESP32-C6 native USB Serial/JTAG CDC interface. Packets, command IDs, payloads,
and acknowledgements are transport-independent.

## Contents

- [Transports](#transports)
- [Packet format](#packet-format)
- [Commands](#commands)
- [Persistent device configuration](#persistent-device-configuration)
- [Acknowledgement model](#acknowledgement-model)
- [Acquisition frame](#acquisition-frame)
- [Typical acquisition session](#typical-acquisition-session)
- [Runtime status](#runtime-status)
- [Clearing status](#clearing-status)
- [Firmware information](#firmware-information)
- [MSP430 firmware update commands](#msp430-firmware-update-commands)

## Transports

| Transport | Endpoint | Notes |
|---|---|---|
| Wi-Fi TCP | TCP port 2121 by default | Discovered through the `_wulpus_pro._tcp` mDNS service after Wi-Fi obtains an IP address. |
| USB CDC | ESP32-C6 USB Serial/JTAG COM port | Baud-rate settings do not control USB line speed. The port must not be open in another GUI, terminal, or monitor. |

Only one transport owns a protocol session at a time. See
[Firmware architecture](firmware_architecture.md#usb-and-wi-fi-session-switching) for
arbitration and switching.

## Packet format

Every message is one packed nine-byte header followed immediately by
`data_length` payload bytes:

| Offset | Size (bytes) | Field | Encoding |
|---:|---:|---|---|
| 0 | 6 | `magic` | ASCII `wulpus` (`77 75 6c 70 75 73`). |
| 6 | 1 | `command` | Command ID from the table below. |
| 7 | 2 | `data_length` | Unsigned little-endian payload length, 0–65535. |
| 9 | variable | `payload` | Command-specific bytes. |

Construct a packet by concatenating the packed header and the payload. Multi-byte
fields use little-endian byte order.

TCP and USB may split or combine packets arbitrarily. A receiver must accumulate
bytes until the complete header and declared payload are available; one socket
read or serial read is not guaranteed to equal one protocol packet.

Before a session is claimed, each listener scans the stream for the `wulpus`
magic. This also recovers from boot text or stale serial bytes. During an active
session, a malformed header or oversized command payload is a protocol error
and ends the session rather than silently resynchronizing in the middle of a
packet.

## Commands

| ID | Name | Direction | Request payload | Responses and effect |
|---:|---|---|---|---|
| `0x57` | `SET_ACQ_CONFIG` | PC -> ESP | MSP430 acquisition configuration package, at most 804 bytes | Empty acknowledgement after DATA_READY and successful SPI transfer; `ERROR` on timeout/transfer failure, `BUSY` while an update is pending. Does not confirm MSP430 application of the configuration. |
| `0x58` | `GET_DATA` | ESP -> PC | 804-byte RF payload | Asynchronous acquisition frame emitted while RX is enabled. It is not a host polling request. |
| `0x59` | `PING` | PC -> ESP | Empty | Empty `PING` acknowledgement, followed by `PONG` containing ASCII `pong`. |
| `0x5A` | `PONG` | ESP -> PC | ASCII `pong` | Second response to `PING`. |
| `0x5B` | `RESET` | PC -> ESP | Empty | Stops acquisition, shuts down/resets MSP430, queues an empty acknowledgement, then restarts ESP32. `BUSY` while an update is pending. Delivery before restart is not guaranteed. |
| `0x63` | `RESET_MSP` | PC -> ESP | Empty | If acquisition and update are inactive, pulses MSP430 reset and acknowledges after its boot delay; otherwise `BUSY`. Keeps the session open. |
| `0x5C` | `CLOSE` | PC -> ESP | Empty | Acquisition is stopped, then an empty `CLOSE` acknowledgement is sent. The session proceeds through common cleanup and releases ownership. |
| `0x5D` | `START_RX` | PC -> ESP | Empty | Empty acknowledgement after enabling acquisition forwarding; `BUSY` while an update is pending. |
| `0x5E` | `STOP_RX` | PC -> ESP | Empty | Acquisition and queued session frames are stopped/discarded before the empty `STOP_RX` acknowledgement is sent. The protocol session remains open. |
| `0x5F` | `BUSY` | ESP -> PC | Empty | Another transport owns the session, `RESET_MSP` is requested during acquisition, or acquisition configuration/start/reset conflicts with a pending update. |
| `0x60` | `GET_STATUS` | PC -> ESP | Empty | Empty `GET_STATUS` acknowledgement followed by one `STATUS` packet. |
| `0x61` | `STATUS` | ESP -> PC | 40-byte versioned status payload | Runtime errors, counters, and frame-pool occupancy. |
| `0x62` | `CLEAR_STATUS` | PC -> ESP | Empty or five-byte clear request | Requested flags/counters are cleared before the empty `CLEAR_STATUS` acknowledgement is sent. |
| `0x64` | `GET_DEVICE_CONFIG` | PC -> ESP | Empty | Acknowledgement followed by `DEVICE_CONFIG`. |
| `0x65` | `DEVICE_CONFIG` | ESP -> PC | 16-byte versioned configuration | Complete non-secret persistent boot configuration. |
| `0x66` | `SET_DEVICE_CONFIG` | PC -> ESP | Complete 16-byte configuration | Atomically replaces the configuration; takes effect after reboot. |
| `0x67` | `GET_WIFI_STATUS` | PC -> ESP | Empty | Acknowledgement followed by `WIFI_STATUS`. |
| `0x68` | `WIFI_STATUS` | ESP -> PC | 12-byte versioned status | State, credential presence, RSSI, and IP; never SSID/password. |
| `0x69` | `SET_WIFI_CREDENTIALS` | PC -> ESP | Header followed by SSID/password | Replaces credentials; takes effect after reboot. |
| `0x6A` | `CLEAR_WIFI_CREDENTIALS` | PC -> ESP | Empty | Clears credentials; takes effect after reboot. |
| `0x6B` | `ERROR` | ESP -> PC | Failed command and ESP error | Command validation, configuration transfer, persistent setter, or update operation failed. |
| `0x6C` | `MSP_UPDATE_BEGIN` | PC -> ESP | 12-byte upload descriptor | Empty acknowledgement after staging setup; `ERROR` on rejection. |
| `0x6D` | `MSP_UPDATE_DATA` | PC -> ESP | 12-byte chunk header + data | 8-byte offset/sequence acknowledgement, or `ERROR`. |
| `0x6E` | `MSP_UPDATE_COMMIT` | PC -> ESP | Empty | Acknowledges persisted update scheduling; ESP32 reboots to program MSP430. |
| `0x6F` | `MSP_UPDATE_ABORT` | PC -> ESP | Empty | Acknowledges abort request; use before commit. |
| `0x70` | `MSP_UPDATE_GET_STATUS` | PC -> ESP | Empty | Empty acknowledgement followed by `MSP_UPDATE_STATUS`. |
| `0x71` | `MSP_UPDATE_STATUS` | ESP -> PC | 28-byte update status | Separate from acquisition `STATUS`. |
| `0x72` | `MSP_UPDATE_GET_DIAGNOSTICS` | PC -> ESP | Empty | Direct `MSP_UPDATE_DIAGNOSTICS` response, without a separate empty acknowledgement. |
| `0x73` | `MSP_UPDATE_DIAGNOSTICS` | ESP -> PC | 16-byte diagnostics | Last JTAG identification diagnostics. |
| `0x74` | `GET_FIRMWARE_INFO` | PC -> ESP | Empty | Empty acknowledgement followed by `FIRMWARE_INFO`. |
| `0x75` | `FIRMWARE_INFO` | ESP -> PC | 72-byte versioned firmware information | ESP32 build version and the MSP430 version detected during configuration, with reserved Git build metadata. |

Command values not explicitly listed above are invalid in the current protocol.
Commands documented as ESP32-to-PC should not be sent by a host.

## Persistent device configuration

The persistent device configuration controls how the ESP32 initializes Wi-Fi
and its power-saving features at startup. It is stored in non-volatile memory,
survives power cycles, and is applied after the ESP32 restarts.

`DEVICE_CONFIG` is the following packed 16-byte structure:

| Offset | Size (bytes) | Field | Allowed values | Default | Meaning |
|---:|---:|---|---|---|---|
| 0 | 1 | `version` | `1` | `1` | Structure version. |
| 1 | 1 | `size` | `16` | `16` | Complete structure size in bytes. |
| 2 | 1 | `wifi_enabled_at_boot` | `0` or `1` | `1` | Start Wi-Fi during boot. |
| 3 | 1 | `auto_provision` | `0` or `1` | `1` | Start provisioning when Wi-Fi is enabled and no credentials are saved. |
| 4 | 1 | `wifi_power_save_mode` | `0`: none; `1`: minimum modem; `2`: maximum modem | `2` | Select the Wi-Fi power-save mode. |
| 5 | 1 | `twt_enabled` | `0` or `1` | `0` | Enable Target Wake Time when supported. |
| 6 | 10 | `reserved` | All bytes zero | All bytes zero | Reserved for future versions. |

`SET_DEVICE_CONFIG` replaces the complete structure. A client should read the
current configuration, modify the required fields, write the complete structure,
and issue `RESET` to apply it.

`auto_provision` is consulted only when Wi-Fi is enabled at boot and no saved
credentials exist. It remains persistent after provisioning, and saved
credentials take priority.

The `SET_WIFI_CREDENTIALS` payload has this variable-length layout:

| Offset | Size (bytes) | Field | Requirements |
|---:|---:|---|---|
| 0 | 1 | `version` | Must be `1`. |
| 1 | 1 | `ssid_length` | 1–32 bytes. |
| 2 | 1 | `password_length` | 0–64 bytes. |
| 3 | 1 | `reserved` | Must be zero. |
| 4 | `ssid_length` | `ssid` | Raw SSID bytes. |
| 4 + `ssid_length` | `password_length` | `password` | Raw password bytes. |

Credentials can be replaced or cleared but never read through this protocol.

## Acknowledgement model

Most PC commands receive an empty packet with the same command ID as their
acknowledgement. The acknowledgement indicates that the command was accepted by
the protocol task. `SET_ACQ_CONFIG` now acknowledges after SPI transfer success,
but there is no separate MSP430 application-level acceptance response.
`MSP_UPDATE_COMMIT` acknowledges scheduling, not programming completion.
Use `GET_STATUS` for acquisition SPI/buffer errors and `MSP_UPDATE_GET_STATUS`
for the separate persisted update result. `PING` establishes ESP32 protocol
responsiveness, not MSP430 health.

Acknowledgements are ordered with acquisition data by the sole packet-TX
thread. Because RF frames are asynchronous, a `GET_DATA` packet may already be
buffered when the host begins waiting for a command response. The host parser
must consume complete packets and continue until it finds the expected command
ID. It must never interpret arbitrary bytes following an RF payload as a
response header.

Special response sequences are:

```text
PING        -> PING acknowledgement -> PONG("pong")
GET_STATUS  -> GET_STATUS acknowledgement -> STATUS(payload)
CLEAR_STATUS -> CLEAR_STATUS acknowledgement after clearing
RESET_MSP   -> RESET_MSP acknowledgement after MSP430 restart, or BUSY
CLOSE       -> CLOSE acknowledgement after stopping RX
```

## Acquisition frame

`GET_DATA` has an 804-byte payload:

| Offset | Size (bytes) | Field | Encoding |
|---:|---:|---|---|
| 0 | 1 | `frame_marker` | `0xFF` from MSP430. |
| 1 | 1 | `tx_rx_id` | Active TX/RX configuration index. |
| 2 | 2 | `acquisition_number` | Unsigned little-endian 16-bit sequence number. |
| 4 | 800 | `samples` | 400 little-endian signed 16-bit samples. |

Including the outer header, one acquisition packet occupies 813 application
bytes. At 500 FPS this requires 406,500 bytes/s (3.252 Mbit/s) before USB or TCP
transport overhead.

The acquisition number is a wrapping sequence value, not an array index or a
reliable indication of progress within a newly requested acquisition. Detect
gaps by comparing consecutive values with modulo-65536 arithmetic.

## Typical acquisition session

```text
PC                                      ESP32 / MSP430
--                                      --------------
connect/open CDC
PING ---------------------------------> claim session, release MSP430 reset
     <------------------------------- PING acknowledgement
     <------------------------------- PONG "pong"
SET_ACQ_CONFIG(package) --------------> transfer configuration to MSP430
     <------------------------------- SET_ACQ_CONFIG acknowledgement
CLEAR_STATUS(mask, counters=1) -------> clear diagnostics
     <------------------------------- CLEAR_STATUS acknowledgement
START_RX -----------------------------> enable forwarding
     <------------------------------- START_RX acknowledgement
     <------------------------------- GET_DATA frame 0
     <------------------------------- GET_DATA frame 1
     <------------------------------- ...
STOP_RX ------------------------------> stop and discard queued session frames
     <------------------------------- STOP_RX acknowledgement
GET_STATUS ---------------------------> snapshot diagnostics
     <------------------------------- GET_STATUS acknowledgement
     <------------------------------- STATUS payload
CLOSE --------------------------------> stop and clean up MSP430/session
     <------------------------------- CLOSE acknowledgement
```

## Runtime status

The version-1 `STATUS` payload is a packed 40-byte little-endian structure:

| Offset | Size (bytes) | Field | Meaning |
|---:|---:|---|---|
| 0 | 1 | `version` | Status schema version; currently 1. |
| 1 | 1 | `size` | Total payload size; currently 40. |
| 2 | 2 | `reserved` | Reserved, currently zero. |
| 4 | 4 | `error_flags` | Sticky error bit mask. |
| 8 | 4 | `buffer_overflow_count` | Times acquisition could not obtain a free frame slot. |
| 12 | 4 | `data_ready_count` | DATA_READY edges serviced by the acquisition thread. |
| 16 | 4 | `completed_spi_count` | Successful acquisition SPI transactions. |
| 20 | 4 | `transmitted_frame_count` | RF frames successfully written to the active link. |
| 24 | 4 | `discarded_frame_count` | Completed frames released without transmission, normally during stop/session cleanup or generation changes. |
| 28 | 4 | `spi_error_count` | Failed or timed-out SPI transfers. |
| 32 | 4 | `link_error_count` | Packet-write/link failures. |
| 36 | 2 | `current_buffer_usage` | Frame slots currently owned by SPI, READY, or TX. |
| 38 | 2 | `maximum_buffer_usage` | High-water mark since initialization or counter reset. |

### Error flags

| Bit | Mask | Name | Meaning |
|---:|---:|---|---|
| 0 | `0x00000001` | `ACQ_BUFFER_OVERFLOW` | No free DMA frame slot became available within the acquisition wait. Acquisition is stopped. |
| 1 | `0x00000002` | `DATA_READY_OVERFLOW` | Reserved by the current status schema for lost/excess DATA_READY events. |
| 2 | `0x00000004` | `SPI_TIMEOUT` | MSP430 edge or SPI shutdown/transfer timing failed. |
| 3 | `0x00000008` | `SPI_FAILURE` | Non-timeout SPI operation failed. |
| 4 | `0x00000010` | `LINK_TIMEOUT` | A packet could not be written within the link timeout. |
| 5 | `0x00000020` | `LINK_DISCONNECTED` | Reserved for explicit link-disconnect reporting. |
| 6 | `0x00000040` | `PROTOCOL` | Invalid active-session header or payload length. |

Error flags are sticky until `CLEAR_STATUS` or reboot. Counters are unsigned
32-bit values and are not automatically reset at the beginning of a host
acquisition unless the host requests it.

## Clearing status

An empty `CLEAR_STATUS` request clears all error bits but preserves counters.
The optional five-byte request payload is:

| Offset | Size (bytes) | Field | Meaning |
|---:|---:|---|---|
| 0 | 4 | `error_mask` | Little-endian bit mask of sticky errors to clear. |
| 4 | 1 | `clear_counters` | Nonzero clears all diagnostic counters and resets the frame-pool high-water mark. |

For example, an `error_mask` of `0xFFFFFFFF` with `clear_counters` set to `1`
clears every defined error flag and all counters.

## Firmware information

`GET_FIRMWARE_INFO` receives an empty acknowledgement followed by a
`FIRMWARE_INFO` response. The version-1 response payload is the following packed
72-byte structure:

| Offset | Size (bytes) | Field | Meaning |
|---:|---:|---|---|
| 0 | 1 | `version` | Firmware-information schema version; currently `1`. |
| 1 | 1 | `size` | Total payload size; currently `72`. |
| 2 | 1 | `flags` | Bit 0: MSP430 version valid; bit 1: ESP32 source dirty; bit 2: MSP430 source dirty; bits 3-7 reserved. Dirty bits are reserved and currently remain clear. |
| 3 | 1 | `reserved` | Reserved, currently zero. |
| 4 | 1 | `msp_major` | MSP430 semantic-version major component. |
| 5 | 1 | `msp_minor` | MSP430 semantic-version minor component. |
| 6 | 1 | `msp_patch` | MSP430 semantic-version patch component. |
| 7 | 1 | `reserved_2` | Reserved, currently zero. |
| 8 | 32 | `esp_version` | NUL-terminated ESP-IDF application-version string. |
| 40 | 13 | `esp_git_hash` | NUL-terminated Git hash of up to 12 hexadecimal characters; reserved and currently empty. |
| 53 | 13 | `msp_git_hash` | NUL-terminated Git hash of up to 12 hexadecimal characters; reserved and currently empty. |
| 66 | 6 | `reserved_3` | Reserved, currently zero. |

The MSP430 version becomes available after a successful acquisition-
configuration SPI transfer. Until then, or when using older MSP430 firmware,
flag bit 0 is clear and the MSP430 version fields must be ignored.
Git-hash generation and scoped dirty-source detection are not yet integrated
into the firmware builds, so both hash fields are empty and both dirty bits are
currently clear.

## MSP430 firmware update commands

The command table above includes the MSP430 update command IDs. See the
[MSP430 firmware update protocol](msp430_update_protocol.md) for upload payloads,
acknowledgements, status values, and diagnostics.
