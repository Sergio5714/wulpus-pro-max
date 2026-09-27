"""
   Copyright (C) 2026 ETH Zurich. All rights reserved.
   Author: Cedric Hirschi, ETH Zurich
           Sergei Vostrikov, ETH Zurich
   Modifications Copyright (C) 2026 Sergei Vostrikov
   Modifications by Sergei Vostrikov:
   - Refactored discovery into a thread-safe mDNS browser with endpoint
     validation, deduplication, and deterministic ordering.
   - Changed the default mDNS service identity from `wulpus` to `wulpus_pro`.
   - Renamed user-facing product references to WULPUS Pro Max.
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
"""

from dataclasses import dataclass
import logging
from threading import Lock
from time import sleep
from typing import Dict, List, Optional

from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WulpusProWiFiDevice:
    """A WULPUS Pro Max Wi-Fi endpoint discovered through mDNS."""

    name: str
    server: str
    ip: str
    port: int

    def __post_init__(self) -> None:
        if not 0 < self.port <= 65535:
            raise ValueError(f"Invalid TCP port: {self.port}")

    @property
    def description(self) -> str:
        if ":" in self.ip:
            return f"[{self.ip}]:{self.port}"
        return f"{self.ip}:{self.port}"

    def __str__(self) -> str:
        return f"{self.name} at {self.description}"


class _WulpusProServiceListener(ServiceListener):
    def __init__(self) -> None:
        self.services: Dict[str, ServiceInfo] = {}
        self._lock = Lock()

    def _resolve(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        info = zeroconf.get_service_info(service_type, name)
        if info is None:
            logger.debug("Could not resolve mDNS service %s", name)
            return
        with self._lock:
            self.services[name] = info

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self._resolve(zeroconf, service_type, name)

    def update_service(
        self, zeroconf: Zeroconf, service_type: str, name: str
    ) -> None:
        self._resolve(zeroconf, service_type, name)

    def remove_service(
        self, zeroconf: Zeroconf, service_type: str, name: str
    ) -> None:
        with self._lock:
            self.services.pop(name, None)

    def snapshot(self) -> List[ServiceInfo]:
        with self._lock:
            return list(self.services.values())


class WulpusProWiFiDiscovery:
    """Discover WULPUS Pro Max TCP services advertised over mDNS."""

    def __init__(self, service_name: str = "wulpus_pro", service_type: str = "tcp"):
        self.service_name = service_name
        self.service_type = service_type
        self.service = f"_{service_name}._{service_type}.local."
        self.devices: List[WulpusProWiFiDevice] = []

    @staticmethod
    def _to_device(info: ServiceInfo) -> Optional[WulpusProWiFiDevice]:
        addresses = info.parsed_addresses()
        if not addresses:
            logger.warning("mDNS service %s has no address", info.name)
            return None

        server = (info.server or "").removesuffix(".")
        return WulpusProWiFiDevice(
            name=info.name,
            server=server,
            ip=addresses[0],
            port=info.port,
        )

    def find(self, timeout: float = 5.0) -> List[WulpusProWiFiDevice]:
        if timeout < 0:
            raise ValueError("Discovery timeout must not be negative")

        zeroconf = Zeroconf()
        listener = _WulpusProServiceListener()
        browser = ServiceBrowser(zeroconf, self.service, listener)
        try:
            # ServiceBrowser works asynchronously. Waiting for the complete scan
            # interval lets us collect more than only the first responding device.
            sleep(timeout)
            discovered = listener.snapshot()
        finally:
            browser.cancel()
            zeroconf.close()

        devices = [self._to_device(info) for info in discovered]
        self.devices = sorted(
            {
                device.description: device
                for device in devices
                if device is not None
            }.values(),
            key=lambda device: (device.name, device.ip, device.port),
        )
        logger.info("Found %d WULPUS Pro Max Wi-Fi device(s)", len(self.devices))
        return list(self.devices)
