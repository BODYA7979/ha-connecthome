import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.lock import LockEntity

from .const import (
    DEVICE_TYPE_DOOR_LOCK,
    DOMAIN,
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
    entities: list[ConnectHomeLock] = []

    for device in coordinator.data.get("devices", []):
        if device.get("type") != DEVICE_TYPE_DOOR_LOCK:
            continue

        params = device.get("params", {})
        locked = not params.get("Status", True)

        entities.append(
            ConnectHomeLock(
                coordinator=coordinator,
                device_id=device["id"],
                name=device.get("_display_name", device.get("name", f"Lock {device['id']}")),
                unique_id_suffix=f"lock_{device['id']}",
            )
        )

    async_add_entities(entities)


class ConnectHomeLock(LockEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: "ButlerCoordinator",
        device_id: int,
        name: str,
        unique_id_suffix: str,
    ) -> None:
        self.coordinator = coordinator
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id_suffix}"

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
    def is_locked(self) -> bool | None:
        device = self._get_device()
        if device is None:
            return None
        locked = device.get("params", {}).get("locked", True)
        status = device.get("params", {}).get("Status")
        if status is not None:
            return not status
        return locked

    def _get_device(self) -> dict[str, Any] | None:
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device
        return None

    async def async_lock(self, **kwargs: Any) -> None:
        await self.coordinator.client.call_device_action(
            self._device_id, "setStatus", {"status": True}
        )
        if self.coordinator.force_refresh:
            await self.coordinator.refresh_device(self._device_id)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.coordinator.client.call_device_action(
            self._device_id, "setStatus", {"status": False}
        )
        if self.coordinator.force_refresh:
            await self.coordinator.refresh_device(self._device_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()
