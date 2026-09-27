# Host board options

WULPUS Pro Max has three host configurations. The
[WiFi host PCB](../hw/wulpus_wifi_host_pcb) is recommended for normal
use because it integrates communication, power delivery, and programming in one
board. The other options are intended for development or compatibility with
legacy setups. The nRF52 BLE option may also suit applications that need even
lower power consumption than the WiFi host solution, but it is unsupported,
is not recommended for new setups, and requires additional integration work.

| Capability | WiFi host PCB | Standalone Seeed Studio XIAO ESP32-C6 | nRF52 BLE solution |
|---|---|---|---|
| Status | Primary and recommended | Development alternative | Legacy, unsupported; not recommended for new setups |
| PC connection | USB CDC or WiFi/TCP | USB CDC or WiFi/TCP | BLE through an nRF52840 USB dongle |
| Acquisition PCB interface | Integrated WULPUS PRO connector | Manual Dupont wiring | Manual Dupont wiring to an nRF52832 DK |
| Powers the Acquisition PCB | Yes | No; external lab supplies are required | No; external power is required |
| Programs the MSP430 | Yes, through the updater GUI | No; JTAG signals are not exposed on the Acquisition PCB Dupont connectors | No; use an external programmer |
| Battery charging | Supported via USB, with integrated battery protection | Not provided for the Acquisition PCB | Not provided |
| Additional hardware | One data-capable USB-C cable | Data-capable USB-C cable, Dupont wires, and lab power supplies | nRF52832 DK, nRF52840 USB dongle, wiring, and external power |

## WiFi host PCB

This option provides the simplest setup. A single USB-C connection can power
the system, provide USB communication, flash the ESP32, and then program the
MSP430 through the updater GUI. WiFi can be used for wireless control and data
transfer after provisioning, with acquisition PRFs of up to 500 Hz over
Wi-Fi/TCP or native USB CDC. The platform can also be powered by an external
Adafruit battery with a standard JST connector, with USB battery charging and
integrated battery protection.

## Standalone Seeed Studio XIAO ESP32-C6

The standalone XIAO runs the same ESP32 firmware and supports the same USB CDC
and WiFi/TCP protocol. It must be wired manually to the Acquisition PCB, and all
Acquisition PCB power domains must be supplied externally. It cannot program
the MSP430, so the Acquisition PCB must already contain compatible MSP430
firmware. See the [board setup and pin mapping](../fw/esp32/docs/development_guide.md#supported-boards).

## nRF52 BLE solution

The legacy BLE setup uses an nRF52832 DK as the Acquisition PCB host and an
nRF52840 USB dongle at the PC. It may suit applications with stricter power
requirements than the WiFi host solution, but it is unsupported and is not
recommended for new setups. Additional integration work is required, including
manual wiring, external power, and a separate programmer for the MSP430. It
does not provide the integrated USB, WiFi, power, or MSP430-programming workflow
of the WiFi host PCB. See the [legacy nRF52 firmware instructions](../fw/nrf52/README.md).
