import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ButlerApiClient, ButlerApiError
from .const import (
    DOMAIN,
    IFACE_MULTICHANNEL_ROOT,
    IFACE_PARENT_DEVICE,
    PLATFORMS,
    POLL_EVENT_DEVICE_CHANGED,
    POLL_EVENT_DEVICE_LIST_CHANGED,
)

if TYPE_CHECKING:
    from . import ButlerConfigEntry

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


class ButlerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    config_entry: "ButlerConfigEntry"

    def __init__(
        self,
        hass: HomeAssistant,
        client: ButlerApiClient,
        poll_enabled: bool = True,
    ) -> None:
        self.client = client
        self._poll_enabled = poll_enabled
        self._poll_task: asyncio.Task | None = None
        self._last_poll_index = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL if not poll_enabled else None,
        )
        self.data = {
            "devices": [],
            "rooms": [],
            "sections": [],
            "home": {},
        }

    async def _async_setup(self) -> None:
        await self._async_refresh_devices()
        if self._poll_enabled:
            self._poll_task = self.hass.async_create_background_task(
                self._poll_loop(), f"{DOMAIN}_poll"
            )

    async def async_shutdown(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

    async def _async_refresh_devices(self) -> None:
        try:
            devices = await self.client.get_devices()
            rooms = await self.client.get_rooms()
            sections = await self.client.get_sections()
            filtered = self._filter_devices(devices, rooms)
            self.data = {
                "devices": filtered,
                "rooms": rooms,
                "sections": sections,
            }
            _sensors = [d for d in filtered if d.get("type") == "DevBinarySensor"]
            if _sensors:
                states = ", ".join(
                    f"id={s['id']} Tripped={s.get('params',{}).get('Tripped')}"
                    for s in _sensors[:8]
                )
                _LOGGER.debug("INIT: loaded %d devices, sensors: %s", len(filtered), states)
        except ButlerApiError as err:
            raise UpdateFailed(f"Failed to fetch devices: {err}") from err

    @staticmethod
    def _filter_devices(
        devices: list[dict[str, Any]], rooms: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        room_by_id = {r["id"]: r for r in rooms}

        def _room_name(room_id: int | None) -> str | None:
            if room_id is None:
                return None
            room = room_by_id.get(room_id)
            if room and room.get("name") and room["name"] != "NAME_ROOM_NONE":
                return room["name"]
            return None

        filtered = []
        for device in devices:
            interfaces = device.get("interfaces", [])
            if IFACE_MULTICHANNEL_ROOT in interfaces or IFACE_PARENT_DEVICE in interfaces:
                continue
            room_name = _room_name(device.get("room_id"))
            if room_name:
                device["_display_name"] = f"{device.get('name', '')} ({room_name})"
            else:
                device["_display_name"] = device.get("name", "")
            filtered.append(device)
        return filtered

    async def _async_update_data(self) -> dict[str, Any]:
        await self._async_refresh_devices()
        return self.data

    async def _poll_loop(self) -> None:
        _LOGGER.debug("POLL: started, last=%d", self._last_poll_index)
        while True:
            try:
                events, new_last = await self.client.get_poll(
                    last=self._last_poll_index
                )
                if events:
                    _LOGGER.debug(
                        "POLL: got %d events, last=%d→%d, types=%s",
                        len(events),
                        self._last_poll_index,
                        new_last,
                        [e.get("type") for e in events],
                    )
                self._last_poll_index = new_last
                if events:
                    await self._handle_events(events)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.debug(
                    "POLL: error, will retry in 5s", exc_info=True
                )
                await asyncio.sleep(5)

    async def _handle_events(self, events: list[dict[str, Any]]) -> None:
        device_list_changed = False
        device_changes: dict[int, dict[str, Any]] = {}

        for event in events:
            event_type = event.get("type")
            if event_type == POLL_EVENT_DEVICE_LIST_CHANGED:
                device_list_changed = True
            elif event_type == POLL_EVENT_DEVICE_CHANGED:
                device_id = event.get("device_id")
                if device_id is not None:
                    if device_id in device_changes:
                        existing = device_changes[device_id]
                        merged = dict(existing)
                        merged["params"] = existing.get("params", []) + event.get(
                            "params", []
                        )
                        for key in (
                            "alive", "name", "role", "room_id",
                            "hidden", "icon", "last_online",
                        ):
                            if key in event:
                                merged[key] = event[key]
                        device_changes[device_id] = merged
                    else:
                        device_changes[device_id] = event

        if device_list_changed:
            await self._async_refresh_devices()
            self.async_set_updated_data(self.data)
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setups(
                    self.config_entry, PLATFORMS
                )
            )
        elif device_changes:
            await self._apply_device_changes(device_changes)
            self.async_set_updated_data(self.data)

    async def _apply_device_changes(
        self, changes: dict[int, dict[str, Any]]
    ) -> None:
        devices = list(self.data.get("devices", []))
        rooms = self.data.get("rooms", [])
        room_by_id = {r["id"]: r for r in rooms}

        def _calc_display_name(dev: dict[str, Any]) -> str:
            name = dev.get("name", "")
            room_id = dev.get("room_id")
            if room_id:
                room = room_by_id.get(room_id)
                if room and room.get("name") and room["name"] != "NAME_ROOM_NONE":
                    return f"{name} ({room['name']})"
            return name

        for i, device in enumerate(devices):
            device_id = device.get("id")
            if device_id in changes:
                change = changes[device_id]
                recalc_name = False
                for key in (
                    "alive",
                    "hidden",
                    "role",
                    "icon",
                    "last_online",
                    "name",
                    "note_text",
                    "note_image",
                    "room_id",
                    "favorite",
                ):
                    if key in change:
                        device[key] = change[key]
                        if key in ("name", "room_id"):
                            recalc_name = True
                if "params" in change:
                    for param in change["params"]:
                        pname = param.get("name")
                        old_val = param.get("old_value")
                        new_val = param.get("new_value")
                        _LOGGER.debug(
                            "DEVICE: id=%d param=%s %s→%s",
                            device_id, pname, old_val, new_val,
                        )
                        if pname and pname in device.get("params", {}):
                            device["params"][pname] = new_val
                        elif pname:
                            device.setdefault("params", {})[pname] = new_val
                if recalc_name:
                    device["_display_name"] = _calc_display_name(device)
                devices[i] = device

        self.data["devices"] = devices
        _sensors = [d for d in devices if d.get("type") == "DevBinarySensor"]
        if _sensors:
            states = ", ".join(
                f"id={s['id']} Tripped={s.get('params',{}).get('Tripped')}"
                for s in _sensors
            )
            _LOGGER.debug("AFTER: sensors=%s", states)
