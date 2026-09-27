# ESP-IDF toolchain setup guide

This firmware is developed and tested with **ESP-IDF 6.0.1** targeting
ESP32-C6. Use the same version when reproducing builds unless a later version
has been explicitly validated by the project.

## Contents

- [Recommended installation with EIM](#recommended-installation-with-eim)
- [VS Code setup](#vs-code-setup)
- [Manual Git installation](#manual-git-installation)
- [Verify the installation](#verify-the-installation)
- [Configure this project](#configure-this-project)
- [Flashing and USB ownership](#flashing-and-usb-ownership)
- [Common problems](#common-problems)

ESP-IDF is more than a compiler. A complete installation includes:

- the ESP-IDF framework and build scripts;
- the RISC-V compiler and debugger for ESP32-C6;
- CMake and Ninja;
- Python and an ESP-IDF-managed Python environment;
- flashing tools such as esptool; and
- optional OpenOCD tools for JTAG debugging.

The recommended installer for ESP-IDF 6.0 and newer is Espressif's ESP-IDF
Installation Manager (EIM). See the official ESP32-C6
[ESP-IDF 6.0.1 Get Started guide](https://docs.espressif.com/projects/esp-idf/en/v6.0.1/esp32c6/get-started/index.html).

## Recommended installation with EIM

Install **ESP-IDF v6.0.1**, not merely whichever release is currently marked
latest. In the EIM graphical interface, use a custom/expert installation when
necessary to select version 6.0.1 and ESP32-C6 support.

The EIM command-line equivalent is:

```text
eim install -i v6.0.1
```

If the command is unavailable or version selection needs interaction, run:

```text
eim wizard
```

### Windows

Install the EIM GUI with Windows Package Manager:

```powershell
winget install Espressif.EIM
```

Alternatively, install the CLI-only package:

```powershell
winget install Espressif.EIM-CLI
```

Open EIM and install ESP-IDF 6.0.1 with ESP32-C6 tools. EIM checks for Git and
Python and offers to install missing prerequisites. ESP-IDF 6.0.1 requires
Python 3.10 or newer.

After installation, use the ESP-IDF terminal/environment created by EIM rather
than an ordinary PowerShell window. The activated terminal supplies `IDF_PATH`,
the ESP-IDF Python environment, CMake, Ninja, the RISC-V toolchain, and
`idf.py`.

Official instructions:
[Installation on Windows](https://docs.espressif.com/projects/esp-idf/en/v6.0.1/esp32c6/get-started/windows-setup.html).

### Linux

On Debian/Ubuntu, EIM can be installed from Espressif's APT repository:

```bash
echo "deb [trusted=yes] https://dl.espressif.com/dl/eim/apt/ stable main" \
  | sudo tee /etc/apt/sources.list.d/espressif.list
sudo apt update
sudo apt install eim
```

Use `eim-cli` instead of `eim` for a CLI-only installation. RPM-based systems
can use Espressif's DNF repository described in the official guide.

Then install ESP-IDF 6.0.1:

```bash
eim install -i v6.0.1
```

Official instructions:
[Installation on Linux](https://docs.espressif.com/projects/esp-idf/en/v6.0.1/esp32c6/get-started/linux-setup.html).

### macOS

Install the prerequisites and EIM with Homebrew:

```bash
brew install libgcrypt glib pixman sdl2 libslirp dfu-util cmake python
brew tap espressif/eim
brew install --cask eim-gui
```

For a CLI-only EIM installation, use:

```bash
brew install eim
eim install -i v6.0.1
```

Official instructions:
[Installation on macOS](https://docs.espressif.com/projects/esp-idf/en/v6.0.1/esp32c6/get-started/macos-setup.html).

## VS Code setup

1. Install Visual Studio Code.
2. Install the official **Espressif IDF** extension.
3. Open the Command Palette.
4. Run **ESP-IDF: Open ESP-IDF Installation Manager** if ESP-IDF is not yet
   installed.
5. Run **ESP-IDF: Select Current ESP-IDF Version** and select the 6.0.1 setup.
6. Open this `fw/esp32` directory as the project folder.
7. Run **ESP-IDF: Doctor Command** if the extension does not find the toolchain
   or connected board.

The extension stores the selected ESP-IDF setup for the workspace and configures
the required environment variables. Do not mix a workspace-selected EIM setup
with stale manually configured `IDF_PATH`, `IDF_TOOLS_PATH`, or
`IDF_PYTHON_ENV_PATH` values.

Official instructions:
[Install ESP-IDF and tools in VS Code](https://docs.espressif.com/projects/vscode-esp-idf-extension/en/latest/installation.html).

## Manual Git installation

Use this path for CI or when EIM cannot be used. On Linux/macOS:

```bash
mkdir -p ~/esp
cd ~/esp
git clone --recursive --branch v6.0.1 \
  https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32c6
. ./export.sh
```

The environment activation applies only to the current shell. Run:

```bash
. ~/esp/esp-idf/export.sh
```

in each new terminal before invoking `idf.py`. The ESP-IDF repository must be
cloned recursively because the framework uses Git submodules.

For Windows, EIM is strongly preferred because it installs and coordinates the
required compiler, Python environment, build tools, and shell shortcuts.

## Verify the installation

Open an activated ESP-IDF shell and run:

```text
idf.py --version
python --version
cmake --version
ninja --version
riscv32-esp-elf-gcc --version
```

The first command should report ESP-IDF v6.0.1. Python must be at least 3.10.
The remaining commands must resolve without manually adding individual tool
directories to `PATH`.

On Windows, also confirm that the board appears in Device Manager when connected
with a data-capable USB cable. Note the assigned COM port for flashing.

## Configure this project

From an activated ESP-IDF shell, change to this directory:

```text
cd path/to/wulpus-pro/fw/esp32
```

Then follow the board-specific commands in the
[development guide](development_guide.md). The WULPUS Pro Max WiFi host PCB is
the primary host board and uses the XIAO ESP32-C6 configuration.

The first configure/build may download managed ESP-IDF components declared by
the project. Internet access is therefore normally required even after the base
toolchain is installed, unless the component cache has already been populated.

## Flashing and USB ownership

Build and flash with the board-specific build directory described in the
[development guide](development_guide.md). For example:

```powershell
idf.py -B build-xiao build
idf.py -B build-xiao -p COM10 flash
```

For distribution as one complete ESP32 image, run
`idf.py -B build-xiao merge-bin` and flash `build-xiao/merged-binary.bin` at
`0x0`. An application-only `.bin` is insufficient for a fresh board. The current
partition table also adds the required 256 KiB MSP430 image staging partition;
flash the updated table when upgrading an older installation.

MSP430 firmware is built separately with CCS and uploaded through the
[firmware update workflow](../../../docs/firmware_update_guide.md). Its TI-TXT
file is not an ESP32 image and must not be passed to the ESP32 flasher.

Replace `COM10` with the actual ESP32-C6 port. Close the Python GUI, Tera Term,
ESP-IDF monitor, and any other serial application before flashing; only one
process can own the CDC COM port on Windows.

Do not leave `idf.py monitor` running during normal WULPUS USB acquisition. The
production configuration reserves native USB CDC for binary PC protocol data
and disables the application console.

## Common problems

- **`idf.py` is not recognized:** the terminal is not running the activated
  ESP-IDF environment. Reopen the EIM/ESP-IDF shell or source `export.sh`.
- **Wrong ESP-IDF version:** select/install v6.0.1 and verify with
  `idf.py --version` before reconfiguring.
- **CMake or compiler not found:** do not install random versions into the
  project environment; repair/select the EIM setup so its managed tools are
  used together.
- **COM port cannot be opened:** close the GUI, terminal, monitor, or another
  flashing process that owns it.
- **JTAG flash says OpenOCD is not running:** start an ESP-IDF JTAG debug/flash
  configuration, or use serial flashing with `idf.py -p COMx flash`.
