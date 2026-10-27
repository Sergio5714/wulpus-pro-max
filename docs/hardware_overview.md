# Hardware overview and replication guide

This page summarizes the hardware needed to reproduce a standard WULPUS Pro
Max system. It covers the default WiFi/USB configuration; alternative host
boards are described in the [host board options](host_board_options.md).

![Assembled WULPUS Pro Max system](images/v1_2/full_system.jpg){ .wp-figure width="80%" }

## Core hardware

| Item | Required | Purpose |
| --- | --- | --- |
| WULPUS PRO Acquisition PCB | Yes | Ultrasound transmit and receive paths, high-voltage switching, power supplies, MSP430 controller, and host interface |
| WULPUS Pro Max WiFi host PCB | Yes, for the default system | USB and Wi-Fi communication, system power, MSP430 programming, battery charging, and protection |
| Ultrasound transducer | Yes | PZT or supported CMUT transducer appropriate for the experiment |
| Data-capable USB-C cable | Yes for setup | Powers the complete system, provides USB CDC communication, and enables firmware updates |
| Host computer | Yes | Runs the desktop application or Python software |
| USB power bank or single-cell Li-Po battery | Optional | Powers portable Wi-Fi operation; a Li-Po battery must have the correct connector polarity and support at least 1 A peak discharge current |

The polyCMUT adapter PCB is optional and is only needed for compatible research
transducers. The integrated WiFi host PCB is required for the default WULPUS
Pro Max system. The standalone ESP32-C6 and legacy BLE configurations are
non-default alternatives that require additional wiring, power hardware, or
programming equipment.

## PCBWay shared projects

The shared projects provide a convenient route to outsourced PCB production
and assembly:

- [WULPUS PRO Acquisition PCB v1.0.0](https://www.pcbway.com/project/shareproject/WULPUS_PRO_Evaluation_board_v1_0_0_992d7510.html)
- [WULPUS Pro Max WiFi host PCB v1.0.0](https://www.pcbway.com/project/shareproject/WULPUS_PRO_WiFi_host_PCB_7cfe7806.html)

Review the board revision, fabrication options, component substitutions, and
assembly quotation before placing an order. Shared-project pricing and part
availability can change.

## Price estimate

The following baseline comes from the project hardware documentation and
mid-2026 PCBWay pricing:

| Item | Estimated price per system |
| --- | ---: |
| Assembled WULPUS PRO Acquisition PCB | USD 220 |
| Assembled WULPUS Pro Max WiFi host PCB | USD 40 |
| **Core assembled PCB subtotal** | **USD 260** |

Allow approximately **one month lead time** for outsourced production and
assembly. This estimate is indicative rather than a quotation. It does not
include:

- shipping, taxes, customs duties, or payment fees;
- minimum-order or panelization effects;
- the ultrasound transducer or optional polyCMUT adapter;
- a USB-C cable, battery, power bank, or host computer;
- component substitutions, rework, test fixtures, or laboratory equipment.

For budgeting, request a current quotation for both shared projects and add the
cost of the application-specific transducer and local import charges.

## Manufacturing from repository files

For reproducible manufacturing, first check
[GitHub Releases](https://github.com/Sergio5714/wulpus-pro-max/releases) and
download the versioned fabrication packages attached to the selected release:

- `wulpus-pro-max-acquisition-pcb-<version>.zip`
- `wulpus-pro-max-wifi-host-pcb-<version>.zip`

Download the corresponding `.zip.sha256` files and verify each archive before
sending it to a manufacturer. The release ZIPs contain the reviewed fabrication
outputs, bills of materials, pick-and-place data, schematics, assembly drawings,
and applicable license and changelog files. They intentionally exclude editable
PCB sources, firmware, backup directories, and private library content.

Use the versioned release ZIPs when reproducing a released board revision. The
repository directories below are useful for design review and development, but
their current contents may be newer than the fabrication package for a specific
release:

- [Acquisition PCB design and fabrication outputs](https://github.com/Sergio5714/wulpus-pro-max/tree/dev/hw/wulpus_pro_acq_pcb_dev_board)
- [WiFi host PCB design and fabrication outputs](https://github.com/Sergio5714/wulpus-pro-max/tree/dev/hw/wulpus_wifi_host_pcb)
- [Hardware source overview and licensing](https://github.com/Sergio5714/wulpus-pro-max/blob/dev/hw/README.md)

The private `hw/kicad_us_lib` development submodule is not required to use the
released fabrication outputs. When editing the KiCad design, generate local
project libraries from the symbols and footprints embedded in the released
project rather than depending on the private library.

## Recommended replication path

1. Order assembled Acquisition and WiFi host PCBs from the shared PCBWay
   projects above, or manufacture them using the versioned release packages.
2. Inspect the assembled boards against the assembly drawings and check for
   misplaced, rotated, or poorly soldered components before applying power.
3. Mate the WiFi host PCB with the Acquisition PCB and connect the system using
   a data-capable USB-C cable.
4. Download and run the standalone desktop executable from
   [GitHub Releases](https://github.com/Sergio5714/wulpus-pro-max/releases). It
   does not require installation. Developers who want to run the application
   from source can follow the
   [source setup guide](https://github.com/Sergio5714/wulpus-pro-max/blob/dev/sw/docs/dependency_installation.md).
5. Install compatible ESP32 and MSP430 packages using the
   [firmware update guide](firmware_update_guide.md).
6. Connect the intended transducer, begin with conservative excitation and
   acquisition settings, and follow the [operating modes guide](operating_modes.md).

!!! warning "High voltage and research hardware"
    The Acquisition PCB generates high voltages for ultrasound excitation and
    transducer biasing. Verify assembly, connector orientation, supply rails,
    and transducer compatibility before enabling the transmit path. The
    platform is research hardware and is not a certified medical device.

## Before the first experiment

- Confirm that the Acquisition PCB and WiFi host PCB revisions match the
  documentation.
- Inspect solder joints, component orientation, connectors, and board-to-board
  alignment.
- Use USB power for initial setup and firmware installation.
- Verify the reported ESP32 and MSP430 firmware versions in the desktop
  application.
- Test communication and acquisition before attaching a battery.
- Confirm transducer pinout, maximum excitation voltage, frequency range, and
  any required biasing.
- For portable use, follow the battery polarity, wake-up, charging, and power
  guidance in the [operating modes guide](operating_modes.md).

