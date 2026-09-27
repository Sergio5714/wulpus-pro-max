# Wi-Fi provisioning guide

The firmware uses ESP-IDF network provisioning over a temporary SoftAP. Wi-Fi
credentials are stored in non-volatile storage and reused after reset or power
cycling.

## Contents

- [When provisioning starts](#when-provisioning-starts)
- [Provisioning parameters](#provisioning-parameters)
- [Boot sequence](#boot-sequence)
- [Reprovisioning](#reprovisioning)
- [USB operation during provisioning](#usb-operation-during-provisioning)
- [Troubleshooting](#troubleshooting)

Provisioning controls only Wi-Fi setup. It does not own the WULPUS Pro Max PC
protocol session, and native USB CDC remains available while the board is
waiting for credentials or network association.

## When provisioning starts

At boot, the persistent Wi-Fi manager loads `wulpus_pro/device_cfg` and checks
ESP-IDF's separate credential storage:

- If Wi-Fi is disabled at boot, the radio remains stopped and USB stays available.
- If no credentials exist and `auto_provision` is enabled, the board starts the SoftAP provisioning service.
- If no credentials exist and `auto_provision` is disabled, the board remains USB-only.
- If credentials exist, the provisioning manager is deinitialized and the
  board immediately attempts to join the stored network.
- If association is lost later, the station reconnects automatically.

The TCP listener starts only after the station obtains an IP address. The USB
listener starts independently during normal firmware startup.

## Provisioning parameters

| Setting | Current value |
|---|---|
| Scheme | SoftAP |
| SoftAP name | `PROV_WULPUS_PRO_XXXXXX` |
| Name suffix | Last three bytes of the station MAC address, uppercase hexadecimal |
| Provisioning security | ESP-IDF Security 1 |
| Proof of possession | `CONFIG_PROVISIONER_POP`; default `abcd1234` |
| SoftAP service key | None |

Use an ESP-IDF-compatible provisioning client, select the
`PROV_WULPUS_PRO_XXXXXX` device, enter the proof-of-possession value, and provide
the target Wi-Fi SSID and password. The provisioning service validates the
credentials by connecting to the requested access point.

The proof-of-possession default is suitable for development only. Set a unique
value through `CONFIG_PROVISIONER_POP` for deployed devices.

## Boot sequence

```mermaid
flowchart TD
    BOOT["Boot"] --> ENABLED{"Wi-Fi enabled at boot?"}
    ENABLED -->|No| USB["Wi-Fi disabled; USB CDC remains available"]
    ENABLED -->|Yes| CHECK{"Stored Wi-Fi credentials?"}
    CHECK -->|No| AUTO{"Automatic provisioning enabled?"}
    AUTO -->|No| USB
    AUTO -->|Yes| AP["Start PROV_WULPUS_PRO_XXXXXX SoftAP"]
    AP --> CREDS["Receive SSID and password"]
    CREDS --> TEST{"Association succeeds?"}
    TEST -->|No| AP
    TEST -->|Yes| STORE["Keep credentials in NVS"]
    CHECK -->|Yes| STA["Start Wi-Fi station"]
    STORE --> STA
    STA --> IP["Obtain IP address"]
    IP --> MDNS["Advertise wulpus_pro TCP service via mDNS"]
    IP --> TCP["Start TCP listener on port 2121"]
```

The persistent device configuration selects no, minimum-modem, or maximum-modem
Wi-Fi power saving. It also selects TWT; the firmware build must include
`CONFIG_PROVISIONER_TWT_ENABLED` for TWT to be available. TWT is suspended while
a WULPUS Pro Max protocol session is active.

`auto_provision` is a persistent policy and is not cleared after successful
provisioning. It is consulted only when Wi-Fi is enabled at boot and no saved
credentials exist. Saved credentials always take priority.

## Reprovisioning

When `CONFIG_WP_DOUBLE_RESET` is enabled, resetting the ESP32 twice within
`CONFIG_WP_DOUBLE_RESET_TIMEOUT` requests a provisioning reset. The default
timeout declared by the project is 2000 ms. On the second boot, stored Wi-Fi
provisioning state is cleared and the SoftAP workflow starts again.

Check the generated `sdkconfig` for the firmware being flashed. If it contains:

```text
# CONFIG_WP_DOUBLE_RESET is not set
```

the double-reset trigger is unavailable in that build.

Wi-Fi credentials can also be set or cleared over USB CDC using the PC protocol
commands. See the [host software documentation](../../../sw/README.md) for the
configuration interface. These operations update persistent storage, and
`RESET` applies the change. SSIDs and passwords cannot be read through the
protocol and are never written to firmware logs.

## USB operation during provisioning

USB CDC can be used even when:

- the device has never been provisioned;
- the configured access point is unavailable;
- the station is reconnecting; or
- the provisioning client is active.

A physical USB connection does not prevent later TCP use. Close the active USB
protocol session before connecting over TCP; see
[Firmware architecture](firmware_architecture.md#usb-and-wi-fi-session-switching).

## Troubleshooting

- **No device appears in Wi-Fi discovery:** confirm provisioning completed and
  the PC and ESP32 are on a network that permits mDNS and peer-to-peer TCP.
- **SoftAP does not appear:** credentials may already be stored. Check whether
  the build enables the double-reset trigger.
- **Provisioning repeatedly rejects credentials:** verify the SSID/password and
  ensure the access point is reachable by an ESP32-C6. With
  `CONFIG_PROVISIONER_RESET_ON_FAILURE`, the provisioning state machine resets
  after the configured number of failed attempts.
- **TCP reports `BUSY`:** another transport owns the WULPUS Pro Max protocol
  session. Close the USB session before retrying TCP.
