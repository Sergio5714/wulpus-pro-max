# WULPUS Pro Max desktop GUI

This directory contains the standalone PySide6 prototype. It uses the same
transport, configuration, acquisition-file, diagnostics, and firmware-package
APIs as the supported notebooks.

## Run

From `sw`:

```powershell
uv sync --group desktop --group flash
uv run --group desktop --group flash python -m desktop_gui.main
```

Pass `--simulator` to expose the development-only simulator transport. It is
not shown during a normal launch.

The application supports one active device at a time. USB CDC, Wi-Fi, and BLE
are available for acquisition; controls that require newer ESP32 commands are
enabled only for transports that implement them. Persistent configuration and
Wi-Fi provisioning intentionally require USB CDC.

For maximum acquisition throughput choose **Off** in the Display selector.
Frames, gap counters, progress, and optional NPZ capture continue without plot
filtering or rendering.

The **Data Viewer** tab opens notebook-compatible acquisition files containing
`data_arr`, `acq_num_arr`, and `tx_rx_id_arr`. It can filter frames by TX/RX
configuration, navigate or replay acquisitions, and overlay raw, band-pass
filtered, and envelope signals.

Use **Debug → Enable debug logging…** to capture detailed GUI, transport, and
session messages. Records are queued in memory and written to the selected log
file in batches by a background thread to avoid acquisition-path file I/O.

## Build

Install the desktop and flash groups, then run:

```powershell
uv run --group desktop --group flash python desktop_gui/build.py --clean
```

The portable `onedir` result is written to `sw/dist/WULPUS-Pro-Max`. Run the
build separately on Windows, Linux, and macOS; PyInstaller does not
cross-compile. Linux users need permission to access the relevant serial
devices. Code signing and macOS notarization are release/deployment steps and
are not performed by this prototype build.
