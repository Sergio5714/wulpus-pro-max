# ESP32 firmware development guide

Install the toolchain and build from source when developing firmware or
preparing a board that does not already have firmware installed.

## Contents

- [Code formatting](#code-formatting)
- [Requirements](#requirements)
- [Supported boards](#supported-boards)
- [Install ESP-IDF](#install-esp-idf)
- [Configure, compile, and flash](#configure-compile-and-flash)
  - [Configure](#configure)
  - [Compile the firmware](#compile-the-firmware)
  - [Flash the firmware](#flash-the-firmware)
  - [Create a merged firmware image](#create-a-merged-firmware-image)
  - [Pin mapping](#pin-mapping)

## Requirements

- ESP-IDF 6.0.1
- A [supported host board](#supported-boards), listed below
- A data-capable USB-C cable
- The ESP-IDF command-line environment or official ESP-IDF VS Code extension

## Supported boards

- **[WULPUS Pro Max WiFi host PCB](../../../hw/wulpus_wifi_host_pcb)** — the primary
  and recommended XIAO ESP32-C6-based host board, compatible with the WULPUS Pro Max
  connector. It is highly integrated: it supplies power to the Acquisition PCB,
  provides Wi-Fi and USB connectivity, and supports MSP430 firmware flashing.
- **[Seeed Studio XIAO ESP32-C6](https://www.seeedstudio.com/Seeed-Studio-XIAO-ESP32C6-p-5884.html)** —
  a standalone development alternative for firmware development and bench
  testing. Connect its pins to the WULPUS PRO Acquisition PCB according to the
  [pin mapping](#pin-mapping) below. This setup does not supply the Acquisition
  PCB power rails; all required power domains must be provided by external lab
  power supplies.

Both boards use the same XIAO defaults, build commands, GPIO assignments, and
WULPUS PRO connector mapping documented below.

Run all `idf.py` commands below from `fw/esp32`. From the repository root:

```powershell
Set-Location fw/esp32
```

The commands shown use PowerShell continuation/quoting syntax. Existing
`sdkconfig.xiao` files retain saved values; compare them with the XIAO defaults
when updating.

## Install ESP-IDF

Install **ESP-IDF 6.0.1** and its ESP32-C6 toolchain before configuring the
firmware. Espressif's Installation Manager is the recommended method:

```text
eim install -i v6.0.1
```

Open an activated ESP-IDF terminal and verify:

```text
idf.py --version
```

See [ESP-IDF toolchain setup](esp_idf_toolchain_guide.md) for Windows, Linux, macOS,
VS Code, manual installation, and troubleshooting instructions.

## Configure, compile, and flash

### Configure

Configure the project with the XIAO board defaults:

```powershell
idf.py -B build-xiao `
  -D SDKCONFIG=sdkconfig.xiao `
  -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.esp32c6;boards/xiao-esp32c6.defaults" `
  reconfigure
```

Alternatively, use the official ESP-IDF VS Code extension. Set its build
directory to `build-xiao` and its SDKConfig file to `sdkconfig.xiao`, select the
board's serial port, then use the **Build** and **Flash** buttons in the VS Code
status bar instead of the commands below. See Espressif's official
[Build Your Project tutorial](https://docs.espressif.com/projects/vscode-esp-idf-extension/en/latest/buildproject.html),
which continues to the flashing instructions.

### Compile the firmware

The ESP32 application version is read from
[`firmware_version.txt`](../firmware_version.txt). Update that file with a
`major.minor.patch` release before compiling; CMake rejects other formats. The
version must match the corresponding release heading in
[`CHANGELOG.md`](../CHANGELOG.md), for example `firmware_version.txt` value
`1.1.0` matches the `## [1.1.0]` changelog entry.

```powershell
idf.py -B build-xiao build
```

The compiled application and supporting bootloader and partition-table images
are written to `build-xiao`.

### Flash the firmware

Connect the selected board to the PC with a data-capable USB-C cable. Replace
`COM10` with the port assigned by Windows:

```powershell
idf.py -B build-xiao -p COM10 flash
```

Use the full `flash` command above when upgrading older firmware so the
bootloader, partition table, and application are installed together.

### Create a merged firmware image

For a single image to distribute to a fresh ESP32, run
`idf.py -B build-xiao merge-bin` after building. Flash the resulting
`build-xiao/merged-binary.bin` at `0x0`. The application
`wulpus-pro-fw.bin` alone does not include the bootloader or partition table.

### Pin mapping

| Signal | ESP32-C6 GPIO | XIAO pin | WULPUS PRO Acquisition PCB connection |
|---|---:|---|---|
| `SPI_SS` | 17 | D7 | X3.4 |
| `SPI_CLK` | 18 | D10 | X3.3 |
| `SPI_MISO` | 20 | D9 / MISO | X3.1 |
| `SPI_MOSI` | 19 | D8 / SCK | X3.2 |
| `DATA_READY` | 1 | D1 | X4.2 |
| `MSP_RST_N` | 0 | D0 | X1.5 |

For a standalone XIAO, connect a common ground and verify the Acquisition PCB
schematic and connector pinout before powering the boards.

## Code formatting

Project-owned ESP32 C sources use clang-format, pinned in the development
dependencies of `sw/pyproject.toml` and `sw/uv.lock`. The commands below reuse
`sw/.venv`; do not create another Python environment or install a formatter
into the ESP-IDF environment. Install `uv` as described in the
[software setup](../../../sw/README.md#how-to-get-started) if needed.

From the repository root, apply formatting before submitting changes:

```powershell
uv run --locked --project sw python scripts/format_esp32_fw.py --fix
```

Check without modifying files:

```powershell
uv run --locked --project sw python scripts/format_esp32_fw.py --check
```

GitHub Actions runs the same script with `--only-group dev` on `uv run`,
installing only development tools in its temporary runner environment. Locally,
use the commands above to retain the complete software environment.

`uv run` installs locked dependencies into the existing software environment
when needed. The script invokes that environment's clang-format binary, so an
ESP-IDF formatter on PATH does not change the result. Rules are in
[`fw/esp32/.clang-format`](../.clang-format).

Scope is tracked `.c` and `.h` files under `fw/esp32/main/` and
`fw/esp32/components/`, excluding bundled TI code in
`components/msp430_programmer/ti/`. Build output, managed components, MSP430,
and nRF52 firmware are outside this scope. Stage new source files with
`git add` before running the script. If adding third-party sources under the
selected directories, update `EXCLUDED` in the script first.

A failing CI check means formatting needs attention: run `--fix`, review the
diff, and commit the formatted files. Keep broad formatting changes separate
from functional changes. Build the firmware after the initial formatting pass.
Optional editor format-on-save should use the same pinned formatter and config.
