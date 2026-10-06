# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-10-06

### Added

- Added a standalone PySide6 desktop application with USB CDC, Wi-Fi, and BLE
  connections; ultrasound and TX/RX configuration; live A-mode and B-mode
  acquisition; NPZ recording and viewing; device configuration; diagnostics;
  debug logging; and ESP32 and MSP430 firmware updates.
- Added live previews for high-voltage duty cycle, excitation, acquisition
  timing, and fixed or time-varying receive gain.
- Added a versioned, one-file desktop executable build.

### Changed

- Refreshed firmware versions automatically after connection and acquisition.
- Used the project version in the GUI title, executable name, and Windows
  metadata.
- Split desktop usage, firmware flashing, notebook, and data instructions into
  focused guides.

### Fixed

- Corrected receive-gain modeling, including VGA precharge and the 80 dB VGA
  gain limit.

### Removed

- Removed archived notebooks and obsolete generated figures. The two supported
  compatibility notebooks remain in `sw`.

## [0.2.0] - 2026-09-27

### Added

- Added native ESP32-C6 USB CDC communication and transport selection between
  USB CDC, Wi-Fi, and the BLE dongle in the Jupyter acquisition GUI.
- Added persistent ESP32 configuration and write-only Wi-Fi credential
  management over USB CDC.
- Added a unified firmware-update notebook for validated ESP32 and MSP430
  release packages, while retaining raw MSP430 development formats.
- Added ESP32 and MSP430 firmware-version reporting and ESP32 runtime diagnostic
  APIs, including error flags, frame counters, and buffer occupancy.
- Added an interactive NPZ viewer with TX/RX filtering, acquisition navigation,
  raw, band-pass-filtered, and envelope views, and asynchronous replay.
- Added a USB frame-rate profiler with configuration presets, saved-configuration
  loading, NPZ output, gap detection, latency, timeout, and achieved-FPS reports.

### Changed

- Renamed user-facing software from WULPUS PRO to WULPUS Pro Max.
- Replaced the separate Wi-Fi example with `wulpus_pro_example.ipynb`, made USB
  CDC the default transport, and archived the older specialized notebooks.
- Made the acquisition GUI transport-neutral and hardened Wi-Fi framing,
  command handling, cleanup, and acquisition lifecycle behavior.
- Renamed the BLE transport to `WulpusBleDongle` and the acquisition
  configuration method to `send_acq_config`; the old API names were removed.

### Fixed

- Reported acquisition-thread transport failures in the GUI instead of leaving
  uncaught background-thread errors.
- Prevented high-rate acquisition processing and GUI updates from blocking the
  frame-receive path.
- Prevented finite acquisitions from stalling when the device's continuous
  acquisition counter exceeded the requested frame count.

### Removed

- Removed the legacy 8-channel WULPUS configuration, packet, scanner, Wi-Fi, and
  channel-GUI modules. The software now exposes only the WULPUS Pro Max stack.

## [0.1.0] - 2025-05-01

### Added

- GUI and library from WULPUS repository version 1.2.2
- A curve to the main GUI, visualizing the gain profile over time.

### Fixed

### Changed

- Extended the number of channels to 16.
- Modified TX/RX pin mapping.
- Added two new configuration parameters for VGA control:
    - `VGA Precharge time [cycles]`
    - `Wiper code for gain slope []`

- Extended the configuration package to accomodate two new parameters.

### Removed
- Removed `Capture restart time` and `Capture timeout time` from the old GUI.
