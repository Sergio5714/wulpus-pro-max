# Acquisition owner regression tests

Run from `fw/esp32`:

```text
python tests/acquisition/run.py
```

The runner uses a native C11 compiler (`CC`, `cc`, or MSVC). On Windows it can
find MSVC Build Tools and the Windows SDK in their standard installation paths.
Artifacts go to `build/acquisition-tests`. No board, serial port, or ESP-IDF
runtime is needed. The tests compile the actual `acquisition_thread.c` with
mock GPIO, SPI, FreeRTOS, session, and frame-pool dependencies, and use the
production internal interface and session/frame headers.

The simulation checks startup and delayed readiness, config low acknowledgement,
a low/high pulse within SPI, pre-enable retention, one transfer per assertion,
repeated start/stop, stop queued during SPI, quiescent high and low, restart's
next configuration request, disconnect before/during transfers, malformed data
after simulated MSP reset, stale generations, private command completion storage,
and timeout cancellation followed by a new command. It also checks disable/resume and the GUI sequence
`STOP_RX -> SET_ACQ_CONFIG(0xFB) -> SET_ACQ_CONFIG(0xFA) -> START_RX`,
including repeated acquisitions and restart acknowledgement timing.

It is deterministic and single-threaded. It does not prove interrupt latency,
FreeRTOS scheduling, electrical timing, DMA behavior, or transport-write ordering.

## USB hardware regression

Close the GUI serial connection and run with the `sw` Python environment:

```powershell
../../sw/.venv/Scripts/python.exe scripts/verify_acquisition_usb.py --port COM10 --cycles 10 --frames 1000
```

This runs the actual GUI command sequence (including CLEAR_STATUS and legacy
restart blocks), checks contiguous frame sequence numbers and firmware errors,
and requires successful STOP/CLOSE acknowledgements. It uses zero TX/RX masks.
It resets the MSP430 and changes its acquisition configuration.

## Physical-board verification (not executed by the host tests)

Capture DATA_READY, CS, SCLK, and MSP_RST_N with a logic analyzer. Log PC commands,
responses, frame sequence numbers, and runtime status for each scenario:

| Scenario | Required observation |
|---|---|
| Fresh ESP32 boot and configuration | One 804-byte config transfer after high; config acknowledgement after low. |
| Delayed MSP startup | Configuration waits for readiness; after two seconds, error rather than success. |
| START_RX with first frame pending | Held frame appears once, retaining its sequence/generation; no duplicate SPI transaction. |
| Repeated STOP_RX / START_RX | Each new physical assertion gets one transfer; no stalled pending frame. |
| Stop during SPI | Existing transfer finishes before stop acknowledgement; no automatic transfer afterward. |
| Stop while DATA_READY low | STOP_RX completes without waiting for a measurement; CLOSE restart waits for next assertion. |
| Stop while DATA_READY high/pending | Pending private/ready frames discarded; restart uses unconsumed high once. |
| Disconnect during configuration | No success acknowledgement after cancellation; reset/cleanup completes; new session configures cleanly. |
| Disconnect during acquisition | No frame reaches a new generation; quiesce/restart/reset cleanup succeeds. |
| MSP430 reset during acquisition | Check error/recovery via RESET_MSP, reconfigure, START_RX; no duplicate transfer on held high. |
| Fast restart low/high | Rising-edge latch proves the intervening low; restart success follows the next configuration-request high. |

An unexpected MSP reset has no dedicated ESP input. Invalid RF markers stop the
owner, but an MSP configuration request with a retained valid RF marker cannot
be reliably identified as a reset with the current wire protocol. Test the actual
MSP firmware behavior; stronger reset detection needs a protocol change.

A link packet already being transmitted may finish after acquisition quiescence.
SPI ownership and publication quiescence do not cancel a partially written packet.
