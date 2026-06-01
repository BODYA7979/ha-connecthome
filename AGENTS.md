# AGENTS.md

## Project

Home Assistant custom integration for ConnectHome Butler smart home controller.

## Stack

- **Language**: Python 3.12+
- **Runtime**: Home Assistant (pip package `homeassistant`)
- **HTTP client**: `aiohttp`
- **No external dependencies** beyond HA built-ins

## Project structure

```
custom_components/connecthome/
├── __init__.py          # Domain setup/teardown, config entry lifecycle
├── manifest.json        # HA integration metadata
├── config_flow.py       # UI setup flow with UDP auto-discovery
├── const.py             # All constants (device types, interfaces, params)
├── api.py               # Async Butler API client (auth, devices, actions, poll)
├── coordinator.py       # DataUpdateCoordinator with long-polling
├── sensor.py            # SensorEntity for temperature, humidity, illuminance, power
├── binary_sensor.py     # BinarySensorEntity for motion, door, window, smoke, leak
├── switch.py            # SwitchEntity for DevSwitch
├── light.py             # LightEntity for DevDimmer, DevDimmerColor
├── cover.py             # CoverEntity for DevShutter
├── climate.py           # ClimateEntity for DevThermostat
├── lock.py              # LockEntity for DevDoorLock
├── strings.json         # Config flow UI strings
└── translations/en.json # English translations
```

## Conventions

- Entity classes use `_attr_has_entity_name = True` and `_attr_should_poll = False`
- Coordinator handles ALL data updates; entities only read from `coordinator.data`
- Entity `name` is a dynamic property that reads `_display_name` from coordinator data
- Filtering of multichannel parent devices happens in `coordinator._filter_devices()`
- Real-time updates via long-polling `GET /poll` with background task

## Butler API

- Base URL: `http://{controller-ip}/api/v2/`
- Auth: Basic → Bearer token via `POST /auth/login`
- Devices: `GET /devices`, actions: `POST /devices/{id}/actions`
- Long-poll: `GET /poll?last=N` returns events with `"last"` index
- Device types map to HA entities via `const.py` constants

## Testing

Deploy via SMB or scp to a real HA instance:
```bash
cp -r custom_components/connecthome /path/to/ha/config/custom_components/
# Then restart HA
```

The SMB share is typically mounted at `/Volumes/config` on macOS or `\\homeassistant\config` on Windows.

Enable debug logging in `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.connecthome: debug
```

## Key patterns

- `coordinator._handle_events` merges multiple `DeviceChanged` events for the same device (params concatenation)
- `DeviceListChanged` triggers full platform reload via `async_forward_entry_setups`
- `cover.py` direct position mapping (Butler Level 0-100 = HA position 0-100, no inversion)
- Action names from real API: `setStatus`, `setLevel`, `startLevelChange`, `setMode`, `setSetpoint`
