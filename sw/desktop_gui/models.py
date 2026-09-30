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


GUI-independent state and compatibility helpers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from wulpus.config_package_pro import configuration_package
from wulpus.uss_conf_pro import WulpusProUssConfig

ERROR_NAMES = {
    1 << 0: "Acquisition buffer overflow",
    1 << 1: "Data-ready overflow",
    1 << 2: "SPI timeout",
    1 << 3: "SPI failure",
    1 << 4: "Link timeout",
    1 << 5: "Link disconnected",
    1 << 6: "Protocol error",
}


@dataclass(frozen=True)
class TransportCapabilities:
    """Feature flags used to gate operations for each supported transport."""

    acquisition: bool = True
    device_config: bool = False
    runtime_status: bool = False
    wifi_status: bool = False
    msp_update: bool = False
    firmware_info: bool = False
    reset_device: bool = False
    reset_msp: bool = False


CAPABILITIES = {
    "USB CDC": TransportCapabilities(True, True, True, True, True, True, True, True),
    "Wi-Fi": TransportCapabilities(True, False, True, True, True, True, True, True),
    "BLE": TransportCapabilities(True),
    "Simulator": TransportCapabilities(True),
}


@dataclass(frozen=True)
class AcquisitionResult:
    """Captured frames in frames-by-samples order with sequence/config metadata."""

    frames: np.ndarray
    acquisition_numbers: np.ndarray
    tx_rx_ids: np.ndarray
    frame_gaps: int
    completed: bool


def decoded_errors(flags: int) -> list[str]:
    """Decode known sticky errors and retain a description of unknown bits."""
    names = [name for bit, name in ERROR_NAMES.items() if flags & bit]
    unknown = flags & ~sum(ERROR_NAMES)
    if unknown:
        names.append(f"Unknown flags 0x{unknown:08x}")
    return names


def frame_gap(previous: int | None, current: int) -> int:
    """Count missing frames for the wrapping uint16 acquisition counter."""
    if previous is None:
        return 0
    distance = (int(current) - int(previous)) & 0xFFFF
    return max(0, distance - 1) if distance < 0x8000 else 0


def config_values(config: WulpusProUssConfig) -> dict[str, Any]:
    """Convert a hardware configuration into editable/JSON-compatible values."""
    result = {
        param.config_name: getattr(config, param.config_name)
        for section in configuration_package
        for param in section
    }
    result["tx_configs"] = [int(item) for item in config.tx_configs]
    result["rx_configs"] = [int(item) for item in config.rx_configs]
    return result


def build_config(values: Mapping[str, Any]) -> WulpusProUssConfig:
    """Merge defaults with edited values and validate mask counts and timing."""
    defaults = config_values(WulpusProUssConfig())
    defaults.update(values)
    count = int(defaults["num_txrx_configs"])
    tx = list(defaults.get("tx_configs", []))
    rx = list(defaults.get("rx_configs", []))
    if len(tx) != count or len(rx) != count:
        raise ValueError("TX/RX configuration lengths must match num_txrx_configs")
    kwargs = {
        param.config_name: defaults[param.config_name]
        for section in configuration_package
        for param in section
    }
    kwargs["tx_configs"] = tx
    kwargs["rx_configs"] = rx
    return WulpusProUssConfig(**kwargs)


def load_config(path: str | Path) -> WulpusProUssConfig:
    """Load an acquisition configuration from JSON."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration JSON must contain an object")
    return build_config(data)


def save_config(path: str | Path, config: WulpusProUssConfig) -> None:
    """Write an acquisition configuration as formatted JSON."""
    Path(path).write_text(json.dumps(config_values(config), indent=4), encoding="utf-8")


def save_npz(path: str | Path, result: AcquisitionResult) -> None:
    """Write the established notebook-compatible, samples-by-frame layout."""
    np.savez(
        Path(path),
        data_arr=np.asarray(result.frames, dtype="<i2").T,
        acq_num_arr=np.asarray(result.acquisition_numbers, dtype="<u2"),
        tx_rx_id_arr=np.asarray(result.tx_rx_ids, dtype=np.uint8),
    )
