# Firmware flashing

The desktop application and `wulpus_pro_firmware_update.ipynb` support released
ESP32-C6 and MSP430 firmware packages. Use the ZIP package published for the
target processor; do not extract or rename its contents.

## Prepare for an update

1. Connect the device directly through USB CDC when updating the ESP32.
2. Stop acquisition and disconnect other clients, serial monitors, and IDE
   monitors from the device.
3. Keep the device powered and connected until the operation completes.
4. Confirm that the selected package belongs to WULPUS Pro Max and the intended
   processor.

Install the flashing dependencies when running from source:

```powershell
uv sync --locked --project sw --group desktop --group flash
```

## Update ESP32 firmware in the desktop GUI

1. Open the **Firmware Update** tab.
2. Select the ESP32 serial port and the released ESP32 ZIP package.
3. Confirm that the GUI recognizes the selected ESP32 firmware package and
   shows the expected version.
4. Select **I will keep USB and board power connected**.
5. Select **Flash ESP32** and wait for flashing and verification to finish.
6. Allow the ESP32 to reboot, then refresh the device list and reconnect.

If automatic bootloader entry fails, hold **BOOT**, tap **RESET**, release
**BOOT**, and retry. Ensure that no other application owns the COM port.

## Update MSP430 firmware in the desktop GUI

1. Connect to the ESP32 host through USB CDC or Wi-Fi.
2. Select the released MSP430 ZIP package.
3. Select **Program MSP430**.
4. Wait while the GUI uploads the firmware and the ESP32 programs the MSP430
   through JTAG.
5. Confirm that the GUI reports `COMPLETE` and refreshes the installed firmware
   versions.

`COMPLETE` confirms that programming and verification succeeded. It does not by
itself confirm normal application behavior, so perform a basic acquisition
after the update.

The GUI displays the MSP430 firmware version as `unknown` until the first
acquisition completes. After that acquisition, the detected version appears
automatically.

MSP430 programming requires the WULPUS Pro Max WiFi host PCB. A standalone XIAO
ESP32-C6 does not provide the required JTAG connection to the MSP430.

## Use the compatibility notebook

From `sw`, start Jupyter and open
[`wulpus_pro_firmware_update.ipynb`](../wulpus_pro_firmware_update.ipynb):

```powershell
uv run --group flash jupyter notebook
```

The notebook provides separate ESP32 and MSP430 panels using the same package
validation and update APIs as the desktop application.

## Recovery and implementation details

For wiring, partitions, package validation, MSP430 status codes, recovery, and
developer workflows, see the repository
[firmware update guide](../../docs/firmware_update_guide.md).
