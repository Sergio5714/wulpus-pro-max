# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-09-27

### Removed

- Dropped ESP32-C6-DEVKITM-1 evaluation kit support, including its board defaults
  and development setup instructions.

### Added

- Added ESP-IDF application-version and runtime MSP430-version reporting over
  the PC protocol, with the ESP32 release read from `firmware_version.txt` and
  required to match the firmware changelog, plus MSP430 discovery during the
  configuration SPI exchange. Reserved per-firmware Git hash fields and dirty
  flags for future build integration.
- Added MSP430FR5043 updates over USB/TCP with a 256 KiB staging partition,
  CRC-checked section images, boot-time four-wire JTAG programming/verification,
  persisted results and diagnostics, and XIAO JTAG GPIO defaults.
- Added the Python MSP430 updater, TI-TXT/Intel HEX import, `.mspfw` packaging,
  and a dedicated USB update notebook.
- Added versioned persistent device configuration, reboot-only Wi-Fi policy and
  credential commands, a persistent Wi-Fi manager, and connection-gated TCP.
- Added an ESP-IDF 6.0.1 toolchain guide covering EIM installation on Windows,
  Linux, and macOS, VS Code setup, manual installation, environment validation,
  flashing, and troubleshooting.
- Added structured ESP32 documentation for firmware threads and data/control
  paths, USB/TCP session switching, Wi-Fi provisioning, the MSP430 SPI and
  configuration protocol, and the framed ESP32-to-PC command/status protocol.
- Added native ESP32-C6 USB CDC as a wired WULPUS Pro Max command and RF-data transport.
- Added first-valid-command arbitration between concurrent TCP and USB listeners, including a `BUSY` response for the losing transport.
- Added a transport-neutral byte-stream layer with exact reads, complete writes, header prefetching, and packet-level TX locking.
- Added a fixed DMA-capable acquisition frame pool, sticky runtime error status,
  and `GET_STATUS`, `STATUS`, and `CLEAR_STATUS` protocol commands.

### Changed

- Renamed the user-facing ESP32 project branding from WULPUS PRO to WULPUS Pro
  Max. This naming change does not alter the existing ETH Zurich copyright,
  authorship, or license notices in inherited source files.
- Acquisition configuration now acknowledges after SPI success and reports
  transfer failures through `ERROR`; start/reset commands acknowledge after
  their actions. Acquisition configuration, start, and resets reject requests
  while the committed update is pending.
- Enabled TI-TXT export in the MSP430 CCS Debug configuration.
- Renamed the ESP acquisition command from `SET_CONFIG` to `SET_ACQ_CONFIG`
  while retaining wire ID `0x57` and without retaining the old command name.
- Made the TCP listener a persistent task gated by Wi-Fi connectivity and moved
  mDNS startup under the persistent Wi-Fi workflow.
- Corrected the documented MSP430 timer ordering: DC-DC turn-on precedes and
  therefore has a lower timer value than the acquisition period.
- Identified the WULPUS Pro Max WiFi host PCB, containing a XIAO ESP32-C6, as the
  primary firmware target throughout the documentation; standalone XIAO
  boards remain a development alternative.
- Increased the default DMA acquisition frame pool from 8 to 64 slots, giving
  128 ms of buffering at 500 FPS, and raised the configurable limit to 128.
- Moved command handling, MSP430 lifecycle management, and acquisition cleanup into one transport-independent session runner.
- Routed RF frames through the active session transport instead of the TCP socket directly.
- Reserved USB CDC for binary protocol data and disabled the conflicting application console by default.
- Prevented automatic light sleep whenever a USB host connection is detected,
  keeping enumeration and USB CDC communication responsive until physical
  disconnection.
- Started the USB listener before waiting for Wi-Fi provisioning or association,
  allowing wired operation when the network is unavailable or unconfigured.
- Split board access, frame storage, control state, protocol framing, generic
  links, and application threads into focused components.
- Made the acquisition thread the sole SPI readout owner and the packet TX
  thread the sole USB/TCP writer, isolating SPI DMA from link backpressure and
  prioritizing control responses at packet boundaries.
- Split the acquisition owner into focused command/state, scheduler,
  DATA_READY/SPI-handshake, and frame-ownership modules while retaining one
  task as the sole owner of MSP430 acquisition operations.
- Reduced `app_main()` to component initialization and task startup, and moved
  every application task implementation under `components/threads`.
- Expanded the firmware README with communication architecture, arbitration, USB flashing/JTAG coexistence, logging, and power-management behavior.

## [1.1.0] - 2026-08-22

### Fixed

- Matched the XIAO ESP32-C6 defaults to the WULPUS Pro Max Wi-Fi host PCB routing.

### Changed

- Replaced the dedicated host-ready handshake with MSP430 reset gating: the ESP32 now holds the MSP430 in reset until a TCP client connects and asserts reset again after disconnects or communication failures.
- Added a bounded graceful-shutdown handshake that sends the MSP430 restart command and waits for its post-`disableAll()` configuration request before asserting reset, with immediate reset retained as a timeout/error fallback.

### Removed

- Removed the dedicated host-ready GPIO configuration and output handling.

## [1.0.0] - 2026-07-11

### Added

- Added ESP32-C6 Wi-Fi firmware for using an ESP32 module as a WULPUS Pro Max host interface.
- Added support for the Seeed Studio XIAO ESP32-C6 board.
- Added board-specific defaults for the Seeed Studio XIAO ESP32-C6 and ESP32-C6-DEVKITM-1.
- Added Wi-Fi provisioning support for storing network credentials in non-volatile memory.
- Added mDNS-based local network discovery.
- Added MSP430 reset control from the ESP32 host firmware.
- Added power-management support for light-sleep operation when idle.
- Added WULPUS PRO connector pin mapping documentation for supported ESP32-C6 boards.
- Added Python-side Wi-Fi usage documentation through `../../sw/wulpus_pro_example.ipynb`.

### Fixed

- Fixed the ESP32-C6-DEVKITM-1 defaults so `MSP_RST_N` no longer conflicts with SPI MOSI on GPIO2.

### Changed

- Updated the project to ESP-IDF 6.0.1.
- Refactored ESP-IDF configuration into reusable project defaults, target-specific defaults, and board-specific defaults.
- Documented first-time Wi-Fi provisioning after flashing the firmware.
- Documented tested board variants, board selection, build, flash, and serial-port usage.

### Removed

- Removed the old ESP32-C6-DEVKITM-1 reset mapping from GPIO2; `MSP_RST_N` is now mapped to GPIO3 for that board.
