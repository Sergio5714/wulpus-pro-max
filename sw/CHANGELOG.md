# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-09-27

### Added

- Added validated ESP32-C6 release-package flashing through esptool and renamed
  the MSP430 notebook to a unified firmware-update notebook with separate ESP32
  and MSP430 operations.
- Added a firmware-information API and GUI label for the running ESP32 and
  detected MSP430 firmware versions, including reserved Git hash and dirty-state
  fields for future firmware build integration.
- Added USB CDC APIs and a Jupyter GUI for persistent device configuration and
  write-only Wi-Fi credential management.
- Added an interactive Jupyter NPZ viewer with browser upload, direct path
  loading, TX/RX configuration filtering, acquisition navigation, metadata,
  raw ADC plotting, GUI-equivalent band-pass filtering, and Hilbert-envelope
  extraction, plus asynchronous replay from the current slider position at a
  configurable frame rate and a fixed Y-axis range during playback.
- Selectable Wi-Fi and BLE communication transports in `WulpusGuiSingleCh`.
- Native ESP32-C6 USB CDC transport for wired WULPUS Pro Max communication.
- Added a GUI acquisition-status field that reports decoded ESP32 error flags,
  overflow, SPI, transmission, discard, and frame-buffer counters when frame
  reception stalls.
- Added a standalone USB frame-rate profiler with acquisition-number gap,
  timeout, latency, and achieved-FPS reporting.
- Added explicit `simplified` and `active-all` profiler modes; the active mode
  enables every TX/RX channel and fixes DC-DC turn-on at 100 us, while custom
  mode exposes absolute or period-relative DC-DC timing.
- Added profiler loading of GUI-saved acquisition JSON, including complete
  timing/gain settings and TX/RX masks in newly saved configuration files.
- Added optional profiler output in the GUI-compatible NPZ format, with
  period-specific filenames for multi-rate sweeps.
- Added Python APIs for reading versioned ESP32 runtime status and clearing
  selected sticky errors and diagnostic counters.

### Fixed

- Bound acquisition to the communication link that was successfully opened,
  preventing a stale default Wi-Fi link from being used after transport
  selection.
- Caught acquisition-thread transport failures and reported them through the
  GUI instead of emitting uncaught background-thread tracebacks.
- Prevented duplicate NPZ-viewer figure windows by embedding the live ipympl
  canvas directly while preserving interactive slider and replay updates.
- Prevented high-frame-rate GUI acquisitions from overflowing the ESP32 frame
  pool by moving B-mode filtering/envelope processing to the visualization
  thread and throttling progress-widget and debug-log updates to 10 Hz.
- Kept GUI-compatible profiler saving out of the acquisition hot path by
  retaining received frame views and assembling the NPZ arrays after RX stops.
- Prevented finite GUI acquisitions from stalling when the device's continuous
  16-bit acquisition counter exceeds the requested frame count; received frames
  are stored using the GUI's independent sequential frame index.
- Worked around the Windows pySerial `SetCommState` error 31 affecting the
  ESP32-C6 USB Serial/JTAG CDC port while preserving all other configuration
  errors.
- Removed multi-second USB receive stalls by blocking for the first byte and
  then draining only the bytes already available from the serial driver.
- Prevented asynchronous `GET_DATA` frames from being mistaken for command
  acknowledgements, including during acquisition shutdown.
- Preserved partial serial writes and reported write timeouts instead of
  silently truncating protocol packets.

### Changed

- Renamed user-facing software branding from WULPUS PRO to WULPUS Pro Max.
- Renamed acquisition configuration APIs to `send_acq_config` without keeping
  the old method name.
- Renamed the main notebook to `wulpus_pro_example.ipynb`, made USB CDC its
  default transport, and moved older specialized notebooks to `legacy/`.
- Moved the ESP32 configuration widgets into `wulpus/device_config_gui.py`,
  arranged credential controls in a right-hand panel, and added explicit USB
  disconnect support.
- Renamed the BLE serial transport from `dongle.py` / `WulpusDongle` to `ble_dongle.py` / `WulpusBleDongle`.
- Decoupled `WulpusGuiSingleCh` from the BLE transport and made its device controls transport-neutral.
- Renamed the Wi-Fi transport and discovery APIs for WULPUS Pro Max and hardened TCP framing, command handling, connection cleanup, and acquisition lifecycle management.
- Reorganized `wulpus_pro_example.ipynb` to launch the GUI after explicit TX/RX and interactive ultrasound configuration, followed by the detailed manual Wi-Fi workflow.
- Added single-owner TCP/USB session arbitration to the ESP32 firmware while preserving the existing WULPUS wire protocol.
- Made the common framed-packet backlog and parser serve both command responses
  and acquisition data so packet boundaries remain synchronized.

### Removed

- Removed the legacy 8-channel WULPUS configuration, packet, and channel-GUI modules. This repository now exposes only the WULPUS Pro Max configuration stack.

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
