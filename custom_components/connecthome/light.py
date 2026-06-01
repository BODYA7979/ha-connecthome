import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.util.color import color_rgb_to_rgbw

from .const import (
    DEVICE_TYPE_DIMMER,
    DEVICE_TYPE_DIMMER_COLOR,
    DOMAIN,
    IFACE_SWITCH_BINARY,
    IFACE_SWITCH_COLOR,
    IFACE_SWITCH_MULTILEVEL,
    PARAM_CURRENT_COMPONENT_VALUES,
    PARAM_LEVEL,
)

if TYPE_CHECKING:
    from . import ButlerConfigEntry
    from .coordinator import ButlerCoordinator

_LOGGER = logging.getLogger(__name__)

_LIGHT_TYPES = {DEVICE_TYPE_DIMMER, DEVICE_TYPE_DIMMER_COLOR}

_HA_BRIGHTNESS_MAX = 255
_BUTLER_LEVEL_MAX = 99


def _butler_level_to_brightness(level: int) -> int:
    return min(_HA_BRIGHTNESS_MAX, round(level / _BUTLER_LEVEL_MAX * _HA_BRIGHTNESS_MAX))


def _brightness_to_butler_level(brightness: int) -> int:
    return min(_BUTLER_LEVEL_MAX, round(brightness / _HA_BRIGHTNESS_MAX * _BUTLER_LEVEL_MAX))


def _butler_rgb_to_ha_rgbw(component_values: dict[str, int]) -> tuple[int, ...]:
    r = component_values.get("Red", 0) * 255 // 100
    g = component_values.get("Green", 0) * 255 // 100
    b = component_values.get("Blue", 0) * 255 // 100
    ww = component_values.get("WarmWhite", 0) * 255 // 100
    cw = component_values.get("ColdWhite", 0) * 255 // 100
    w = max(ww, cw)
    return color_rgb_to_rgbw(r, g, b, w)


def _ha_color_to_butler_components(
    rgb_color: tuple[int, ...] | None,
    brightness: int | None,
) -> dict[str, int]:
    components: dict[str, int] = {}
    if rgb_color:
        r, g, b = rgb_color[:3]
        components["Red"] = r * 100 // 255
        components["Green"] = g * 100 // 255
        components["Blue"] = b * 100 // 255
    if brightness is not None:
        w = brightness * 100 // 255
        components["WarmWhite"] = w
    return components


async def async_setup_entry(
    hass: Any,
    entry: "ButlerConfigEntry",
    async_add_entities: Any,
) -> None:
    coordinator: "ButlerCoordinator" = entry.runtime_data
    entities: list[ConnectHomeLight] = []

    for device in coordinator.data.get("devices", []):
        if device.get("type") not in _LIGHT_TYPES:
            continue
        interfaces = device.get("interfaces", [])
        if IFACE_SWITCH_MULTILEVEL not in interfaces:
            continue

        is_color = IFACE_SWITCH_COLOR in interfaces
        supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}
        if is_color:
            supported_color_modes.add(ColorMode.RGBW)

        entities.append(
            ConnectHomeLight(
                coordinator=coordinator,
                device_id=device["id"],
                name=device.get("_display_name", device.get("name", f"Light {device['id']}")),
                unique_id_suffix=f"light_{device['id']}",
                is_color=is_color,
                supported_color_modes=supported_color_modes,
            )
        )

    async_add_entities(entities)


class ConnectHomeLight(LightEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: "ButlerCoordinator",
        device_id: int,
        name: str,
        unique_id_suffix: str,
        is_color: bool,
        supported_color_modes: set[ColorMode],
    ) -> None:
        self.coordinator = coordinator
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id_suffix}"
        self._attr_supported_color_modes = supported_color_modes
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._is_color = is_color

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
        level = device.get("params", {}).get(PARAM_LEVEL, 0)
        return level > 0

    @property
    def brightness(self) -> int | None:
        device = self._get_device()
        if device is None:
            return None
        level = device.get("params", {}).get(PARAM_LEVEL, 0)
        return _butler_level_to_brightness(level)

    @property
    def rgbw_color(self) -> tuple[int, ...] | None:
        if not self._is_color:
            return None
        device = self._get_device()
        if device is None:
            return None
        components = device.get("params", {}).get(PARAM_CURRENT_COMPONENT_VALUES, {})
        if not components:
            return None
        return _butler_rgb_to_ha_rgbw(components)

    @property
    def color_mode(self) -> ColorMode:
        if self._is_color and self.rgbw_color:
            return ColorMode.RGBW
        return ColorMode.BRIGHTNESS

    def _get_device(self) -> dict[str, Any] | None:
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        params: dict[str, Any] = {}

        if ATTR_BRIGHTNESS in kwargs:
            params["level"] = _brightness_to_butler_level(kwargs[ATTR_BRIGHTNESS])
        elif not self.is_on:
            params["level"] = 99

        if self._is_color:
            color_params = _ha_color_to_butler_components(
                kwargs.get(ATTR_RGB_COLOR),
                kwargs.get(ATTR_BRIGHTNESS),
            )
            if color_params:
                params.update(color_params)

        if params:
            await self.coordinator.client.call_device_action(
                self._device_id, "setLevel", params
            )
        else:
            await self.coordinator.client.call_device_action(
                self._device_id, "setStatus", {"status": True}
            )
        if self.coordinator.force_refresh:
            await self.coordinator.refresh_device(self._device_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
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
