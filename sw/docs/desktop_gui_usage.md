# Desktop GUI usage

The WULPUS Pro Max desktop application provides the normal workflow for device
configuration, acquisition, saved-data inspection, diagnostics, and firmware
updates.

## Start the application

Install the desktop dependencies as described in the
[dependency installation guide](dependency_installation.md), then run from the
`sw` folder:

```powershell
uv run --locked --group desktop --group flash python -m desktop_gui.main
```

On Windows, start the versioned one-file release directly, for example
`WULPUS-Pro-Max-x.x.x.exe`, where `x.x.x` is the release version.

## Connect a device

Open the connection panel, select a transport, refresh the available devices,
and connect:

- **USB CDC** provides direct communication through the ESP32-C6 USB
  Serial/JTAG interface. Close serial monitors and other applications using the
  same COM port before connecting.
- **Wi-Fi** discovers devices through mDNS. The computer and device must be on
  the same network. The software also tries the `wulpus_pro.local` hostname if
  multicast discovery is unavailable.
- **BLE** uses the legacy WULPUS USB dongle.

Only one host and one application can control a device at a time. Disconnect
before opening the port in another program or beginning an ESP32 update.

## Configure ultrasound acquisition

Use the **Ultrasound Configuration** tab to set:

- measurement period and acquisition timing;
- excitation frequency, pulse count, and high time;
- active transmit and receive channels;
- fixed or time-varying receive gain;
- advanced ADC, PGA, pulser, HV-MUX, and capture timing.

The live diagrams show the excitation waveform, high-voltage duty cycle,
receive-gain profile, and detailed acquisition sequence. Resolve timing errors
shown by these diagrams before starting acquisition. Save reusable ultrasound
and TX/RX configurations as JSON files.

## Acquire and save data

Choose A-mode, B-mode, or **Off** in the display selector. Turning display off
keeps acquisition and optional NPZ recording active while avoiding plot
processing, which provides the highest throughput.

Set the acquisition length and output file as needed, then start acquisition.
The application records raw frames and reports acquisition-number gaps. Stop is
cooperative and may wait for the current receive operation and device cleanup
to finish.

Saved NPZ files contain `data_arr`, `acq_num_arr`, and `tx_rx_id_arr`. Display
filters and envelope processing do not modify the saved raw samples.

## Inspect saved data

Open the **Data Viewer** tab and select a compatible NPZ file. The viewer can:

- filter frames by TX/RX configuration;
- move through acquisitions or replay them;
- display raw, band-pass-filtered, and envelope traces;
- switch between A-mode and B-mode views.

Legacy NPZ files do not store their sampling frequency. Enter the frequency
used during acquisition before applying filters or interpreting the time axis.

## Device configuration and diagnostics

Persistent ESP32 configuration and Wi-Fi credential changes require USB CDC.
Credentials are write-only and are never read back by the application. Reboot
the device when prompted so persistent changes take effect.

Use the service and diagnostic controls to inspect firmware versions, error
flags, frame counters, discarded frames, and buffer occupancy. Clearing status
can preserve lifetime counters or reset them, depending on the selected action.
The MSP430 firmware version is reported after the first acquisition completes.
Until then, the GUI displays its version as `unknown`.

Enable detailed logging through **Debug > Enable debug logging...**. Logs are
written in batches to reduce acquisition overhead and never include stored
Wi-Fi credentials or firmware payloads.

## Troubleshooting

- If USB is unavailable, close every program that may own the COM port, reconnect
  the cable, and refresh the device list.
- If Wi-Fi discovery fails, confirm that both systems are on the same network,
  allow mDNS on UDP port 5353, or enter the device address manually.
- If acquisition stalls, stop the session, review runtime status and the debug
  log, disconnect, and reconnect the device.
- If the application cannot reconnect after a reset or update, wait for the
  device to finish booting and refresh the connection list.

For firmware-update failures, follow the recovery steps in the
[firmware flashing guide](firmware_flashing.md).
