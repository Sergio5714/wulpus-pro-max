# Firmware update guide

This guide explains how to install released ESP32-C6 and MSP430FR5043 firmware
on a WULPUS Pro Max WiFi host PCB connected to an Acquisition PCB. Use the
packaged files attached to the corresponding project release on GitHub.

> **Note:** This workflow is suitable for freshly fabricated and assembled
> boards with blank controllers. It installs the complete ESP32 image first,
> then uses the running ESP32 and the WiFi host PCB's integrated JTAG
> connections to program the MSP430. No external programmer is required for
> normal initial provisioning.

## Requirements

- A WiFi host PCB connected to the Acquisition PCB.
- A data-capable USB-C cable and stable power throughout the update.
- The [Python software environment](../sw/README.md#how-to-get-started),
  including the `flash` dependency group.
- `wulpus-pro-max-esp32-<version>.zip` for an ESP32 update.
- `wulpus-pro-max-msp430-<version>.mspfw` for an MSP430 update.

Close the acquisition GUI, serial monitors, and any other program using the
ESP32 COM port. Disconnect an external MSP-FET before updating the MSP430.

> The integrated MSP430 updater requires the JTAG connections on the WiFi host
> PCB. It is not available with a standalone XIAO ESP32-C6 connected through
> the Acquisition PCB's Dupont headers.

## Open the updater

From the `sw` directory, start Jupyter and open
`wulpus_pro_firmware_update.ipynb`:

```powershell
uv sync --group flash
uv run jupyter notebook
```

## Update the ESP32

On a freshly fabricated board, perform this step before attempting the MSP430
update.

1. In the ESP32 section, refresh the port list and select the ESP32-C6 port.
2. Select the released ESP32 ZIP. The GUI verifies its product, target, flash
   layout, version, and image checksums.
3. Confirm that USB and power will remain connected, then click **Flash ESP32**.
4. Wait for writing, verification, reset, and USB re-enumeration to finish.

The normal update preserves the device configuration and saved Wi-Fi
credentials. If automatic bootloader entry fails, hold **BOOT**, press and
release **RESET**, release **BOOT**, and retry.

## Update the MSP430

Update the ESP32 first when both controllers need new firmware.

1. Wait for the ESP32 to restart, then refresh and open its COM port in the
   MSP430 section.
2. Select the released `.mspfw` file and click **Upload and program**.
3. Keep USB and system power connected while the image is uploaded and the
   ESP32 restarts to program and verify the MSP430.
4. Reconnect and click **Check status** if the result is not restored
   automatically. Require `COMPLETE` with error zero.

`COMPLETE` confirms programming and verification. Reopen the acquisition
notebook, apply a configuration, and verify normal acquisition to confirm that
the full system operates correctly.

## Verify the installed versions

Open `wulpus_pro_example.ipynb`, connect to the device, and confirm the reported
ESP32 and MSP430 versions match the selected release packages. The MSP430
version becomes available after the first successful acquisition-configuration
exchange.

## Recovery

An interrupted MSP430 update is not resumed automatically, and the MSP430 has
no dual-image rollback. Reconnect and retry the complete update. If the ESP32
cannot identify or program the MSP430, recovery may require an external
programmer.

Developers investigating the updater implementation should use the
[ESP32 MSP430 updater implementation guide](../fw/esp32/docs/msp430_update_guide.md).
