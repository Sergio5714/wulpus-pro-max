"""
Copyright (C) 2026 Sergei Vostrikov

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0

USB CDC GUI for persistent WULPUS Pro Max device configuration.
"""

from typing import Dict, Optional

import ipywidgets as widgets

from .usb_cdc_link import WulpusProUsbCdcDevice, WulpusProUsbCdcLink
from .wifi_link import WulpusProDeviceConfig, WulpusProWiFiPowerSave


class WulpusProDeviceConfigGUI(widgets.VBox):
    """Load and replace device configuration and write-only credentials."""

    def __init__(self, link: Optional[WulpusProUsbCdcLink] = None) -> None:
        self.link = link or WulpusProUsbCdcLink()
        self.devices: Dict[str, WulpusProUsbCdcDevice] = {}

        self.device = widgets.Dropdown(description="USB device")
        self.wifi_boot = widgets.Checkbox(description="Enable Wi-Fi at boot")
        self.auto_provision = widgets.Checkbox(description="Automatic provisioning")
        self.power_save = widgets.Dropdown(
            description="Power save",
            options=[(item.name, item) for item in WulpusProWiFiPowerSave],
        )
        self.twt = widgets.Checkbox(description="Enable TWT")
        self.ssid = widgets.Text(description="New SSID")
        self.password = widgets.Password(description="New password")
        self.confirm_clear = widgets.Checkbox(description="Confirm removal")
        self.output = widgets.Output()

        refresh = self._button("Refresh", self._refresh)
        connect = self._button("Connect", self._connect)
        disconnect = self._button("Disconnect", self._disconnect)
        load = self._button("Load config", self._load)
        save = self._button("Save config", self._save)
        set_credentials = self._button("Set credentials", self._set_credentials)
        clear_credentials = self._button("Clear credentials", self._clear_credentials)
        reboot = self._button("Reboot", self._reboot)

        config_panel = widgets.VBox(
            [
                widgets.HTML("<b>Device configuration</b>"),
                self.wifi_boot,
                self.auto_provision,
                self.power_save,
                self.twt,
                widgets.HBox([save, reboot]),
            ],
            layout=widgets.Layout(width="50%"),
        )
        credentials_panel = widgets.VBox(
            [
                widgets.HTML("<b>Replace credentials (write-only)</b>"),
                self.ssid,
                self.password,
                set_credentials,
                self.confirm_clear,
                clear_credentials,
            ],
            layout=widgets.Layout(width="50%"),
        )
        super().__init__(
            [
                widgets.HBox([refresh, connect, disconnect, load]),
                self.device,
                widgets.HBox([config_panel, credentials_panel]),
                self.output,
            ]
        )
        self._refresh()

    @staticmethod
    def _button(description, callback):
        button = widgets.Button(description=description)
        button.on_click(callback)
        return button

    def _run(self, operation) -> None:
        with self.output:
            self.output.clear_output()
            try:
                operation()
            except Exception as error:
                print(f"Error: {error}")

    def _refresh(self, _=None) -> None:
        found = self.link.get_available()
        self.devices = {str(item): item for item in found}
        self.device.options = list(self.devices)

    def _connect(self, _=None) -> None:
        def operation():
            if not self.device.value or not self.link.open(self.devices[self.device.value]):
                raise RuntimeError("Could not connect")
            print("Connected over USB CDC")

        self._run(operation)

    def _disconnect(self, _=None) -> None:
        def operation():
            if not self.link.close():
                raise RuntimeError("Could not disconnect")
            print("USB CDC port closed")

        self._run(operation)

    def _load(self, _=None) -> None:
        def operation():
            config = self.link.get_device_config()
            status = self.link.get_wifi_status()
            self.wifi_boot.value = config.wifi_enabled_at_boot
            self.auto_provision.value = config.auto_provision
            self.power_save.value = config.wifi_power_save_mode
            self.twt.value = config.twt_enabled
            print(f"Configuration loaded; credentials present: {status.credentials_present}")

        self._run(operation)

    def _save(self, _=None) -> None:
        def operation():
            self.link.set_device_config(
                WulpusProDeviceConfig(
                    self.wifi_boot.value,
                    self.auto_provision.value,
                    self.power_save.value,
                    self.twt.value,
                )
            )
            print("Device configuration saved; reboot required")

        self._run(operation)

    def _set_credentials(self, _=None) -> None:
        def operation():
            self.link.set_wifi_credentials(self.ssid.value, self.password.value)
            self.ssid.value = ""
            self.password.value = ""
            print("Credentials saved; reboot required")

        self._run(operation)

    def _clear_credentials(self, _=None) -> None:
        def operation():
            if not self.confirm_clear.value:
                raise ValueError("Select confirmation before clearing credentials")
            self.link.clear_wifi_credentials()
            self.confirm_clear.value = False
            print("Credentials cleared; reboot required")

        self._run(operation)

    def _reboot(self, _=None) -> None:
        def operation():
            self.link.reset()
            print("Reboot requested; reconnect after the device restarts")

        self._run(operation)
