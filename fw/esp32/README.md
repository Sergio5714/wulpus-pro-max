# WULPUS Pro Max ESP32 firmware

This ESP-IDF firmware connects the Acquisition PCB to a PC through
either Wi-Fi/TCP or the native USB Serial/JTAG CDC interface of an ESP32-C6.
Both transports use the same framed binary protocol and can remain available
concurrently, while session arbitration ensures that only one host controls the
Acquisition PCB at a time.

## Overview

### Host board

The **[WULPUS Pro Max WiFi host PCB](../../hw/wulpus_wifi_host_pcb)** is the primary
host board for this firmware. It contains a Seeed Studio XIAO ESP32-C6 and uses
the XIAO board configuration in this project. A standalone XIAO ESP32-C6 is
supported as a development alternative.

### Main functions

- **Runtime MSP430 configuration and ultrasound data acquisition:** sends
  acquisition settings and receives ultrasound frames through SPI with DMA.
- **Real-time data streaming over Wi-Fi or USB CDC:** selects the active
  transport at runtime through protocol sessions, with one controlling host
  at a time.
- **Persistent ESP32 configuration:** stores device boot policy, Wi-Fi settings,
  and credentials across power cycles; changes take effect after reboot.
- **MSP430 flashing:** accepts firmware images over USB/TCP and programs the
  MSP430FR5043 through four-wire JTAG.
- **Wi-Fi provisioning and discovery:** supports SoftAP setup, automatic
  reconnection, and mDNS discovery by the host application.
- **Buffering and diagnostics:** buffers acquisition frames and reports SPI,
  transport, and buffer errors, frame counters, and MSP430 update results.

> MSP430 firmware flashing is available only with the WULPUS Pro Max WiFi host PCB;
> it is not available with a standalone XIAO ESP32-C6.

## Reference documentation

### Build and installation

- [ESP-IDF toolchain setup](docs/esp_idf_toolchain_guide.md) — installation on Windows,
  Linux, and macOS, VS Code configuration, environment activation, verification,
  and troubleshooting.
- [Development guide](docs/development_guide.md) — requirements, board configuration,
  building, flashing, and creating a merged firmware image.

### Operation and configuration

- [MSP430 updater implementation](docs/msp430_update_guide.md) — staging,
  boot-time JTAG programming, verification, diagnostics, and recovery behavior.
- [Wi-Fi provisioning](docs/wifi_provisioning_guide.md) — first boot, SoftAP parameters,
  credential storage, reconnection, reprovisioning, and USB availability.

### Architecture and protocols

- [Firmware architecture](docs/firmware_architecture.md) — components, threads, data and
  control paths, DMA frame buffering, session lifecycle, and USB/Wi-Fi switching.
- [ESP32-to-MSP430 acquisition protocol](docs/msp430_acq_protocol.md) — SPI electrical settings,
  DATA_READY handshake, configuration-package fields, timing conversions,
  restart behavior, and RF frame layout.
- [ESP32-to-PC protocol](docs/esp32_pc_protocol.md) — USB/TCP framing, commands,
  acknowledgements, acquisition packets, status flags, and diagnostic counters.
- [MSP430 firmware update protocol](docs/msp430_update_protocol.md) — image
  upload commands, update states, and JTAG diagnostics.

### Project history

- [Firmware changelog](CHANGELOG.md)

## Authors

- Sergei Vostrikov
- Cedric Hirschi, ETH Zurich

## License

Project source files are licensed under the terms stated in their headers and
the repository license files. ESP-IDF and its third-party components retain
their respective licenses.
