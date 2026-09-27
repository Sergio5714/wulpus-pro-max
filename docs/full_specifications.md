# WULPUS Pro Max Full Specifications

Most specifications on this page are derived from measurements reported in the official [WULPUS PRO arXiv preprint](https://arxiv.org/abs/2607.12137).

## Transducer and transmit path

| Feature | Specification |
| --- | --- |
| Channels | 16, time-multiplexed |
| Transducer support | PZT transducers and CMUTs |
| Transducer bias | Indirect or direct bias, -30 V or 30 V |
| Excitation amplitude | 30 V unipolar |
| Excitation frequency | 100 kHz to 10 MHz |

## Receive path

| Feature | Specification |
| --- | --- |
| Analog front-end | 6 dB LNA + 70 dB VGA |
| Time gain compensation | TGC up to 70 dB depth-dependent attenuation compensation |
| Envelope extraction | Optional LTC5507-based envelope detector, runtime configurable |
| Envelope detector bandwidth | Up to 1.5 MHz envelope bandwidth |
| Amplification-only bandwidth | Up to 14 MHz |
| End-to-end -3 dB bandwidth | 1.4 MHz (bounded by MSP430) |
| Passband SNR | Approximately 45 dB at 41.9 dB total gain |
| SNR at 3 MHz | >=30 dB |
| Maximum SINAD | 41 dB at 1 MHz (25.3 mV input);<br>35 dB at 2.25 MHz (31.6 mV input) |
| ENOB (based on SINAD) | Approximately 6.5 bits at 1 MHz;<br>approximately 5.5 bits at 2.25 MHz |

## Acquisition and data link

| Feature | Specification |
| --- | --- |
| ADC | 8 Msps analog-to-digital converter, 12-bit resolution |
| Host interface | SPI, 8 MHz |
| Maximum PRF | 500 Hz |
| Raw streaming FPS<br>(400 samples per acquisition) | USB (500 Hz)<br>Wi-Fi (500 Hz)<br>BLE (50 Hz, legacy) |

## Power

| Feature | Specification |
| --- | --- |
| Power budget | <=40 mW at 50 Hz PRF (with BLE host) |
| Core electronics power<br>(Acquisition PCB) | 35 mW (50 Hz PRF)<br>58 mW (300 Hz PRF) |
| Battery-life reference<br>(BLE host) | More than 24 hours of continuous raw data streaming<br>at 50 Hz PRF from a 300 mAh Li-Po battery|

## Imaging performance

| Feature | Specification |
| --- | --- |
| B-mode frame rate | 18 FPS using 16-channel synthetic-aperture acquisition at 300 Hz PRF |
| B-mode axial resolution | ~ 0.7 mm with a 2.25 MHz transducer (LA-2.25-32, Vermon) |
| B-mode lateral resolution | ~ 2.3 mm at the center with a 2.25 MHz transducer (LA-2.25-32, Vermon) |

## Mechanics

| Feature | Specification |
| --- | --- |
| Acquisition PCB size | 39 x 21 x 6 mm |
| Acquisition PCB weight | 5 g |
| WiFi host PCB size | 39 x 21 x 7 mm |
| WiFi host PCB weight | 5 g |
