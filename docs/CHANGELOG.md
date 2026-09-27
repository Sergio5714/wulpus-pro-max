# Changelog

All notable changes to the WULPUS Pro Max documentation will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added a comparison of the integrated WiFi host PCB, standalone XIAO
  ESP32-C6, and legacy nRF52 BLE host options.
- Documented persistent device configuration, reboot-only Wi-Fi policy,
  write-only credential commands, Wi-Fi runtime status, and the persistent
  Wi-Fi/TCP task model.
- Added WULPUS Pro Max full specifications as a dedicated documentation page.
- Added project-level documentation changelog.
- Added image documentation README with authorship and CC BY-ND 4.0 license information.
- Added PCB images to the root README hero and hardware photos sections.
- Added the system diagram to the root README.
- Documented native ESP32-C6 USB CDC operation, TCP/USB session arbitration,
  flashing and JTAG coexistence, binary-protocol logging constraints, and USB
  frame-rate profiling.

### Changed

- Updated the full specifications and README comparison with measured receive
  performance, data rates, power, mechanics, and arXiv sourcing.
- Renamed user-facing documentation from WULPUS PRO to WULPUS Pro Max and
  updated repository links for the new `wulpus-pro-max` name.
- Updated the WiFi host description and PRF specifications to document up to
  500 Hz over Wi-Fi/TCP or USB CDC, and replaced the outdated battery-charging
  status with external Adafruit battery support through a standard JST
  connector, USB charging, and integrated battery protection.
- Added the `images/v1_2` hardware photos, updated the root README gallery,
  captions and alt text, and extended image authorship coverage.
- Updated setup documentation to use `wulpus_pro_example.ipynb` as the main
  USB CDC, Wi-Fi, and BLE workflow and documented archived notebooks under
  `sw/legacy`.
- Documented GUI-compatible profiler NPZ output and the interactive NPZ
  viewer's file selection, configuration filtering, signal processing, and  replay controls.
- Moved the full specifications table from the root README to `docs/full_specifications.md`.
- Updated ESP32 and Python usage documentation for transport selection, USB
  connection ownership, and power-management behavior while a USB host is
  connected.
- Documented the task-based SPI DMA and packet-transmission architecture and
  runtime status commands.
