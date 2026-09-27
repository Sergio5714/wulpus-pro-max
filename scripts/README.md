# Development scripts

This directory contains maintainer and firmware-development utilities. Run all
commands from the repository root.

## Prerequisites

Follow the authoritative setup and build instructions before using these
scripts:

- [Python software setup](../sw/README.md#how-to-get-started)
- [ESP32 firmware development](../fw/esp32/docs/development_guide.md)
- [MSP430 firmware development](../fw/msp430/README.md#build-and-export-firmware)

The packaging scripts do not compile firmware. They validate and package the
outputs produced by these toolchains.

## ESP32 formatting

Check the formatting of project-owned ESP32 C sources:

```powershell
uv run --project sw python scripts/format_esp32_fw.py --check
```

`--check` only reports formatting differences and does not create or modify any
files. Apply formatting with:

```powershell
uv run --project sw python scripts/format_esp32_fw.py --fix
```

`--fix` modifies the project-owned `.c` and `.h` files in place under
`fw/esp32/main/` and `fw/esp32/components/`. It does not generate a separate
output file. Third-party sources under
`fw/esp32/components/msp430_programmer/ti/` are excluded.

## ESP32 release package

After building the XIAO ESP32-C6 firmware in `fw/esp32/build-xiao`, create the
validated release ZIP:

```powershell
uv run --project sw python scripts/package_esp32_release.py
```

The script reads these compiled files by default:

```text
fw/esp32/build-xiao/
|-- bootloader/bootloader.bin
|-- partition_table/partition-table.bin
`-- wulpus-pro-fw.bin
```

It creates the ignored `releases/` directory when needed and writes exactly one
release artifact:

```text
releases/wulpus-pro-max-esp32-<version>.zip
```

The ZIP contains:

```text
manifest.json
bootloader.bin
partition-table.bin
wulpus-pro-fw.bin
```

`manifest.json` contains the firmware version, ESP32-C6 target, flash settings,
fixed image offsets, and a SHA-256 hash for every binary.

Use `--build-dir PATH` to read build files from a different directory or
`--output FILE.zip` to select another output path. Packaging verifies that the
version embedded in `wulpus-pro-fw.bin` matches
`fw/esp32/firmware_version.txt`.

## MSP430 release package

Build the MSP430 **Debug** configuration in Code Composer Studio, then package
the generated TI-TXT image:

```powershell
uv run --project sw python scripts/package_msp430_release.py
```

By default, the script recursively searches
`fw/msp430/wulpus_msp430_firmware/` for a TI-TXT `.txt` or `.titxt` build. A
normal CCS Debug build is found at:

```text
fw/msp430/wulpus_msp430_firmware/Debug/wulpus_pro_msp430_firmware.txt
```

The script verifies its compiled firmware version against
`wulpus/firmware_version.h` and the MSP430 changelog. It creates the ignored
`releases/` directory when needed and writes two files:

```text
releases/
|-- wulpus-pro-max-msp430-<version>.mspfw
`-- wulpus-pro-max-msp430-<version>.mspfw.sha256
```

The `.mspfw` file is the validated, section-based image consumed by the ESP32
MSP430 updater. The `.sha256` file contains its release checksum.

If more than one TI-TXT build exists, select it explicitly:

```powershell
uv run --project sw python scripts/package_msp430_release.py `
  --input path\to\wulpus_pro_msp430_firmware.txt
```

Use `--search-dir PATH` to change automatic discovery or `--output-dir PATH`
to place both generated files elsewhere.

## PCB fabrication packages

Before packaging, manually regenerate and review all fabrication outputs and
documentation from the PCB source projects. In particular, regenerate the
KiCad fabrication and documentation outputs for the WiFi host PCB. This script
does not run KiCad, Altium Designer, design-rule checks, or output jobs.

Package the Acquisition PCB and WiFi host PCB:

```powershell
uv run --project sw python scripts/package_pcb_releases.py
```

The script reads only the `fabrication_outputs/` and `docs/` directories from
the two PCB projects. It creates four ignored release artifacts:

```text
releases/
|-- wulpus-pro-max-acquisition-pcb-1.0.0.zip
|-- wulpus-pro-max-acquisition-pcb-1.0.0.zip.sha256
|-- wulpus-pro-max-wifi-host-pcb-1.0.1.zip
`-- wulpus-pro-max-wifi-host-pcb-1.0.1.zip.sha256
```

The Acquisition PCB ZIP also contains `LICENSE_ETH`. The WiFi host PCB ZIP
also contains `CHANGELOG.md` and `LICENSE`. No editable PCB source files,
backup directories, firmware, or library files are included. Use
`--acquisition-version`, `--wifi-host-version`, or `--output-dir` to override
the defaults. The WiFi host version must match its latest changelog release.

## Installing release packages

This directory only documents development and packaging utilities. For the
supported graphical ESP32 and MSP430 update workflow, follow the
[software and firmware-update instructions](../sw/README.md).
