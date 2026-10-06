# Data files and profiling

The desktop application, compatibility notebook, and USB profiler share the
same acquisition-file layout and transport APIs.

## NPZ acquisition files

An acquisition file contains:

- `data_arr`, shaped as samples by frames;
- `acq_num_arr`, containing the device acquisition number for each frame;
- `tx_rx_id_arr`, identifying the TX/RX configuration used for each frame.

Files are loaded with NumPy pickle support disabled. Legacy files do not store
their sampling frequency, so enter it explicitly when viewing or processing
those files.

The desktop **Data Viewer** supports frame filtering, navigation, replay, raw
traces, band-pass filtering, and Hilbert envelopes. The equivalent Python
viewer is available from a notebook:

```python
%matplotlib widget
from wulpus.npz_viewer import WulpusProNpzViewer

viewer = WulpusProNpzViewer("acquisition.npz")
viewer
```

## Profile USB acquisition

Close the desktop application and serial monitors before running the profiler.
TX is disabled by default:

```powershell
uv run --project sw python sw/profile_usb_fps.py --port COM9 --period-us 10000 5000 2000 --frames 500
```

The report includes target and measured frame rates, 95th-percentile frame
latency, timeouts, and acquisition-number gaps. The fastest passing period is
the maximum stable rate among the tested values.

To reproduce a configuration saved by the GUI:

```powershell
uv run --project sw python sw/profile_usb_fps.py --port COM10 --config uss_config_pro.json --frames 2000
```

Add `--output acquisition.npz` to save frames in the shared NPZ format. When
profiling several periods, the profiler appends the period to each output
filename.

The `simplified` preset disables TX/RX masks and adds a 1 ms DC-DC margin. The
`active-all` preset selects every TX/RX channel and fixes DC-DC turn-on at
100 us. Enable TX only after confirming a safe pulse-repetition rate for the
connected hardware and transducer.

## Runtime status

TCP and USB CDC links expose the same diagnostic interface:

```python
status = link.get_status()
print(hex(status.error_flags), status.current_buffer_usage)

link.clear_status()
link.clear_status(clear_counters=True)
```

The status snapshot includes acquisition-buffer overflow, SPI and transport
errors, DATA_READY, SPI and transmitted-frame counters, discarded frames, and
current and maximum buffer occupancy.
