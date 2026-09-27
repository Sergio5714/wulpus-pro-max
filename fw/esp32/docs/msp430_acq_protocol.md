# ESP32-to-MSP430 acquisition protocol

The ESP32 is the SPI master and the MSP430 acquisition controller is
the SPI slave. The interface uses fixed-length, full-duplex transactions: data
from the ESP32 configures or restarts the MSP430 while data from the MSP430
contains an acquisition frame when one is available.

## Contents

- [Electrical and SPI settings](#electrical-and-spi-settings)
- [Transaction phases](#transaction-phases)
- [Configuration package](#configuration-package)
- [RF acquisition payload](#rf-acquisition-payload)
- [Current constraints](#current-constraints)

## Electrical and SPI settings

| Property | Value |
|---|---|
| SPI role | ESP32 master, MSP430 slave |
| Clock | 8 MHz by default (`CONFIG_WP_SPI_CLOCK_SPEED`) |
| Mode | SPI mode 1 |
| Bit order | MSB first |
| Chip select | Active low, hardware-controlled by the ESP32 SPI driver |
| Transaction length | 804 bytes |
| Flow-control signal | Active-high `DATA_READY` from MSP430 to ESP32 |
| MSP430 reset | Active-low, open-drain `MSP_RST_N` from ESP32 |

The MSP430 raises `DATA_READY` only after its SPI DMA is prepared. The ESP32
detects the rising edge and performs one 804-byte transaction. The MSP430 lowers
`DATA_READY` when its receive DMA completes.

## Transaction phases

### Configuration phase

After the ESP32 releases `MSP_RST_N`, the MSP430 initializes its peripherals,
disables acquisition power paths, and requests a configuration transfer by
raising `DATA_READY`.

The ESP32 transmits an 804-byte block whose meaningful prefix is the
configuration package described below. The remainder is zero padding. The
MSP430 examines byte 0; it accepts the package only when that byte is `0xFA`.
Invalid packages cause it to request another configuration transaction.

### Acquisition phase

After applying a valid configuration, the MSP430 performs acquisitions at the
configured measurement period. When an acquisition completes, it prepares the
804-byte RF frame, raises `DATA_READY`, and waits for the ESP32 SPI transaction.

During that full-duplex transaction:

- MSP430 to ESP32 carries the RF frame.
- ESP32 to MSP430 is normally zero-filled.
- If ESP32 byte 0 is `0xFB`, the MSP430 exits the acquisition loop after the
  transfer and returns to the configuration phase.

This restart-on-next-transfer behavior allows a graceful shutdown: the ESP32
sends an 804-byte block beginning with `0xFB`, waits for `DATA_READY` to fall,
and then waits for the next configuration request before asserting reset.

## Configuration package

All multibyte values are little-endian. The host sends a 105-byte configuration
package, and the ESP32 zero-pads it to the fixed 804-byte SPI transaction.

### Fixed prefix

| Offset | Size (bytes) | Field | Meaning |
|---:|---:|---|---|
| 0 | 1 | `start_byte` | `0xFA` identifies a configuration package. |
| 1 | 2 | `dcdc_turnon` | Slow-timer count for enabling the HV DC-DC before acquisition. Generated as `floor(microseconds * 65535 / 2000000)`. It must be lower than `meas_period` so the DC-DC event occurs before acquisition in the timer sequence. |
| 3 | 2 | `meas_period` | Slow-timer acquisition-period count, using the same approximately 32.768 kHz conversion. A 2000 us period requests 500 FPS. |
| 5 | 4 | `trans_freq` | Transducer frequency in hertz. Present in the package but currently reserved/not used by MSP430 firmware. |
| 9 | 4 | `pulse_freq` | Pulse-generator frequency in hertz. |
| 13 | 1 | `num_pulses` | Number of excitation pulses, 0–30 in the host configuration model. |
| 14 | 2 | `oversampling_rate` | SDHS oversampling selector; see the table below. |
| 16 | 2 | `sample_size_bytes` | Number of sample bytes, generated as `2 * num_samples`. The current ESP transport and frame format are fixed at 800 sample bytes (400 samples). |
| 18 | 1 | `rx_gain` | MSP430 PGA gain register code. |
| 19 | 1 | `enable_envelope_detector` | `0` disables and `1` enables the hardware envelope detector. |
| 20 | 1 | `tx_rx_config_count` | Number of TX/RX mask pairs that follow; maximum 16. |

### TX/RX configuration array

Starting at offset 21, each configuration occupies four bytes:

| Relative offset | Size (bytes) | Field | Meaning |
|---:|---:|---|---|
| `4*i + 0` | 2 | `tx_mask[i]` | Little-endian 16-bit transmit-channel mask. |
| `4*i + 2` | 2 | `rx_mask[i]` | Little-endian 16-bit receive-channel mask. |

The MSP430 cycles `tx_rx_id` from zero through
`tx_rx_config_count - 1`, then wraps to zero. A zero TX mask is useful for
receive-only throughput testing because it suppresses excitation pulses.

### Advanced timing and VGA fields

The advanced section starts at:

```text
advanced_offset = 21 + 4 * tx_rx_config_count
```

| Relative offset | Size (bytes) | Field | Host conversion and meaning |
|---:|---:|---|---|
| 0 | 2 | `start_hvmuxrx` | HV-MUX receive timing; `floor(us * 8)`. |
| 2 | 2 | `start_ppg` | Pulse-generator start timing; `floor(us * 5)`. |
| 4 | 2 | `turnon_adc` | ADC turn-on timing; `floor(us * 5)`. |
| 6 | 2 | `start_pgainbias` | PGA input-bias start timing; `floor(us * 5)`. |
| 8 | 2 | `start_adcsampl` | ADC sampling start timing; `floor(us * 5)`. |
| 10 | 2 | `restart_capt` | Capture-restart timing; `floor(us * 5 / 16)`. |
| 12 | 2 | `capt_timeout` | Capture timeout; `floor(us * 5 / 4)`. |
| 14 | 2 | `vga_rc_precharge_cycles` | VGA RC-network precharge duration in MSP430 delay cycles. Zero disables precharge. |
| 16 | 2 | `vga_slope_code` | Digital-potentiometer code for time-gain slope. Values 0–255 select a slope; 256 selects fixed-gain mode. |

The complete meaningful length is `39 + 4 * tx_rx_config_count` bytes. At the
maximum 16 configurations this is 103 bytes; the host package is padded to 105
bytes and the ESP32 SPI block to 804 bytes.

### Oversampling and sampling frequency

The host maps the SDHS oversampling selector to sample rate as follows:

| Register value | Oversampling ratio | Sampling frequency |
|---:|---:|---:|
| 0 | 10 | 8 MHz |
| 1 | 20 | 4 MHz |
| 2 | 40 | 2 MHz |
| 3 | 80 | 1 MHz |
| 4 | 160 | 500 kHz |

### RX gain

`rx_gain` is a hardware register code rather than a signed dB number. Supported
gain settings map to register codes 17–63; clients must use the MSP430 PGA gain
mapping rather than derive this byte directly from a dB value.

## RF acquisition payload

Every MSP430-to-ESP32 acquisition transfer is 804 bytes:

| Offset | Size (bytes) | Field | Meaning |
|---:|---:|---|---|
| 0 | 1 | `frame_marker` | `0xFF` identifies the beginning of an RF frame. |
| 1 | 1 | `tx_rx_id` | Index of the TX/RX configuration used for this frame. |
| 2 | 2 | `acquisition_number` | Little-endian unsigned 16-bit sequence number; increments after each successful acquisition and wraps at 65535. It resets when the MSP430 returns to its outer configuration loop. |
| 4 | 800 | `samples` | 400 little-endian signed 16-bit ADC samples. |

The ESP32 currently forwards all 804 bytes unchanged as the payload of a PC
`GET_DATA` packet. The host should use modulo-65536 sequence arithmetic when
detecting missing frames.

## Current constraints

- Host `PING` is answered by the ESP32; it is not an MSP430 health check.
  `SET_ACQ_CONFIG` is acknowledged after SPI transfer success and observation
  of DATA_READY low, without a separate MSP430 response validating the fields.
- ESP frame storage and the PC decoder are configured for a fixed 804-byte RF
  payload, corresponding to 400 samples. Although the configuration model
  exposes other sample counts, they require coordinated changes to the MSP430,
  ESP32 `CONFIG_WP_DATA_RX_LENGTH`, and host decoder.
- The MSP430 has one RF transfer buffer; it waits for the ESP32 transaction
  before advancing, so prompt servicing of `DATA_READY` is required.

See [Firmware architecture](firmware_architecture.md) for buffering and task ownership,
and [ESP32-to-PC protocol](esp32_pc_protocol.md) for the outer framing applied by the
ESP32.
