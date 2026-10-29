<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/connecthome/brand/dark_logo@2x.png">
    <source media="(prefers-color-scheme: light)" srcset="custom_components/connecthome/brand/logo@2x.png">
    <img src="custom_components/connecthome/brand/logo@2x.png" alt="ConnectHome" width="280">
  </picture>
</p>

<h1 align="center">ConnectHome Butler</h1>

<p align="center">
  Connect your <a href="https://c-home.ua/">Butler smart home controller</a> to <a href="https://www.home-assistant.io/">Home Assistant</a>.<br>
  Local control &nbsp;·&nbsp; Live updates &nbsp;·&nbsp; Automatic discovery
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-orange?style=flat-square" alt="HACS custom integration"></a>
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-2024.1%2B-18BCF2?style=flat-square&amp;logo=home-assistant&amp;logoColor=white" alt="Home Assistant 2024.1 or later"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-3d5ba7?style=flat-square" alt="MIT license"></a>
</p>

<p align="center">
  <strong>English</strong> &nbsp;·&nbsp; <a href="README_UA.md">Українська</a><br>
  <a href="#installation">Installation</a> &nbsp;·&nbsp; <a href="#supported-devices">Supported devices</a> &nbsp;·&nbsp; <a href="https://github.com/BODYA7979/ha-connecthome/issues">Report an issue</a>
</p>

<details>
<summary>Unofficial community integration — disclaimer</summary>

This is an unofficial community integration made by an enthusiast. It is not affiliated with, endorsed by, or connected to ConnectHome or Home Assistant. Use at your own risk. The author assumes no responsibility for any damage, data loss, or other issues caused by using this integration.

</details>

## Features

- **All device types**: switches, dimmers, RGB lights, shutters, thermostats, door locks, temperature/humidity/illuminance sensors, motion/door/window/smoke sensors
- **Real-time updates**: long-polling via Butler API, state changes appear in < 1 second
- **Auto-discovery**: UDP broadcast detection of Butler controllers on your local network
- **Room mapping**: device names include room context (e.g. "Light Switch (Kitchen)")
- **Live rename/add/remove**: changes made in Butler app propagate to HA automatically

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → ⋮ → **Custom repositories**
3. Paste `https://github.com/BODYA7979/ha-connecthome` → Category: **Integration**
4. Click **Download**
5. Restart Home Assistant

### Manual

```bash
cd /config/custom_components
git clone https://github.com/BODYA7979/ha-connecthome.git connecthome
# Restart Home Assistant
```

## Setup

1. Settings → Devices & Services → Add Integration
2. Search for **ConnectHome Butler**
3. Enter your Butler controller IP, username, and password
4. If controllers are discovered automatically, they'll be listed on the setup screen

## Supported Devices

| Butler Device Type | Home Assistant Entity |
|---|---|
| DevSwitch | `switch` |
| DevDimmer | `light` (brightness) |
| DevDimmerColor | `light` (RGBW) |
| DevShutter | `cover` (shutter, position control) |
| DevBinarySensor | `binary_sensor` (motion, door, window, smoke, leak) |
| DevTemperature | `sensor` (temperature) |
| DevHygrometry | `sensor` (humidity) |
| DevLuminosity | `sensor` (illuminance) |
| DevGenericSensor | `sensor` |
| DevThermostat | `climate` (mode, setpoint, operating state) |
| DevDoorLock | `lock` |
| DevMeter | `sensor` (power) |

## Requirements

- Home Assistant 2024.1.0+
- ConnectHome Butler controller with firmware 0.9+
- Integration icons and logos in the Home Assistant UI require Home Assistant 2026.3+.

## Known limitations

Not all device types have been tested on real hardware, as the author does not own every type of Butler-compatible device. If something doesn't work — please [open an Issue](https://github.com/BODYA7979/ha-connecthome/issues), or even better, submit a Pull Request with a fix.

## Development

```bash
# Syntax check
for f in custom_components/connecthome/*.py; do python3 -c "import ast; ast.parse(open('$f').read())" && echo "OK $f"; done

# Enable debug logging (in configuration.yaml)
logger:
  logs:
    custom_components.connecthome: debug
```

## License

[MIT](LICENSE)
