# WULPUS Pro Max desktop GUI

This directory contains the standalone PySide6 application. It uses the same
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

The **Ultrasound Configuration** tab separates acquisition, excitation, TX/RX
channel, and advanced timing settings. The acquisition view shows the measurement
period and HV supply ON interval. It also shows the invalid case where the HV
supply ON time is not earlier than the next acquisition-sequencer trigger. The
disable marker follows sequencer completion, estimated from ADC sampling start,
sample count, and sampling frequency. The firmware-fixed sample count remains
visible but disabled, while the reserved capture-restart parameter is hidden.
RX gain, VGA precharge, and VGA gain-slope controls follow the duty-cycle view
as a separate gain section with a live fixed/time-varying receive-gain profile.
The TX/RX tab keeps configuration count, add/edit/remove, and TX/RX file
load/save controls together in a toolbar above the channel-configuration cards.
The TX/RX editor presents each channel bank as two rows of eight, with separate
TX and RX groups and additional vertical spacing between them.
The advanced view shows the ADC, PGA, pulser, HV-MUX, and capture events on a
detailed microsecond axis.
The excitation view renders the configured unipolar pulse train and reports
its frequency, period, 50% high time, pulse count, and total burst duration.

For maximum acquisition throughput choose **Off** in the Display selector.
Frames, gap counters, progress, and optional NPZ capture continue without plot
filtering or rendering. The acquisition display's band-pass filter uses a
dual-handle frequency slider with synchronized low- and high-cutoff fields.

The **Data Viewer** tab opens notebook-compatible acquisition files containing
`data_arr`, `acq_num_arr`, and `tx_rx_id_arr`. It can filter frames by TX/RX
configuration, navigate or replay acquisitions, and overlay raw, band-pass
filtered, and envelope signals.

Use **Debug → Enable debug logging…** to capture detailed GUI, transport, and
session messages. Records are queued in memory and written to the selected log
file in batches by a background thread to avoid acquisition-path file I/O.

## Build

From the repository root, install the locked environment and build:

```powershell
uv sync --locked --project sw --group desktop --group flash --group dev
uv run --locked --project sw --group desktop --group flash python scripts/build_desktop_gui.py --clean
```

The portable `onedir` result is written to `sw/dist/WULPUS-Pro-Max`. Run the
build separately on Windows, Linux, and macOS; PyInstaller does not
cross-compile. Linux users need permission to access the relevant serial
devices. Code signing and macOS notarization are release/deployment steps and
are not performed by this build. The root build script also produces a
platform-specific ZIP and a SHA-256 checksum beside the portable directory.
Use `--output-dir` to select another destination.

## Development and architecture

See [the developer guide](../docs/desktop_gui_development.md) for module ownership,
threading rules, file contracts, logging, packaging, and release checks.

`main.py` only parses launch options and starts Qt. `window.py` composes the
tabs and manages application-wide theme, logging, and connection state.
Each panel lives in its own module: `connection`, `configuration`, `acquisition`,
`data_viewer`, `device_config`, `service`, and `firmware`. `txrx.py` contains
reusable channel widgets; `style.py` owns visual policy.

Keep hardware operations in `controller.py` and protocol modules, independent
of Qt widgets. `workers.py` adapts blocking operations to Qt threads;
`async_ui.py` retains tasks until their queued callbacks are delivered.
Add a new panel by composing it in `window.py`, and expose transport-specific
features through `TransportCapabilities` in `models.py`.

Use four-space indentation, 88-column formatting, sorted imports, and the
pinned Ruff rules in `sw/pyproject.toml`. Avoid semicolon-packed statements.
Comments should explain protocol invariants, thread ownership, and unusual
constraints rather than restating code. Format/check from the repository root:

```powershell
uv run --locked --project sw --group dev python scripts/format_desktop_gui.py
uv run --locked --project sw --group dev python scripts/format_desktop_gui.py --check
```

Run tests from `sw`:

```powershell
uv run --locked --group desktop --group flash python -m unittest discover -s desktop_gui/tests -v
```

Tests cover controller behavior, file compatibility, log overflow/shutdown,
and offline Qt window/acquisition integration. Real-device USB/Wi-Fi/BLE,
firmware updates, and operating-system packaging still require release checks
on each supported platform.
