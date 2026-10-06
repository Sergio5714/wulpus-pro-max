# Changelog

All main changes to this project will be documented in this file.
For the detailed description, please explore nested folders and corresponding CHANGELOG.md files (e.g. for PCB projects or firmware). 

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] - 2026-10-06

### Added

- Added a standalone desktop application for device connection, ultrasound and
  TX/RX configuration, live acquisition, NPZ recording and viewing, device
  configuration, diagnostics, logging, and firmware updates.
- Added live previews for acquisition timing, excitation, high-voltage duty
  cycle, and fixed or time-varying receive gain.
- Added a versioned, one-file Windows executable build and a release packaging
  script that places the executable and its SHA-256 checksum under `releases/`.

### Changed

- The desktop GUI now refreshes firmware versions automatically after connecting
  and after acquisition completes.
- The standalone GUI title, one-file executable name, and Windows executable
  metadata now use the software version from `sw/pyproject.toml`.
- Reorganized software documentation around the desktop application and moved
  detailed workflows into focused guides.

### Fixed

- Corrected receive-gain modeling, including VGA precharge and the 80 dB VGA
  gain limit.
- Kept the detected MSP430 firmware version available after normal acquisition
  cleanup restarts so the desktop GUI no longer falls back to `unknown`.

### Removed

- Removed archived software notebooks and obsolete generated figures while
  retaining the two supported compatibility notebooks.

## [2.0.0] - 2026-09-27

### Added

- Added native ESP32-C6 USB CDC communication alongside Wi-Fi/TCP, with
  single-host session arbitration and common acquisition and diagnostic APIs.
- Added persistent ESP32 configuration and Wi-Fi provisioning, including boot,
  automatic provisioning, modem power-save, and TWT policies.
- Added MSP430 programming through the ESP32, running-firmware version reporting,
  and a unified graphical updater for validated ESP32 and MSP430 releases.
- Added an interactive NPZ acquisition viewer and a USB frame-rate profiler with
  saved-configuration loading, acquisition metrics, and compatible NPZ output.
- Added release tooling for ESP32, MSP430, and PCB packages, with checksums,
  license material, automated ESP32 formatting, and CI validation.
- Added structured documentation for host-board selection, ESP32 setup and
  architecture, Wi-Fi provisioning, protocols, firmware updates, and recovery.

### Changed

- Renamed the project and user-facing software from WULPUS PRO to WULPUS Pro
  Max.
- Released the WiFi host PCB v1.0.1 and made it the primary ESP32 host; retained
  the standalone XIAO ESP32-C6 as a development option and classified the nRF52
  BLE host as legacy and unsupported.
- Rebuilt the ESP32 firmware around transport-independent sessions, separate
  acquisition and transmission ownership, and buffered zero-copy frame storage.
- Consolidated USB CDC, Wi-Fi, and BLE operation in the main software notebook,
  made USB CDC the default transport, and archived specialized notebooks.
- Updated system specifications and documentation with measured performance,
  streaming, power, mechanics, hardware photos, and attribution.

### Fixed

- Improved acquisition reliability by keeping host visualization work out of
  the receive path, accepting continuous device acquisition counters, and
  reporting background transport failures in the GUI.

### Removed

- Removed ESP32-C6-DEVKITM-1 support and its board configuration.
- Removed the legacy 8-channel WULPUS software stack in favor of the WULPUS Pro
  Max configuration and transport APIs.

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
