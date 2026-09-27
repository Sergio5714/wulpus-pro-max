# WULPUS PRO source files for nRF52 DK BLE MCU firmware projects
This directory contains the source files for 
- nRF52832 BLE MCU (`fw/nrf52/ble_peripheral`) used by nRF52 DK.
- nRF52840 Dongle (`fw/nrf52/peripheral`) used to receive the ultrasound data on a host PC.

# How to get started?

Please refer to the `WULPUS User Manual` of the WULPUS system v 1.2.2 for the instructions on how to flash the BLE MCU and USB Dongle:
`https://github.com/Sergio5714/wulpus/blob/main/docs/wulpus_user_manual.pdf`

### Interconnect with nRF52 DK

Use the following pin mapping to connect the WULPUS PRO Acquisition PCB to the **nRF52 DK**:

| **Signal**         | **nRF52 DK Pin** | **WULPUS PRO Connector Pin** |
|--------------------|------------------|-------------------------------|
| `SPI_SS`           | P0.04            | X3.4                          |
| `SPI_CLK`          | P0.29            | X3.3                          |
| `SPI_MISO`         | P0.30            | X3.1                          |
| `SPI_MOSI`         | P0.31            | X3.2                          |
| `Data_ready`       | P0.24            | X4.2                          |
| `BLE_conn_ready`   | P0.25            | X4.3                          |

# License
The files in the `fw/nrf52/ble_peripheral` and `fw/nrf52/peripheral` directories contain third-party sources that come with their own licenses. See the respective folders and source files' headers for the licenses used.
