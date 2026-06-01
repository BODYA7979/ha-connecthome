import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
    LIGHT_LUX,
)

from .const import (
    DEVICE_TYPE_GENERIC_SENSOR,
    DEVICE_TYPE_HYGROMETRY,
    DEVICE_TYPE_LUMINOSITY,
    DEVICE_TYPE_METER,
    DEVICE_TYPE_TEMPERATURE,
    DOMAIN,
    HUMIDITY_SENSOR_TYPES,
    IFACE_SENSOR_MULTILEVEL,
    LUMINOSITY_SENSOR_TYPES,
    PARAM_SENSOR_TYPE,
    PARAM_VALUE,
    PARAM_VALUE_SCALE,
    PARAM_VALUE_UNIT,
    POWER_SENSOR_TYPES,
    TEMPERATURE_SENSOR_TYPES,
)

if TYPE_CHECKING:
    from . import ButlerConfigEntry
    from .coordinator import ButlerCoordinator

_LOGGER = logging.getLogger(__name__)

_SENSOR_TYPES = {
    DEVICE_TYPE_TEMPERATURE,
    DEVICE_TYPE_HYGROMETRY,
    DEVICE_TYPE_LUMINOSITY,
    DEVICE_TYPE_GENERIC_SENSOR,
    DEVICE_TYPE_METER,
}

_SENSOR_TYPE_CONFIG: list[tuple[frozenset[str], SensorDeviceClass | None, str | None, SensorStateClass | None]] = [
    (frozenset(TEMPERATURE_SENSOR_TYPES), SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT),
    (frozenset(HUMIDITY_SENSOR_TYPES), SensorDeviceClass.HUMIDITY, PERCENTAGE, SensorStateClass.MEASUREMENT),
    (frozenset(LUMINOSITY_SENSOR_TYPES), SensorDeviceClass.ILLUMINANCE, LIGHT_LUX, SensorStateClass.MEASUREMENT),
    (frozenset(POWER_SENSOR_TYPES), SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT),
]


def _resolve_sensor_config(sensor_type: str) -> tuple[SensorDeviceClass | None, str | None, SensorStateClass | None]:
    for types, dcls, unit, scls in _SENSOR_TYPE_CONFIG:
        if sensor_type in types:
            return (dcls, unit, scls)
    return (None, None, SensorStateClass.MEASUREMENT)

_VALUE_SCALE_UNIT_MAP = {
    "Celcius": UnitOfTemperature.CELSIUS,
    "Celsius": UnitOfTemperature.CELSIUS,
    "PercentageValue": PERCENTAGE,
}


async def async_setup_entry(
    hass: Any,
    entry: "ButlerConfigEntry",
    async_add_entities: Any,
) -> None:
    coordinator: "ButlerCoordinator" = entry.runtime_data
    entities: list[ConnectHomeSensor] = []

    for device in coordinator.data.get("devices", []):
        if device.get("type") not in _SENSOR_TYPES:
            continue
        if IFACE_SENSOR_MULTILEVEL not in device.get("interfaces", []):
            continue

        params = device.get("params", {})
        sensor_type = params.get(PARAM_SENSOR_TYPE, "")
        value = params.get(PARAM_VALUE)

        if value is None:
            continue

        device_class, unit, state_class = _resolve_sensor_config(sensor_type)

        if unit is None:
            unit = params.get(PARAM_VALUE_UNIT)
        if unit is None and params.get(PARAM_VALUE_SCALE):
            unit = _VALUE_SCALE_UNIT_MAP.get(params[PARAM_VALUE_SCALE])

        entities.append(
            ConnectHomeSensor(
                coordinator=coordinator,
                device_id=device["id"],
                name=device.get("_display_name", device.get("name", f"Sensor {device['id']}")),
                device_type=sensor_type,
                unique_id_suffix=f"sensor_{device['id']}",
                native_unit_of_measurement=unit,
                device_class=device_class,
                state_class=state_class,
            )
        )

    async_add_entities(entities)


class ConnectHomeSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: "ButlerCoordinator",
        device_id: int,
        name: str,
        device_type: str,
        unique_id_suffix: str,
        native_unit_of_measurement: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
    ) -> None:
        self.coordinator = coordinator
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id_suffix}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_state_class = state_class

    @property
    def name(self) -> str | None:
        device = self._get_device()
        if device is not None:
            return device.get("_display_name", device.get("name"))
        return self._attr_name

    @property
    def available(self) -> bool:
        device = self._get_device()
        if device is None:
            return False
        return bool(device.get("alive", False))

    @property
    def native_value(self) -> float | None:
        device = self._get_device()
        if device is None:
            return None
        return device.get("params", {}).get(PARAM_VALUE)

    def _get_device(self) -> dict[str, Any] | None:
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device
        return None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()
