# WULPUS Pro Max software

This directory contains the WULPUS Pro Max desktop application, Python API,
communication transports, data-analysis tools, and compatibility notebooks.
The software connects to the device through USB CDC, Wi-Fi, or the legacy BLE
dongle.

## Overview

### Desktop application

The standalone PySide6 application is the primary user interface. It provides
device discovery and connection, ultrasound and TX/RX configuration, live
acquisition, saved-data viewing, diagnostics, device configuration, and ESP32
and MSP430 firmware updates.

Download the latest compiled GUI executable from
[GitHub Releases](https://github.com/Sergio5714/wulpus-pro-max/releases). The
Windows one-file release uses a versioned name such as
`WULPUS-Pro-Max-x.x.x.exe`.

### Python and notebook compatibility

The `wulpus` package provides the transport, configuration, acquisition,
firmware-update, and file-processing APIs used by the desktop application.
Two notebooks remain in this directory for compatibility:

- [`wulpus_pro_example.ipynb`](wulpus_pro_example.ipynb): acquisition,
  configuration, device setup, and interactive data analysis.
- [`wulpus_pro_firmware_update.ipynb`](wulpus_pro_firmware_update.ipynb):
  ESP32 and MSP430 firmware updates.

## Reference documentation

### Installation and operation

- [Dependency installation](docs/dependency_installation.md): install `uv`,
  create the Python environment, and select the required dependency groups.
- [Desktop GUI usage](docs/desktop_gui_usage.md): launch the application,
  connect a device, configure acquisition, record data, and use diagnostics.
- [Firmware flashing](docs/firmware_flashing.md): update ESP32 and MSP430
  firmware through the desktop application or compatibility notebook.
- [Notebook compatibility](docs/jupyter_compatibility.md): start Jupyter and
  use the two retained notebooks.
- [Data files and profiling](docs/data_and_profiling.md): inspect NPZ files,
  profile USB frame rates, and interpret runtime counters.

### Development and packaging

- [Desktop GUI developer guide](docs/desktop_gui_development.md): application
  architecture, threading, file contracts, tests, packaging, and release checks.
- [Desktop GUI component notes](desktop_gui/README.md): source layout and
  commands for running, formatting, testing, and building the application.

### Project history

- [Software changelog](CHANGELOG.md)

## Authors

- Sergei Vostrikov
- Cedric Hirschi, ETH Zurich

## License

The software is licensed under the [Apache License 2.0](LICENSE).
