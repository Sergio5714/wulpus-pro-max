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

Profile WULPUS Pro Max frame rate over ESP32-C6 native USB CDC.
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np

from wulpus.usb_cdc_link import WulpusProUsbCdcLink
from wulpus.uss_conf_pro import WulpusProUssConfig
from wulpus.wifi_link import WulpusProWiFiError

DEFAULT_DCDC_AFTER_PERIOD_MARGIN_US = 1000
MAX_SLOW_TIMER_PERIOD_US = 2_000_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure sustained USB CDC frame rate. TX is disabled by default; "
            "close the GUI and serial monitors before running."
        )
    )
    parser.add_argument("--port", default="COM9", help="USB CDC port (default: COM9)")
    parser.add_argument(
        "--mode",
        choices=("custom", "simplified", "active-all"),
        default="custom",
        help=(
            "configuration preset: simplified uses TX/RX 0x0000 and the "
            "default DC-DC margin; active-all uses TX/RX 0xFFFF and fixed "
            "dcdc_turnon=100 us; custom uses the explicit mask/timing options"
        ),
    )
    parser.add_argument(
        "--period-us",
        type=int,
        nargs="+",
        help=(
            "acquisition periods to test, in microseconds; when omitted with "
            "--config, use meas_period from the saved configuration"
        ),
    )
    parser.add_argument(
        "--config",
        help="GUI-saved WULPUS Pro Max acquisition configuration JSON file",
    )
    parser.add_argument("--frames", type=int, default=500, help="Measured frames per period")
    parser.add_argument("--warmup", type=int, default=10, help="Frames discarded before timing")
    parser.add_argument(
        "--output",
        help=(
            "optionally save measured frames as a GUI-compatible .npz file; "
            "rate sweeps append _<period>us to the filename"
        ),
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=None,
        help="override 16-bit samples per frame (default: saved value or 400)",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-frame timeout in seconds")
    parser.add_argument(
        "--dcdc-margin-us",
        type=int,
        default=None,
        help=(
            "microseconds added to the acquisition period for dcdc_turnon "
            f"(default: {DEFAULT_DCDC_AFTER_PERIOD_MARGIN_US})"
        ),
    )
    parser.add_argument(
        "--dcdc-turnon-us",
        type=int,
        default=None,
        help=(
            "absolute dcdc_turnon time in microseconds; when set, overrides "
            "--dcdc-margin-us"
        ),
    )
    parser.add_argument(
        "--tx-mask",
        type=lambda value: int(value, 0),
        default=None,
        help="override TX channel bit mask",
    )
    parser.add_argument(
        "--rx-mask",
        type=lambda value: int(value, 0),
        default=None,
        help="override RX channel bit mask",
    )
    return parser.parse_args()


def sequence_gap_count(numbers: List[int]) -> int:
    return sum(
        ((current - previous) & 0xFFFF) != 1
        for previous, current in zip(numbers, numbers[1:])
    )


def load_saved_config(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as config_file:
        data = json.load(config_file)
    if not isinstance(data, dict):
        raise ValueError("saved configuration must contain a JSON object")
    valid_fields = {
        "num_acqs", "dcdc_turnon", "meas_period", "trans_freq",
        "pulse_freq", "num_pulses", "sampling_freq", "num_samples",
        "rx_gain", "num_txrx_configs", "tx_configs", "rx_configs",
        "start_hvmuxrx", "start_ppg", "turnon_adc", "start_pgainbias",
        "start_adcsampl", "restart_capt", "capt_timeout",
        "vga_rc_prech_cyc", "vga_slope_code", "enable_env_det",
    }
    return {key: value for key, value in data.items() if key in valid_fields}


def make_config(args: argparse.Namespace, period_us: int) -> WulpusProUssConfig:
    values = dict(args.saved_config)
    values["num_acqs"] = args.frames + args.warmup
    values["meas_period"] = period_us

    if args.samples is not None:
        values["num_samples"] = args.samples
    if args.dcdc_turnon_us is not None:
        values["dcdc_turnon"] = args.dcdc_turnon_us
    elif args.dcdc_margin_us is not None:
        values["dcdc_turnon"] = period_us + args.dcdc_margin_us

    if args.tx_mask is not None or args.rx_mask is not None:
        tx_mask = 0 if args.tx_mask is None else args.tx_mask
        rx_mask = 0 if args.rx_mask is None else args.rx_mask
        values["num_txrx_configs"] = 1
        values["tx_configs"] = [tx_mask]
        values["rx_configs"] = [rx_mask]

    count = int(values.get("num_txrx_configs", 1))
    tx_configs = values.get("tx_configs")
    rx_configs = values.get("rx_configs")
    if tx_configs is None or rx_configs is None:
        if count != 1:
            raise ValueError(
                "saved configuration has multiple TX/RX configurations but "
                "does not contain tx_configs and rx_configs"
            )
        values.setdefault("tx_configs", [0])
        values.setdefault("rx_configs", [0])
    elif len(tx_configs) != count or len(rx_configs) != count:
        raise ValueError(
            "tx_configs and rx_configs lengths must match num_txrx_configs"
        )

    return WulpusProUssConfig(**values)


def output_path(filename: str, period_us: int, multiple_periods: bool) -> Path:
    path = Path(filename)
    if path.suffix.lower() != ".npz":
        path = path.with_suffix(".npz")
    if multiple_periods:
        path = path.with_name(f"{path.stem}_{period_us}us{path.suffix}")
    return path


def profile_period(
    link: WulpusProUsbCdcLink,
    args: argparse.Namespace,
    period_us: int,
    save_path: Optional[Path] = None,
) -> bool:
    config = make_config(args, period_us)
    link.acq_length = config.num_samples
    timestamps: List[float] = []
    acquisition_numbers: List[int] = []
    timed_out = False
    total_received = 0
    saved_samples = []
    saved_acq_numbers = []
    saved_tx_rx_ids = []

    link.toggle_rx(False)
    link.send_acq_config(config.get_restart_package())
    time.sleep(2.5)
    link.send_acq_config(config.get_conf_package())
    link.toggle_rx(True)
    try:
        for index in range(args.frames + args.warmup):
            frame = link.receive_frame(args.timeout)
            if frame is None:
                timed_out = True
                break
            total_received += 1
            if index >= args.warmup:
                timestamps.append(time.perf_counter())
                acquisition_numbers.append(frame.acquisition_number)
                if save_path is not None:
                    # frame.samples is already a view of the received immutable
                    # packet bytes. Retain that view and defer all bulk copying
                    # and file I/O until acquisition has stopped.
                    saved_samples.append(frame.samples)
                    saved_acq_numbers.append(frame.acquisition_number)
                    saved_tx_rx_ids.append(frame.tx_rx_id)
    finally:
        link.toggle_rx(False)
        link.send_acq_config(config.get_restart_package())

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        data_arr = (
            np.column_stack(saved_samples).astype("<i2", copy=False)
            if saved_samples
            else np.empty((config.num_samples, 0), dtype="<i2")
        )
        np.savez(
            save_path,
            data_arr=data_arr,
            acq_num_arr=np.asarray(saved_acq_numbers, dtype="<u2"),
            tx_rx_id_arr=np.asarray(saved_tx_rx_ids, dtype=np.uint8),
        )
        print(f"Saved {len(saved_samples)} measured frames to {save_path}")

    target_fps = 1_000_000 / period_us
    if len(timestamps) < 2:
        print(
            f"{period_us:9d} us  target={target_fps:9.2f} FPS  "
            f"insufficient frames (received={total_received}, "
            f"warmup={min(total_received, args.warmup)}, "
            f"measured={len(timestamps)}, timeout={timed_out})"
        )
        return False

    intervals = [later - earlier for earlier, later in zip(timestamps, timestamps[1:])]
    average_fps = (len(timestamps) - 1) / (timestamps[-1] - timestamps[0])
    median_fps = 1 / statistics.median(intervals)
    p95_interval = sorted(intervals)[int(0.95 * (len(intervals) - 1))]
    gaps = sequence_gap_count(acquisition_numbers)
    stable = not timed_out and gaps == 0 and len(timestamps) == args.frames
    status = "PASS" if stable else "FAIL"
    print(
        f"{period_us:9d} us  target={target_fps:9.2f} FPS  "
        f"average={average_fps:9.2f}  median={median_fps:9.2f}  "
        f"p95_latency={p95_interval * 1000:8.3f} ms  "
        f"frames={len(timestamps):5d}  gaps={gaps:3d}  {status}"
    )
    return stable


def main() -> int:
    args = parse_args()
    if args.mode == "simplified":
        args.tx_mask = 0x0000
        args.rx_mask = 0x0000
        args.dcdc_turnon_us = None
        args.dcdc_margin_us = DEFAULT_DCDC_AFTER_PERIOD_MARGIN_US
    elif args.mode == "active-all":
        args.tx_mask = 0xFFFF
        args.rx_mask = 0xFFFF
        args.dcdc_turnon_us = 100

    try:
        args.saved_config = load_saved_config(args.config) if args.config else {}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"could not load acquisition configuration: {exc}") from exc

    if args.period_us is None:
        if "meas_period" not in args.saved_config:
            raise SystemExit("--period-us is required unless --config contains meas_period")
        args.period_us = [int(args.saved_config["meas_period"])]

    if args.mode == "custom" and not args.config:
        if args.tx_mask is None:
            args.tx_mask = 0
        if args.rx_mask is None:
            args.rx_mask = 0
        if args.dcdc_turnon_us is None and args.dcdc_margin_us is None:
            args.dcdc_margin_us = DEFAULT_DCDC_AFTER_PERIOD_MARGIN_US

    effective_samples = args.samples
    if effective_samples is None:
        effective_samples = int(args.saved_config.get("num_samples", 400))

    if args.frames < 2 or args.warmup < 0 or effective_samples <= 0:
        raise SystemExit("frames must be >= 2, warmup >= 0, and samples > 0")
    if any(period <= 0 for period in args.period_us):
        raise SystemExit("all acquisition periods must be greater than zero")
    if args.dcdc_margin_us is not None and args.dcdc_margin_us <= 0:
        raise SystemExit("dcdc-margin-us must be greater than zero")
    if args.dcdc_turnon_us is not None and args.dcdc_turnon_us <= 0:
        raise SystemExit("dcdc-turnon-us must be greater than zero")
    if (
        args.dcdc_turnon_us is not None
        and args.dcdc_turnon_us > MAX_SLOW_TIMER_PERIOD_US
    ):
        raise SystemExit(
            f"dcdc-turnon-us must not exceed {MAX_SLOW_TIMER_PERIOD_US}"
        )
    if (
        args.tx_mask is not None and not 0 <= args.tx_mask <= 0xFFFF
    ) or (
        args.rx_mask is not None and not 0 <= args.rx_mask <= 0xFFFF
    ):
        raise SystemExit("TX and RX masks must fit in 16 bits (0x0000..0xFFFF)")
    if args.dcdc_margin_us is not None and any(
        period + args.dcdc_margin_us > MAX_SLOW_TIMER_PERIOD_US
        for period in args.period_us
    ):
        raise SystemExit(
            "each acquisition period must leave room for dcdc_turnon to be "
            f"{args.dcdc_margin_us} us later (maximum period: "
            f"{MAX_SLOW_TIMER_PERIOD_US - args.dcdc_margin_us} us)"
        )

    link = WulpusProUsbCdcLink(port=args.port, timeout=args.timeout)
    if not link.open():
        print(f"Could not open {args.port}; close the GUI and serial monitors", file=sys.stderr)
        return 2

    results: List[bool] = []
    try:
        pong = link.ping(args.timeout)
        print(f"Connected to {args.port}; handshake payload={pong[1]!r}")
        preview = make_config(args, args.period_us[0])
        tx_masks = ", ".join(f"0x{int(mask):04X}" for mask in preview.tx_configs)
        rx_masks = ", ".join(f"0x{int(mask):04X}" for mask in preview.rx_configs)
        print(
            f"Configuration: mode={args.mode}; TX=[{tx_masks}]; "
            f"RX=[{rx_masks}]; first dcdc_turnon={preview.dcdc_turnon} us"
        )
        print(
            "   period             requested             measured"
            "                         integrity"
        )
        multiple_periods = len(args.period_us) > 1
        for period_us in args.period_us:
            save_path = (
                output_path(args.output, period_us, multiple_periods)
                if args.output
                else None
            )
            results.append(profile_period(link, args, period_us, save_path))
    except WulpusProWiFiError as exc:
        print(f"Profiling failed: {exc}", file=sys.stderr)
        return 3
    finally:
        link.close()

    passing = [period for period, passed in zip(args.period_us, results) if passed]
    if passing:
        fastest = min(passing)
        print(f"Fastest stable tested period: {fastest} us ({1_000_000 / fastest:.2f} FPS target)")
    else:
        print("No tested period completed without timeout or sequence gaps")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
