# WULPUS Pro Max PCB design files

This directory contains the PCB designs used by WULPUS Pro Max. The source files are
provided in Altium Designer or KiCad format, depending on the board. Where
available, each project also includes PDF schematics and assembly drawings under
`docs`, and production-ready files under `fabrication_outputs`, including bills
of materials, Gerber files, NC drill files, and pick-and-place files.

## Included PCB designs

### WULPUS PRO Acquisition PCB

Directory: [`wulpus_pro_acq_pcb_dev_board`](wulpus_pro_acq_pcb_dev_board)

The WULPUS PRO Acquisition PCB is the platform's ultrasound acquisition and
pulser board. It contains
the transmit and receive signal paths, high-voltage switching, power supplies,
MSP430 control circuitry, and the host interface. The design sources are provided
in Altium Designer format. This board is required to build a WULPUS Pro Max
system.

### WULPUS Pro Max WiFi host PCB

Directory: [`wulpus_wifi_host_pcb`](wulpus_wifi_host_pcb)

An open-source companion board that integrates wireless communication, power
delivery, and firmware programming for the WULPUS PRO Acquisition PCB. Based
on the [Seeed Studio XIAO ESP32-C6](https://www.seeedstudio.com/Seeed-Studio-XIAO-ESP32C6-p-5884.html),
it supports runtime acquisition configuration and real-time ultrasound data
streaming over Wi-Fi/TCP or native USB CDC at pulse repetition frequencies
(PRFs) of up to 500 Hz. It is the primary host board for WULPUS Pro Max and runs
the [ESP32 firmware](../fw/esp32).

A single USB-C connection powers the complete system and enables wired
communication and firmware updates, including [programming the acquisition
board's MSP430 through integrated JTAG](../docs/firmware_update_guide.md).
The host supports Wi-Fi provisioning, automatic reconnection, and device
discovery. The platform can also be powered by an external Adafruit battery
with a standard JST connector. USB battery charging is supported, and battery
protection is integrated.

The design sources are provided in KiCad format, together with fabrication and
assembly outputs.

Using the XIAO module provides a stable, actively supported wireless platform
with a proven RF design. Seeed publishes compliance records for the
module, including [FCC Part 15](https://files.seeedstudio.com/Seeed_Certificate/documents_certificate/113991254-FCC.pdf)
and [CE RED](https://files.seeedstudio.com/Seeed_Certificate/documents_certificate/113991254-CE.pdf)
testing. This pre-tested module significantly reduces RF design effort and
compliance risk compared with developing a custom, uncertified RF implementation.

### polyCMUT adapter board

Directory: [`wulpus_polycmut_adapter`](wulpus_polycmut_adapter)

An optional research adapter for connecting polyCMUT transducers to WULPUS. The
design sources are provided in Altium Designer format. This board is not required
for standard WULPUS Pro Max operation.

## Internal KiCad library

The [`kicad_us_lib`](kicad_us_lib) directory is referenced as a Git submodule and
contains the internal KiCad symbols, footprints, and related library assets used
to develop the hardware designs. It is hosted in a private repository and is
intended only for internal development; external users will not have access to
it. The library could not be made publicly open source because some of its
contents are subject to third-party licensing restrictions.

The released KiCad projects embed the symbols and footprints used by each
design. External users are advised to generate their own project-specific symbol
and footprint libraries from the corresponding project files instead of relying
on `kicad_us_lib`. The released fabrication outputs can be used without the
private submodule.

## PCBWay shared projects

For convenient one-click PCB production and assembly, you can use the PCBWay shared projects:

- [WULPUS PRO Acquisition PCB v1.0.0](https://www.pcbway.com/project/shareproject/WULPUS_PRO_Evaluation_board_v1_0_0_992d7510.html)

- [WULPUS PRO WiFi host PCB v1.0.0](https://www.pcbway.com/project/shareproject/WULPUS_PRO_WiFi_host_PCB_7cfe7806.html)

This option is convenient for outsourced PCB production and assembly, with an estimated **~1 month lead time** and a price of about **220 USD** per probe for Acquisition PCB and **40 USD** for the WiFi host PCB, based on mid-2026 pricing.

## License

All three PCB designs are released under the Solderpad Hardware License v0.51
(`SHL-0.51`). They use separate license files because their copyright holders
differ:

| PCB design | Directory | License file | Copyright |
| --- | --- | --- | --- |
| WULPUS PRO Acquisition PCB | [`wulpus_pro_acq_pcb_dev_board`](wulpus_pro_acq_pcb_dev_board) | [`LICENSE_ETH`](LICENSE_ETH) | Copyright (C) 2025 ETH Zurich. All rights reserved. |
| WULPUS polyCMUT adapter | [`wulpus_polycmut_adapter`](wulpus_polycmut_adapter) | [`LICENSE_ETH`](LICENSE_ETH) | Copyright (C) 2025 ETH Zurich. All rights reserved. |
| WULPUS Pro Max WiFi host PCB | [`wulpus_wifi_host_pcb`](wulpus_wifi_host_pcb) | [`LICENSE`](LICENSE) | Copyright (C) 2026 Sergei Vostrikov. All rights reserved. |

The license terms are otherwise identical. The internal `kicad_us_lib`
submodule contains third-party material and is not covered by this table; its
contents retain their respective license terms.
