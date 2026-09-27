# WULPUS Pro Max source files for MSP430 Ultrasound MCU firmware project
This directory contains the source firmware files for 
- MSP430FR5043 Ultrasound MCU (`fw/msp430/wulpus_msp430_firmware`) mounted on the WULPUS Pro Max PCB

# Build and export firmware

Install Code Composer Studio with the TI MSP430 21.6 compiler family.
Import `wulpus_msp430_firmware` into Code Composer Studio as an existing CCS
project. Its CCS project name is `wulpus_pro_msp430_firmware` and it uses the TI
MSP430 21.6 compiler family. Build **Debug** to produce the `.out` executable
and a TI-TXT image: the Debug configuration now enables the MSP430 Hex Utility
with TI-TXT output and 8-bit memory/ROM widths. Release does not currently
enable that export step. The project preferences allow flexible compiler/product
version matching, so pin the installed toolchain for reproducible builds.

# Flashing

For the WiFi host PCB, follow the user-facing
[firmware update guide](../../docs/firmware_update_guide.md).

An MSP-FET can alternatively program the MSP430 using the procedure in the
legacy [WULPUS User Manual](https://github.com/pulp-bio/wulpus/blob/main/docs/wulpus_user_manual.pdf).
Before connecting the programmer, verify the MSP-FET pin mapping against the
Acquisition PCB schematic and connector pinout.
Disconnect the MSP-FET when using the ESP32 as the JTAG programmer.

# License
This directory contains third-party sources with their own licenses (primarily
BSD and Apache 2.0). See the respective folders and source headers, including
[`driverlib/license.txt`](wulpus_msp430_firmware/driverlib/license.txt). Firmware
releases must include applicable notices for bundled code and linked runtime
libraries. A compiler change does not remove those dependency obligations.
