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

Exercise the GUI command sequence on a connected ESP32/MSP430 over USB.
Run with the sw Python environment; TX and RX masks are zero for this transport test.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sw"))
from wulpus.usb_cdc_link import WulpusProUsbCdcLink
from wulpus.wifi_link import WulpusProWiFiCommand as Command
from wulpus.uss_conf_pro import WulpusProUssConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--frames", type=int, default=1000)
    parser.add_argument("--period-us", type=int, default=3000)
    args = parser.parse_args()
    if args.cycles < 1 or args.frames < 2 or args.period_us < 2000:
        parser.error("require cycles >= 1, frames >= 2, period-us >= 2000")
    config = WulpusProUssConfig(
        dcdc_turnon=100, meas_period=args.period_us, num_samples=400,
        tx_configs=[0], rx_configs=[0], num_txrx_configs=1,
    )
    link = WulpusProUsbCdcLink(args.port, timeout=5.0)
    if not link.open():
        raise RuntimeError(f"Could not open {args.port}; close the GUI connection first")
    try:
        link.toggle_rx(False)
        link.send_command(Command.RESET_MSP)
        for cycle in range(1, args.cycles + 1):
            link.toggle_rx(False)
            link.send_acq_config(config.get_restart_package())
            time.sleep(2.5)  # Match the GUI's existing restart delay.
            link.send_acq_config(config.get_conf_package())
            link.clear_status(clear_counters=True, timeout=2.0)
            start = time.perf_counter()
            link.toggle_rx(True)
            acknowledgement_ms = (time.perf_counter() - start) * 1000
            previous = None
            gaps = 0
            sequence_jumps = []
            first_received = None
            for index in range(args.frames):
                frame = link.receive_frame(3.0)
                if frame is None:
                    raise RuntimeError(f"Cycle {cycle}: frame timeout after {index} frames")
                now = time.perf_counter()
                if first_received is None:
                    first_received = now
                if previous is not None and (frame.acquisition_number - previous) & 0xFFFF != 1:
                    gaps += 1
                    sequence_jumps.append([index, previous, frame.acquisition_number])
                previous = frame.acquisition_number
            fps = (args.frames - 1) / (now - first_received)
            link.toggle_rx(False)
            status = link.get_status()
            print(json.dumps({"cycle": cycle, "frames": args.frames, "fps": round(fps, 1),
                              "start_ack_ms": round(acknowledgement_ms, 1), "gaps": gaps, "sequence_jumps": sequence_jumps,
                              "status": asdict(status)}), flush=True)
            if gaps or status.error_flags or status.current_buffer_usage:
                raise RuntimeError(f"Cycle {cycle} failed sequence/status checks")
        link.send_command(Command.CLOSE)
        print("PASS: all cycles and CLOSE acknowledged", flush=True)
    except Exception:
        try:
            print("Failure status:", link.get_status(), flush=True)
        except Exception:
            pass
        try:
            link.toggle_rx(False)
            link.send_command(Command.CLOSE)
        except Exception:
            pass
        raise
    finally:
        if link.sock is not None:
            link.sock.close()
            link.sock = None


if __name__ == "__main__":
    main()
