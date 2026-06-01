import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import STATE_CLOSED, STATE_OPEN

from .const import (
    DEVICE_TYPE_SHUTTER,
    DOMAIN,
    IFACE_SHUTTER,
    IFACE_SWITCH_MULTILEVEL,
    PARAM_LEVEL,
)

if TYPE_CHECKING:
    from . import ButlerConfigEntry
    from .coordinator import ButlerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: Any,
    entry: "ButlerConfigEntry",
    async_add_entities: Any,
) -> None:
    coordinator: "ButlerCoordinator" = entry.runtime_data
    entities: list[ConnectHomeCover] = []

    for device in coordinator.data.get("devices", []):
        if device.get("type") != DEVICE_TYPE_SHUTTER:
            continue
        if IFACE_SHUTTER not in device.get("interfaces", []):
            continue

        stopable = device.get("params", {}).get("stopable", False)
        supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )
        if stopable:
            supported_features |= CoverEntityFeature.STOP

        entities.append(
            ConnectHomeCover(
                coordinator=coordinator,
                device_id=device["id"],
                name=device.get("_display_name", device.get("name", f"Shutter {device['id']}")),
                unique_id_suffix=f"cover_{device['id']}",
                supported_features=supported_features,
            )
        )

    async_add_entities(entities)


class ConnectHomeCover(CoverEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = CoverDeviceClass.SHUTTER

    def __init__(
        self,
        coordinator: "ButlerCoordinator",
        device_id: int,
        name: str,
        unique_id_suffix: str,
        supported_features: CoverEntityFeature,
    ) -> None:
        self.coordinator = coordinator
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id_suffix}"
        self._attr_supported_features = supported_features

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
    def current_cover_position(self) -> int | None:
        device = self._get_device()
        if device is None:
            return None
        level = device.get("params", {}).get(PARAM_LEVEL)
        if level is None:
            return None
        return min(100, max(0, int(level)))

    @property
    def is_closed(self) -> bool:
        position = self.current_cover_position
        if position is None:
            return False
        return position <= 5

    @property
    def is_opening(self) -> bool | None:
        return None

    @property
    def is_closing(self) -> bool | None:
        return None

    def _get_device(self) -> dict[str, Any] | None:
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self.coordinator.client.call_device_action(
            self._device_id, "startLevelChange", {"direction": "up"}
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self.coordinator.client.call_device_action(
            self._device_id, "startLevelChange", {"direction": "down"}
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self.coordinator.client.call_device_action(
            self._device_id, "stop"
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        position = kwargs.get("position", 0)
        level = min(100, max(0, int(position)))
        await self.coordinator.client.call_device_action(
            self._device_id, "setLevel", {"level": level}
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()
