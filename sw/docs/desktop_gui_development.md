# Desktop GUI developer guide

The desktop application uses PySide6 for widgets, PyQtGraph for plots, and the
existing `wulpus` transport/protocol modules. Start at `desktop_gui/main.py`;
application composition lives in `desktop_gui/window.py`.

## Environment and commands

From the repository root:

```powershell
uv sync --locked --project sw --group desktop --group flash --group dev
uv run --locked --project sw --group dev python scripts/format_desktop_gui.py
uv run --locked --project sw --group dev python scripts/format_desktop_gui.py --check
```

Run and test from `sw` so Python can resolve the local packages:

```powershell
uv run --locked --group desktop --group flash python -m desktop_gui.main --simulator
uv run --locked --group desktop --group flash python -m unittest discover -s desktop_gui/tests -v
```

The simulator is an explicit development option. It does not open hardware.
Normal launches expose USB CDC, Wi-Fi, and BLE transports.

## Module map

| Module | Responsibility |
| --- | --- |
| `main`, `entrypoint` | CLI/Qt startup and frozen application entry |
| `window` | Compose tabs, connect signals, theme/logging lifecycle |
| `controller` | Exclusive device session, capability checks, capture and cleanup |
| `models` | Capabilities, result objects, configuration and NPZ compatibility |
| `workers`, `async_ui` | Blocking-operation adapters and task lifetime |
| `connection` | Discovery and connect/disconnect controls |
| `configuration`, `txrx` | Parameter editing and channel-mask cards/dialogs |
| `acquisition` | Live previews, capture controls, queued recovery |
| `data_viewer` | Offline NPZ navigation, processing, and replay |
| `device_config`, `service`, `firmware` | Provisioning, diagnostics, updates |
| `style` | Shared widget sizing and Qt/plot themes |
| `debug_log` | Bounded log queue and background batch writer |

Add a panel by creating a focused QWidget module and composing it in `window`.
Keep protocol I/O in the controller/transport layer. Declare new transport
features in `TransportCapabilities`; widgets should use these flags to determine
availability. Avoid importing `window` from panels, which introduces cycles.

## Threading and lifecycle

Only the GUI thread may modify widgets. `AsyncMixin.run_task()` retains each
pool task until queued callbacks are delivered. Use it for short blocking
operations and handle results in GUI callbacks.

Acquisition uses a dedicated QThread and `AcquisitionWorker`. The controller
records every received frame; display notifications are throttled separately.
`stop()` is cooperative: the current receive call and cleanup must finish.
Reset/reboot requested during capture waits for that release before using the
same transport. Do not issue concurrent protocol reads on a connected link.

Window closure is deferred while short tasks are active. Shutdown requests
capture cancellation, stops replay, closes an idle session, and drains logging.
Reset recovery still depends on transport timeouts; it cannot interrupt an
indefinitely blocked driver call.

## Data and visualization contracts

- NPZ uses `data_arr` shaped `(samples, frames)`, plus one-dimensional
  `acq_num_arr` and `tx_rx_id_arr` of matching frame length. Loading disables
  pickle. Legacy files do not carry sampling frequency; the viewer user supplies it.
- Legacy TX/RX JSON uses `configs`, with contiguous `config_id` values beginning
  at zero, channel lists, and `optimized_switching`. Pro Max uses direct
  channel-to-bit mapping for channels 0–15; switching optimization is not used.
- A-mode has a continuous ADC-amplitude Y axis. B-mode images use samples/depth
  on X and configuration rows centered at integer IDs on Y.
- Replay freezes the plot range until playback stops. Filtering and envelope
  generation affect display, not saved raw samples.

## Logging

Enable logging through **Debug → Enable debug logging…**. Normal log producers
enqueue formatted records; one writer flushes approximately once per second.
The queue holds up to 10,000 records and reports overflow rather than blocking
acquisition. Disabling logging drains accepted records with a bounded shutdown
wait. Files are appended, so choose a fresh name for an independent session.

Use `logging.getLogger(__name__)` and `SessionController.log()` for lifecycle
events. Avoid per-sample messages and never log credentials or raw firmware
payloads. The handler captures Python logging records, not arbitrary stdout or
device UART text. Runtime disk errors are retained and reported when logging
is disabled; a stuck filesystem can exceed the shutdown wait.

## Style and verification

Ruff is pinned in the lockfile. Use four-space indentation, 88-column formatting,
sorted imports, and one statement per line. Public classes and nontrivial public
methods should have docstrings describing purpose, ownership, side effects,
units/shapes, or errors where relevant. Comments explain invariants and reasons.

The desktop CI workflow checks formatting and runs offline tests on Windows.
Add tests for protocol/state transitions, file validation, and cancellation or
shutdown changes. Qt tests use the offscreen backend and synthetic transports.

## Distributables

From the repository root:

```powershell
uv run --locked --project sw --group desktop --group flash python scripts/build_desktop_gui.py --clean
```

This produces `sw/dist/WULPUS-Pro-Max/`, a platform/architecture ZIP, and a
`.zip.sha256` checksum. Distribute the whole folder or ZIP, not only the executable.
`--output-dir PATH` selects another destination. `--console` includes a console
for diagnosing packaged startup failures; omit it for the regular GUI build.
The old `desktop_gui/build.py` command delegates to this script.

Run the packaged executable with `--smoke-test` to construct the GUI using only
the simulator, process Qt events for one second, and exit. This verifies startup
without opening a hardware connection. A console build can expose import errors.

PyInstaller builds for the host OS. Linux/macOS packages must be built and tested
on those systems. Before release, verify packaged startup on a clean machine,
USB/Wi-Fi/BLE operation, capture files, recovery after a stalled connection, and
both firmware update workflows. Signing/notarization and hardware qualification
are separate release steps; offline tests alone do not establish production readiness.
