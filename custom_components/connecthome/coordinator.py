import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ButlerApiClient, ButlerApiError
from .const import (
    CONF_ENTITY_PREFIX,
    CONF_FORCE_REFRESH,
    CONF_POLL_ENABLED,
    CONF_POLL_INTERVAL,
    CONF_ROOM_NAME_IN_TITLE,
    CONF_SHOW_HIDDEN,
    DEFAULT_POLL_INTERVAL,
    DEVICE_TYPE_THERMOSTAT,
    DOMAIN,
    IFACE_MULTICHANNEL_ROOT,
    IFACE_PARENT_DEVICE,
    IFACE_THERMOSTAT_MODE,
    IFACE_THERMOSTAT_SETPOINT,
    PLATFORMS,
    POLL_EVENT_DEVICE_CHANGED,
    POLL_EVENT_DEVICE_LIST_CHANGED,
)

if TYPE_CHECKING:
    from . import ButlerConfigEntry

_LOGGER = logging.getLogger(__name__)


class ButlerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    config_entry: "ButlerConfigEntry"

    def __init__(
        self,
        hass: HomeAssistant,
        client: ButlerApiClient,
    ) -> None:
        self.client = client
        self._poll_task: asyncio.Task | None = None
        self._last_poll_index = 0

        update_interval = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.data: dict[str, Any] = {
            "devices": [],
            "rooms": [],
            "sections": [],
            "home": {},
        }

    def _read_options(self) -> None:
        options = dict(self.config_entry.options)
        self._options = {
            CONF_ROOM_NAME_IN_TITLE: options.get(CONF_ROOM_NAME_IN_TITLE, True),
            CONF_POLL_ENABLED: options.get(CONF_POLL_ENABLED, True),
            CONF_POLL_INTERVAL: options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            CONF_ENTITY_PREFIX: options.get(CONF_ENTITY_PREFIX, ""),
            CONF_FORCE_REFRESH: options.get(CONF_FORCE_REFRESH, True),
            CONF_SHOW_HIDDEN: options.get(CONF_SHOW_HIDDEN, False),
        }

    @property
    def force_refresh(self) -> bool:
        return self._options[CONF_FORCE_REFRESH]

    async def apply_options(self) -> None:
        self._read_options()
        update_interval = (
            None
            if self._options[CONF_POLL_ENABLED]
            else timedelta(seconds=self._options[CONF_POLL_INTERVAL])
        )
        self.update_interval = update_interval
        start_polling = self._options[CONF_POLL_ENABLED] and self._poll_task is None
        if not self._options[CONF_POLL_ENABLED]:
            if self._poll_task:
                self._poll_task.cancel()
                self._poll_task = None
        elif start_polling:
            _, self._last_poll_index = await self.client.get_poll(last=0)
        await self._async_refresh_devices()
        if start_polling:
            self._poll_task = self.hass.async_create_background_task(
                self._poll_loop(), f"{DOMAIN}_poll"
            )
        self.async_set_updated_data(self.data)

    async def _async_setup(self) -> None:
        self._read_options()
        update_interval = (
            None
            if self._options[CONF_POLL_ENABLED]
            else timedelta(seconds=self._options[CONF_POLL_INTERVAL])
        )
        self.update_interval = update_interval
        if self._options[CONF_POLL_ENABLED]:
            # Establish the cursor before taking a fresh snapshot. Replaying
            # /poll?last=0 can overwrite it with unordered historical changes.
            _, self._last_poll_index = await self.client.get_poll(last=0)
        await self._async_refresh_devices()
        if self._options[CONF_POLL_ENABLED]:
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
                    f"id={s['id']} Tripped={s.get('params', {}).get('Tripped')}"
                    for s in _sensors[:8]
                )
                _LOGGER.debug(
                    "INIT: loaded %d devices, sensors: %s", len(filtered), states
                )
        except ButlerApiError as err:
            raise UpdateFailed(f"Failed to fetch devices: {err}") from err

    def _filter_devices(
        self, devices: list[dict[str, Any]], rooms: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        room_by_id = {r["id"]: r for r in rooms}

        def _room_name(room_id: int | None) -> str | None:
            if room_id is None:
                return None
            room = room_by_id.get(room_id)
            if room and room.get("name") and room["name"] != "NAME_ROOM_NONE":
                return room["name"]
            return None

        show_hidden = self._options[CONF_SHOW_HIDDEN]
        add_room = self._options[CONF_ROOM_NAME_IN_TITLE]
        prefix = self._options[CONF_ENTITY_PREFIX]

        # Butler operates visible thermostat roots directly. A single hidden
        # thermostat endpoint must not replace that root with a separate cache.
        thermostat_roots = {
            device["id"]: device
            for device in devices
            if device.get("type") == DEVICE_TYPE_THERMOSTAT
            and not device.get("hidden", False)
            and (
                IFACE_MULTICHANNEL_ROOT in device.get("interfaces", [])
                or IFACE_PARENT_DEVICE in device.get("interfaces", [])
            )
            and (
                IFACE_THERMOSTAT_MODE in device.get("interfaces", [])
                or IFACE_THERMOSTAT_SETPOINT in device.get("interfaces", [])
            )
        }
        replacements = {}
        for root_id, root in thermostat_roots.items():
            root.pop("_legacy_climate_device_id", None)
            children = [
                device
                for device in devices
                if device.get("type") == DEVICE_TYPE_THERMOSTAT
                and device.get("params", {}).get("parentDeviceId") == root_id
            ]
            if len(children) == 1 and children[0].get("hidden", False):
                child_id = children[0]["id"]
                replacements[child_id] = root_id
                root["_legacy_climate_device_id"] = child_id

        filtered = []
        for device in devices:
            interfaces = device.get("interfaces", [])
            if (
                IFACE_MULTICHANNEL_ROOT in interfaces
                or IFACE_PARENT_DEVICE in interfaces
            ) and device["id"] not in thermostat_roots:
                continue
            if device["id"] in replacements:
                continue
            if not show_hidden and device.get("hidden", False):
                continue

            name = device.get("name", "")
            if add_room:
                room_name = _room_name(device.get("room_id"))
                if room_name:
                    name = f"{name} ({room_name})"
            if prefix:
                name = f"{prefix} {name}"

            device["_display_name"] = name
            filtered.append(device)
        return filtered

    async def _async_update_data(self) -> dict[str, Any]:
        await self._async_refresh_devices()
        return self.data

    async def refresh_device(self, device_id: int) -> None:
        try:
            fresh = await self.client.get_device(device_id)
            for i, dev in enumerate(self.data.get("devices", [])):
                if dev.get("id") == device_id:
                    dev["params"] = fresh.get("params", {})
                    dev["alive"] = fresh.get("alive", dev.get("alive"))
                    self.data["devices"][i] = dev
                    self.async_set_updated_data(self.data)
                    break
        except Exception:
            _LOGGER.debug(
                "Force refresh failed for device %d", device_id, exc_info=True
            )

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
                cursor_reset = new_last < self._last_poll_index
                if cursor_reset:
                    # A restarted Butler has a new event history. Its current
                    # snapshot is authoritative, rather than those old events.
                    await self._async_refresh_devices()
                    self._last_poll_index = new_last
                    self.async_set_updated_data(self.data)
                else:
                    self._last_poll_index = new_last
                    if events:
                        await self._handle_events(events)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.debug("POLL: error, will retry in 5s", exc_info=True)
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
                            "alive",
                            "name",
                            "role",
                            "room_id",
                            "hidden",
                            "icon",
                            "last_online",
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

    async def _apply_device_changes(self, changes: dict[int, dict[str, Any]]) -> None:
        devices = list(self.data.get("devices", []))
        rooms = self.data.get("rooms", [])
        room_by_id = {r["id"]: r for r in rooms}
        add_room = self._options[CONF_ROOM_NAME_IN_TITLE]
        prefix = self._options[CONF_ENTITY_PREFIX]

        def _calc_display_name(dev: dict[str, Any]) -> str:
            name = dev.get("name", "")
            if add_room:
                room_id = dev.get("room_id")
                if room_id:
                    room = room_by_id.get(room_id)
                    if room and room.get("name") and room["name"] != "NAME_ROOM_NONE":
                        name = f"{name} ({room['name']})"
            if prefix:
                name = f"{prefix} {name}"
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
                            device_id,
                            pname,
                            old_val,
                            new_val,
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
                f"id={s['id']} Tripped={s.get('params', {}).get('Tripped')}"
                for s in _sensors
            )
            _LOGGER.debug("AFTER: sensors=%s", states)
