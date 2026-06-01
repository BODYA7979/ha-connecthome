import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import Platform

from .const import (
    DEVICE_TYPE_BINARY_SENSOR,
    DOMAIN,
    IFACE_SENSOR_BINARY,
    PARAM_TRIPPED,
)

if TYPE_CHECKING:
    from . import ButlerConfigEntry
    from .coordinator import ButlerCoordinator

_LOGGER = logging.getLogger(__name__)

_ROLE_DEVICE_CLASS_MAP: dict[str, BinarySensorDeviceClass] = {
    "BinaryMotionSensor": BinarySensorDeviceClass.MOTION,
    "BinarySmokeSensor": BinarySensorDeviceClass.SMOKE,
    "BinaryDoorSensor": BinarySensorDeviceClass.DOOR,
    "BinaryWindowSensor": BinarySensorDeviceClass.WINDOW,
    "BinaryLeakingSensor": BinarySensorDeviceClass.MOISTURE,
    "BinaryGenericSensor": BinarySensorDeviceClass.PROBLEM,
}


async def async_setup_entry(
    hass: Any,
    entry: "ButlerConfigEntry",
    async_add_entities: Any,
) -> None:
    coordinator: "ButlerCoordinator" = entry.runtime_data
    entities: list[ConnectHomeBinarySensor] = []

    for device in coordinator.data.get("devices", []):
        if device.get("type") != DEVICE_TYPE_BINARY_SENSOR:
            continue
        if IFACE_SENSOR_BINARY not in device.get("interfaces", []):
            continue

        role = device.get("role", "")
        device_class = _ROLE_DEVICE_CLASS_MAP.get(
            role, BinarySensorDeviceClass.PROBLEM
        )

        entities.append(
            ConnectHomeBinarySensor(
                coordinator=coordinator,
                device_id=device["id"],
                name=device.get("_display_name", device.get("name", f"Binary Sensor {device['id']}")),
                unique_id_suffix=f"binary_{device['id']}",
                device_class=device_class,
            )
        )

    async_add_entities(entities)


class ConnectHomeBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: "ButlerCoordinator",
        device_id: int,
        name: str,
        unique_id_suffix: str,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        self.coordinator = coordinator
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id_suffix}"
        self._attr_device_class = device_class

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
    def is_on(self) -> bool:
        device = self._get_device()
        if device is None:
            return False
        return bool(device.get("params", {}).get(PARAM_TRIPPED, False))

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
