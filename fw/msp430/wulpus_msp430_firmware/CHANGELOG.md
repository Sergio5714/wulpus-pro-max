# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-09-27

### Added

- Added a compiled semantic version returned to the host MCU during the existing
  full-duplex SPI transaction.

## [1.0.0]

### Changed

- Removed the P5.7 host-ready polling gate. The ESP32 host now keeps the MSP430 in reset until a TCP client connects.

## [0.1.0] - 2025-05-01

### Added

- MSP 430 firmware from WULPUS repository version 1.2.2

### Fixed

### Changed

- Changed pin mapping of the pins according to the schematics of the WULPUS PRO
- Added initialization of multiple new IOs for enbaling power domain and VGA control
- Added two new configuration parameters to the `msp_config` for VGA control:
    - `VGA Precharge time`
    - `Wiper code for gain slope`

- Added a new timer instance for precise time delay for VGA control input precharging.
