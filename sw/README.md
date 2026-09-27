# WULPUS Pro Max software
This directory contains the WULPUS Pro Max Python API, graphical user interface components, Wi-Fi and serial transports, and example Jupyter notebooks.

`wulpus_pro_example.ipynb` is the supported main notebook for USB CDC, Wi-Fi,
and BLE operation. Older specialized notebooks are retained for reference in
`legacy/` and are not part of the current workflow.

The supported configuration implementation is the WULPUS Pro Max stack:

- `wulpus/rx_tx_conf_pro.py`: 16-channel TX/RX mask generation
- `wulpus/uss_conf_pro.py`: acquisition configuration and packet encoding
- `wulpus/config_package_pro.py`: configuration field definitions
- `wulpus/uss_conf_gui_pro.py`: configuration widgets
- `wulpus/gui.py`: transport-independent acquisition and visualization GUI
- `wulpus/wifi_link.py`: robust TCP transport and acquisition lifecycle
- `wulpus/wifi_discovery.py`: mDNS discovery
- `wulpus/usb_cdc_link.py`: native ESP32-C6 USB CDC transport
- `wulpus/ble_dongle.py`: legacy BLE-dongle serial transport
- `wulpus/device_config_gui.py`: persistent ESP32 configuration over USB CDC
- `wulpus/esp32_update.py`: validated ESP32-C6 release packages and flashing
  through uv-managed esptool
- `wulpus/msp430_update.py`: TI-TXT packaging, MSP430 upload, status,
  diagnostics, and update widgets over USB CDC or Wi-Fi
- `wulpus/npz_viewer.py`: interactive acquisition-file inspection and signal processing

`WulpusGuiSingleCh` depends on the `WulpusProCommunicationLink` protocol rather than a concrete transport, so it can operate with `WulpusBleDongle`, `WulpusProWiFiLink`, or `WulpusProUsbCdcLink`.

The ESP32 device-configuration section in `wulpus_pro_example.ipynb` uses
`WulpusProDeviceConfigGUI` to load and replace non-secret configuration over
USB CDC, set or clear write-only Wi-Fi credentials, and reboot to apply changes.
The GUI never reads stored SSIDs or passwords.

## Firmware updates

Use [`wulpus_pro_firmware_update.ipynb`](wulpus_pro_firmware_update.ipynb) to
flash a packaged ESP32-C6 release without installing ESP-IDF. Install the
flashing dependency with `uv sync --group flash`, close every client using the
COM port, and select the release ZIP in the ESP32 panel.

The same notebook retains the separate MSP430 updater. Select the released
MSP430 ZIP; the GUI verifies its firmware checksum and container before upload.
TI-TXT and standalone `.mspfw` files remain available for development. Click
**Upload and program**. Commit reboots the ESP32; programming happens before
normal connectivity returns. **Check status** retrieves the persisted result.
`COMPLETE` confirms programming/verification, not application health. Wiring,
partition requirements, Wi-Fi API usage, and recovery are documented in the
[firmware update guide](../docs/firmware_update_guide.md).

## Interactive NPZ viewer

Use `WulpusProNpzViewer` in Jupyter to inspect files saved by either the GUI or
the USB profiler. Select a local `.npz` using the upload control, filter frames
by TX/RX configuration, and move through matching acquisitions with the slider.
Raw, GUI-equivalent band-pass-filtered, and Hilbert-envelope traces can be
shown independently. Set the sampling-frequency control to the value used for
the acquisition because the legacy NPZ format does not store it. Set the
acquisition slider to any filtered frame and press **Replay** to advance from
that position at the selected FPS; replay ends at the final matching frame or
when **Stop** is pressed. The Y-axis range is locked when replay starts so
amplitude changes do not rescale the plot during playback:

```python
%matplotlib widget
from wulpus.npz_viewer import WulpusProNpzViewer

viewer = WulpusProNpzViewer()
viewer
```

Files on the Jupyter server can also be opened directly:

```python
viewer = WulpusProNpzViewer("data_0.npz")
viewer
```

## USB CDC operation

Select **USB CDC** in the example GUI when the XIAO ESP32-C6 is connected
directly to the PC. The link scans for the Espressif USB Serial/JTAG CDC port
and runs the same WULPUS command and RF-frame protocol used by Wi-Fi.

Only one application can own the COM port. Before flashing or opening IDF
Monitor, stop acquisition and close the device in the GUI. Flash normally with:

```powershell
idf.py -p COM9 flash
```

Replace `COM9` with the detected port. Reopen it in the GUI after the ESP32
restarts. JTAG is a separate interface of the ESP32-C6 composite USB device and
remains available, although halting the CPU interrupts live acquisition.

### USB frame-rate profiling

Close the GUI and all serial monitors, then run the standalone profiler with
explicit acquisition periods. TX is disabled by default, so this exercises the
capture and USB transport without firing the pulser:

```powershell
uv run python profile_usb_fps.py --port COM9 --period-us 10000 5000 2000 --frames 500
```

The profiler reports target and measured FPS, 95th-percentile frame latency,
timeouts, and acquisition-number gaps. The fastest passing period is the
maximum stable rate among the values tested. The `simplified` preset disables
TX/RX masks and uses a +1 ms DC-DC margin. The `active-all` preset selects all
channels and fixes DC-DC turn-on at 100 us. Custom and saved configurations use
their explicitly selected timing and masks. Enabling TX requires an
independently verified safe pulse-repetition rate for the connected hardware
and transducer.

To reproduce a configuration saved by the acquisition GUI, pass its JSON file.
The saved measurement period is used when `--period-us` is omitted:

```powershell
uv run python profile_usb_fps.py --port COM10 --config uss_config_pro.json --frames 2000
```

Add `--output acquisition.npz` to save the measured frames in the same format
as the GUI, with the `data_arr`, `acq_num_arr`, and `tx_rx_id_arr` arrays. Warmup
frames are not saved. When profiling multiple periods, the profiler appends the
period to each filename, for example `acquisition_2000us.npz`.

Specify `--period-us` to override only the saved period for a rate sweep. New
GUI configuration files include TX/RX mask arrays. Legacy files without masks
remain compatible and use one zero-mask TX/RX configuration unless masks or a
profiler mode are supplied explicitly.

### Runtime status

The TCP and USB CDC links expose the same ESP32 diagnostic API:

```python
status = link.get_status()
print(hex(status.error_flags), status.current_buffer_usage)

# Clear all sticky errors while preserving lifetime counters.
link.clear_status()

# Clear sticky errors and reset diagnostic counters.
link.clear_status(clear_counters=True)
```

The status snapshot includes acquisition-buffer overflow, SPI and link errors,
DATA_READY/SPI/transmitted-frame counters, discarded frames, and current and
maximum DMA-buffer occupancy.

# How to get started?

Install dependencies with `uv` and launch Jupyter from this folder:

```bash
uv sync
uv run jupyter notebook
```

In the Jupyter browser, open `wulpus_pro_example.ipynb`. It is the main
supported workflow for USB CDC, Wi-Fi, and BLE operation.

For more details, see `sw/how_to_install_dependencies.md`.

## Wi-Fi example on Windows

The `wulpus_pro_example.ipynb` notebook discovers the ESP32 through the
`_wulpus_pro._tcp.local.` mDNS service and communicates with it over TCP port 2121.
The computer and WULPUS Pro Max must be connected to the same local network.

Windows may block mDNS or the TCP connection when the network profile is
**Public**. On a trusted network, either change its profile to **Private**, or
open PowerShell as Administrator and add narrowly scoped rules for the Python
interpreter used by this project's virtual environment:

```powershell
# Run from the repository's sw directory.
$pythonPath = (Resolve-Path ".\.venv\Scripts\python.exe").Path

New-NetFirewallRule `
    -DisplayName "WULPUS Pro Max mDNS discovery" `
    -Direction Inbound `
    -Action Allow `
    -Program $pythonPath `
    -Protocol UDP `
    -LocalPort 5353 `
    -RemoteAddress LocalSubnet `
    -Profile Public

New-NetFirewallRule `
    -DisplayName "WULPUS Pro Max TCP communication" `
    -Direction Outbound `
    -Action Allow `
    -Program $pythonPath `
    -Protocol TCP `
    -RemotePort 2121 `
    -RemoteAddress LocalSubnet `
    -Profile Public
```

The active notebook interpreter can be checked with:

```python
import sys
print(sys.executable)
```

After changing the network profile or firewall rules, restart the notebook
kernel and reset the ESP32. If multicast service discovery remains unavailable,
`WulpusProWiFiLink.get_available()` also attempts to resolve `wulpus_pro.local`.
The ESP32 IP address can additionally be supplied manually using
`WulpusProWiFiDevice` as shown in the example notebook.

To remove the firewall rules later:

```powershell
Remove-NetFirewallRule -DisplayName "WULPUS Pro Max mDNS discovery"
Remove-NetFirewallRule -DisplayName "WULPUS Pro Max TCP communication"
```

# License
The source files are released under Apache v2.0 (`Apache-2.0`) license unless noted otherwise, please refer to the `sw/LICENSE` file for details.
