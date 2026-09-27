# Changelog

All main changes to this project will be documented in this file.
For the detailed description, please explore nested folders and corresponding CHANGELOG.md files (e.g. for PCB projects or firmware). 

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-09-27

### Removed

- Dropped ESP32-C6-DEVKITM-1 evaluation kit support, including its board defaults
  and development setup instructions.

### Added

- Added release tooling for validated ESP32 ZIPs, versioned MSP430 `.mspfw`
  images, and minimal PCB fabrication packages, including checksums, a unified
  graphical firmware updater, and development-script documentation.
- Added ESP32 and MSP430 running-firmware version reporting through the common
  USB/TCP protocol and main acquisition GUI.
- Added pinned clang-format tooling in the existing software development
  environment, an ESP32 formatting script, CI checks, and developer instructions.
- Added a host-board comparison covering the integrated WiFi host PCB,
  standalone XIAO ESP32-C6, and legacy nRF52 BLE solution.
- Added MSP430FR5043 firmware updating through the ESP32 over USB CDC or Wi-Fi,
  with staged images, boot-time JTAG programming/verification, and saved status
  and diagnostics.
- Documented updater wiring, partition requirements, protocol, and recovery,
  plus TI-TXT export. CCS Debug now exports TI-TXT.
- Added versioned ESP32 device configuration in NVS with reboot-only Wi-Fi
  boot, automatic provisioning, modem power-save, and TWT policies.
- Added protocol and Python APIs for complete device-configuration replacement,
  Wi-Fi status, and write-only credential replacement or clearing.
- Added a USB CDC device-configuration GUI to the main WULPUS PRO example
  notebook.
- Added an interactive viewer for GUI- and profiler-generated NPZ acquisitions,
  including TX/RX configuration filtering, acquisition navigation, band-pass
  filtering, Hilbert-envelope extraction, and controllable acquisition replay
  with stable Y-axis limits.
- Added exact GUI-saved acquisition configuration loading to the USB profiler,
  including persisted TX/RX mask arrays for reproducible headless tests and
  optional GUI-compatible NPZ acquisition output.
- Added ESP-IDF 6.0.1 installation and validation documentation for the ESP32
  firmware toolchain across Windows, Linux, macOS, and VS Code.
- Added structured ESP32 documentation covering runtime architecture,
  provisioning, the MSP430 SPI/configuration protocol, and the common USB/TCP
  PC protocol.
- Added native ESP32-C6 USB CDC communication as a wired alternative to Wi-Fi,
  using the existing WULPUS command and acquisition-data protocol.
- Added concurrent TCP/USB session arbitration and an explicit `BUSY` protocol
  response when another transport owns the device.
- Added a standalone Python USB frame-rate profiler.
- Added runtime acquisition diagnostics and host commands for reading and
  clearing sticky ESP32 errors.
- Added GUI stall diagnostics showing ESP32 acquisition errors and relevant
  buffer, SPI, transmission, and discard counters.

### Fixed

- Bound GUI acquisition to the transport that was actually opened and contained
  background transport failures in GUI status reporting.
- Embedded the NPZ viewer's live ipympl canvas directly so replay and slider
  updates use one visible plot instead of creating duplicate figure windows.
- Prevented high-frame-rate GUI processing from stalling USB acquisitions by
  keeping filtering, plotting, widget updates, and per-frame logging out of the
  continuous receive path.
- Prevented optional profiler data saving from adding per-frame NumPy copies to
  the high-rate USB receive loop.
- Fixed GUI acquisitions stalling partway through a run when the device's
  continuous acquisition sequence number exceeded the requested frame count.
- Kept the ESP32-C6 out of automatic light sleep whenever a USB host is
  connected, preventing missed USB CDC commands and enumeration failures.
- Fixed Windows ESP32-C6 CDC opening, partial writes, receive latency, and
  asynchronous acquisition frames arriving while command acknowledgements are
  pending.

### Changed

- Updated the README and full specifications with measured receive performance,
  streaming, power, mechanics, and arXiv sourcing.
- Renamed the user-facing project branding and repository from WULPUS PRO to
  WULPUS Pro Max.
- Released the WULPUS Pro Max WiFi host PCB v1.0.1 with updated title blocks,
  silkscreen, and regenerated design and fabrication outputs.
- Clarified in the README and host-board guide that the legacy nRF52 BLE option
  may suit lower-power applications, but is unsupported, is not recommended for
  new setups, and requires additional integration work.
- Polished the WiFi host PCB description and aligned the README and host
  documentation with support for up to 500 Hz PRF over Wi-Fi/TCP or USB CDC,
  external Adafruit battery power through a standard JST connector, USB battery
  charging, and integrated battery protection.
- Added the `docs/images/v1_2` hardware photos, updated the README gallery,
  captions and alt text, and extended image authorship coverage.
- Updated the project description and clarified attribution.
- Renamed `SET_CONFIG` to `SET_ACQ_CONFIG` while retaining wire ID `0x57`.
- Consolidated the supported USB CDC, Wi-Fi, and BLE workflow in
  `sw/wulpus_pro_example.ipynb` and moved older notebooks to `sw/legacy`.
- Reworked Wi-Fi provisioning as a persistent manager and made the persistent
  TCP thread wait for Wi-Fi connectivity.
- Added receive-only and all-channel USB profiler presets with explicit DC-DC
  timing, and corrected the MSP430 documentation to place DC-DC turn-on before
  the acquisition-period event.
- Documented the WULPUS PRO WiFi host PCB and its integrated XIAO ESP32-C6 as
  the primary ESP32 host, replacing the obsolete recommendation to use an
  external XIAO while the host PCB was under test.
- Increased the ESP32 DMA acquisition frame pool from 8 to 64 slots to tolerate
  longer host USB/GUI scheduling pauses at high frame rates.
- Refactored the ESP32 firmware into focused board, control, protocol, link,
  frame-storage, and task components around a transport-independent session
  layer. SPI acquisition and packet transmission now have independent owners
  connected by a zero-copy frame pool, and the acquisition owner is split into
  command/state, scheduler, DATA_READY/SPI-handshake, and frame-ownership
  modules.
- Reserved the native USB CDC interface for binary protocol traffic and disabled
  the conflicting application console in the default ESP32-C6 configuration.
- Made USB communication available before Wi-Fi provisioning or association
  completes.

## [1.1.0] - 2026-08-22

### Added

- Added the WULPUS PRO Wifi host PCB design (KiCad) and fabrication outputs.
- Added board-specific hardware licensing documentation and a separate `hw/LICENSE_ETH` file for the ETH Zurich PCB designs.
- Expanded the hardware README with the represented PCB designs, their CAD formats, purposes, and license assignments.
- Documented the WULPUS PRO Wifi host PCB testing status, planned battery and USB operating modes, and temporary use of an external XIAO ESP32-C6.
- Documented that `kicad_us_lib` is a private, development-only submodule and advised external users to generate project-specific KiCad libraries from the project files.
- Added the `kicad_us_lib` repository as a Git submodule under `hw/kicad_us_lib`.
- Added private-submodule cloning guidance for maintainers and external users to the root README.
- Added a linked table of contents to the root README.
- Added the WULPUS PRO arXiv preprint citation and BibTeX entry to the root README.
- Added PCBWay shared-project production and assembly information to the hardware README.
- Expanded the root README acknowledgements.

## [1.0.0] - 2026-07-11

### Added

- Added ESP32-C6 Wi-Fi firmware support for the Seeed Studio XIAO ESP32-C6 board, including board-specific defaults and README pin mapping.
- Added MSP430 board reset control logic to the ESP32 Wi-Fi firmware.
- Added a Python Wi-Fi example notebook for discovery, connection setup, configuration transfer, and data acquisition over the ESP32 TCP link.
- Added Apache-2.0 license headers to ESP32 firmware source files and Python support scripts.
- Added a documentation changelog under `docs/`.
- Added image documentation README with CC BY-ND 4.0 license information.
- Added WULPUS PRO images to the root README hero and hardware photos sections.
- Added the WULPUS PRO system diagram to the root README.
- Added `uv` project metadata and lockfile for Python dependency management.
- Added a root README specifications section comparing WULPUS PRO with the original WULPUS platform.

### Fixed

- Fixed the MSP430 firmware initialization so the preamplifier power switch is always enabled at startup.
- Fixed the ESP32-C6-DEVKITM-1 board defaults to avoid reusing GPIO2 for both SPI MOSI and MSP430 reset.

### Changed

- Refactored the ESP32 firmware configuration around reusable ESP-IDF defaults, target-specific defaults, and board-specific pinout files.
- Updated the ESP32 project from ESP-IDF 5.4.1 to ESP-IDF 6.0.1.
- Updated ESP32 documentation for tested DevKit and XIAO boards, board selection, flashing, serial port selection, and WULPUS PRO connector pin mappings.
- Updated ESP32 firmware attribution with author information and ESP-IDF example note.
- Reworked the root README introduction with a concise overview of the pulser, acquisition front end, supported transducers, and module form factor.
- Updated project READMEs for repository structure, build instructions, usage flows, firmware links, and WULPUS PRO-specific documentation pointers.
- Migrated Python package management from conda to uv.
- Moved WULPUS PRO full specifications from the root README into `docs/full_specifications.md`.
- Updated gitignore rules.

### Removed

- Removed the old ESP32-C6-DEVKITM-1 MSP430 reset mapping from GPIO2; GPIO2 is used for SPI MOSI and MSP430 reset is now on GPIO3.
- Removed the old Conda `sw/requirements.yml` dependency file.

## [0.1.0] - 2025-05-1

### Added
- Initial release (without official GitHub release)

### Fixed

### Changed
