# Development scripts

This directory contains maintainer and firmware-development utilities. Run all
commands from the repository root.

## Prerequisites

Follow the authoritative setup and build instructions before using these
scripts:

- [Python software setup](../sw/docs/dependency_installation.md)
- [ESP32 firmware development](../fw/esp32/docs/development_guide.md)
- [MSP430 firmware development](../fw/msp430/README.md#build-and-export-firmware)

The packaging scripts do not compile firmware. They validate and package the
outputs produced by these toolchains.

## Desktop GUI formatting and tests

Check the desktop GUI and its maintainer scripts with the pinned Ruff version:

```powershell
uv run --locked --project sw python scripts/format_desktop_gui.py --check
```

Apply safe lint fixes and formatting in place:

```powershell
uv run --locked --project sw python scripts/format_desktop_gui.py
```

Run the desktop unit and offline GUI integration tests from the software
package directory:

```powershell
cd sw
$env:QT_QPA_PLATFORM = "offscreen"
uv run --locked --group desktop --group flash python -m unittest discover `
  -s desktop_gui/tests -v
cd ..
```

The GUI integration test uses the simulator and does not connect to hardware.
Physical USB, Wi-Fi, firmware-update, reboot, and reset behavior must still be
validated on supported hardware before a release.

## Desktop GUI distributable

Build the native windowed application on the target operating system:

```powershell
uv run --locked --project sw --group desktop --group flash `
  python scripts/build_desktop_gui.py --clean
```

On Windows, the build writes the onedir application, portable ZIP, and ZIP
checksum under `sw/dist/`:

```text
sw/dist/
|-- WULPUS-Pro-Max/
|-- WULPUS-Pro-Max-windows-amd64.zip
`-- WULPUS-Pro-Max-windows-amd64.zip.sha256
```

Use `--output-dir PATH` to select another artifact directory. Add `--console`
for a diagnostic build that keeps a console window for startup errors. The
console option is intended for troubleshooting, not normal release packages.

Build a single self-extracting executable with:

```powershell
uv run --locked --project sw --group desktop --group flash `
  python scripts/build_desktop_gui.py --clean --onefile
```

This writes a versioned executable such as
`sw/dist/WULPUS-Pro-Max-x.x.x.exe`, using the version from
`sw/pyproject.toml`. It extracts its bundled runtime to a temporary directory
when launched, so it starts more slowly than the portable directory build.

For a release, build the one-file executable, generate its checksum, and place
both files under `releases/` with:

```powershell
uv run --locked --project sw --group desktop --group flash `
  python scripts/package_desktop_gui_release.py
```

The script performs a clean build and writes:

```text
releases/
|-- WULPUS-Pro-Max-x.x.x.exe
`-- WULPUS-Pro-Max-x.x.x.exe.sha256
```

The version comes from `sw/pyproject.toml`. Use `--output-dir PATH` to place
both files in another directory.

After a portable-directory build, run the packaged offline startup check:

```powershell
sw\dist\WULPUS-Pro-Max\WULPUS-Pro-Max.exe --smoke-test
```

The smoke-test mode constructs the full interface, processes queued Qt events,
performs normal resource cleanup, and exits without opening a hardware link.

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
`wulpus/firmware_version.h` and the MSP430 changelog. It also locates the TI
MSP430 21.6.0.LTS compiler used by the project and packages its original RTS
manifest and SPDX inventory with the DriverLib license. It creates the ignored
`releases/` directory when needed and writes two files:

```text
releases/
|-- wulpus-pro-max-msp430-<version>.zip
`-- wulpus-pro-max-msp430-<version>.zip.sha256
```

The ZIP contains the validated `.mspfw` image consumed by the ESP32 updater,
`SHA256SUMS.txt`, the project license, `THIRD_PARTY_NOTICES.txt`, and original
TI compliance files under `LICENSES/`. The adjacent `.sha256` file verifies the
complete release ZIP.

If more than one TI-TXT build exists, select it explicitly:

```powershell
uv run --project sw python scripts/package_msp430_release.py `
  --input path\to\wulpus_pro_msp430_firmware.txt
```

Use `--search-dir PATH` to change automatic discovery or `--output-dir PATH`
to place both generated files elsewhere. If the compiler is not in a standard
CCS installation directory, pass `--ti-compiler-dir PATH` or set
`TI_MSP430_CGT_DIR` to `ti-cgt-msp430_21.6.0.LTS`.

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
[firmware-update instructions](../docs/firmware_update_guide.md).
