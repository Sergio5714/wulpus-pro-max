# Jupyter notebook compatibility

The desktop application is the primary user interface. Two notebooks remain in
the `sw` root for compatibility with existing workflows.

## Start Jupyter

Install the standard dependencies as described in the
[dependency installation guide](dependency_installation.md). From `sw`, run:

```powershell
uv run jupyter notebook
```

## Acquisition and configuration notebook

Open [`wulpus_pro_example.ipynb`](../wulpus_pro_example.ipynb) to:

- connect through USB CDC, Wi-Fi, or the BLE dongle;
- configure ultrasound acquisition and TX/RX channels;
- acquire and save RF frames;
- inspect NPZ data interactively;
- access lower-level Python objects for development and diagnostics.

Only one notebook kernel or application can own a USB serial port or active
device session. Disconnect the desktop GUI before connecting from the notebook.

## Firmware-update notebook

Open
[`wulpus_pro_firmware_update.ipynb`](../wulpus_pro_firmware_update.ipynb) for
ESP32 and MSP430 firmware updates. Install the `flash` dependency group first:

```powershell
uv sync --group flash
```

Follow the [firmware flashing guide](firmware_flashing.md) for package and
recovery requirements.

## About the notebooks

The notebooks use the same device communication and file formats as the desktop
application. They are retained for compatibility with existing workflows.
