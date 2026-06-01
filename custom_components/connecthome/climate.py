import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import (
    DEVICE_TYPE_THERMOSTAT,
    DOMAIN,
    IFACE_THERMOSTAT_MODE,
    IFACE_THERMOSTAT_OPERATING_STATE,
    IFACE_THERMOSTAT_SETPOINT,
    PARAM_AVAILABLE_MODES,
    PARAM_CURRENT_MODE,
    PARAM_CURRENT_SETPOINTS,
    PARAM_CURRENT_STATE,
)

if TYPE_CHECKING:
    from . import ButlerConfigEntry
    from .coordinator import ButlerCoordinator

_LOGGER = logging.getLogger(__name__)

_BUTLER_MODE_TO_HVAC: dict[str, HVACMode] = {
    "Off": HVACMode.OFF,
    "Heat": HVACMode.HEAT,
    "Cool": HVACMode.COOL,
    "Auto": HVACMode.AUTO,
}

_HVAC_TO_BUTLER_MODE: dict[HVACMode, str] = {
    v: k for k, v in _BUTLER_MODE_TO_HVAC.items()
}

_BUTLER_STATE_TO_ACTION: dict[str, HVACAction] = {
    "Idle": HVACAction.IDLE,
    "Heating": HVACAction.HEATING,
    "Cooling": HVACAction.COOLING,
}


async def async_setup_entry(
    hass: Any,
    entry: "ButlerConfigEntry",
    async_add_entities: Any,
) -> None:
    coordinator: "ButlerCoordinator" = entry.runtime_data
    entities: list[ConnectHomeClimate] = []

    for device in coordinator.data.get("devices", []):
        if device.get("type") != DEVICE_TYPE_THERMOSTAT:
            continue
        interfaces = device.get("interfaces", [])
        has_mode = IFACE_THERMOSTAT_MODE in interfaces
        has_setpoint = IFACE_THERMOSTAT_SETPOINT in interfaces

        if not has_mode and not has_setpoint:
            continue

        params = device.get("params", {})
        raw_modes = params.get(PARAM_AVAILABLE_MODES, [])
        hvac_modes: list[HVACMode] = []
        for mode_name in raw_modes:
            hvac = _BUTLER_MODE_TO_HVAC.get(mode_name)
            if hvac:
                hvac_modes.append(hvac)

        if not hvac_modes:
            hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]

        supported_features = ClimateEntityFeature(0)
        if has_setpoint:
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        entities.append(
            ConnectHomeClimate(
                coordinator=coordinator,
                device_id=device["id"],
                name=device.get("_display_name", device.get("name", f"Thermostat {device['id']}")),
                unique_id_suffix=f"climate_{device['id']}",
                hvac_modes=hvac_modes,
                supported_features=supported_features,
                has_setpoint=has_setpoint,
            )
        )

    async_add_entities(entities)


class ConnectHomeClimate(ClimateEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: "ButlerCoordinator",
        device_id: int,
        name: str,
        unique_id_suffix: str,
        hvac_modes: list[HVACMode],
        supported_features: ClimateEntityFeature,
        has_setpoint: bool,
    ) -> None:
        self.coordinator = coordinator
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id_suffix}"
        self._attr_hvac_modes = hvac_modes
        self._attr_supported_features = supported_features
        self._has_setpoint = has_setpoint

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
    def hvac_mode(self) -> HVACMode | None:
        device = self._get_device()
        if device is None:
            return None
        mode = device.get("params", {}).get(PARAM_CURRENT_MODE, "")
        return _BUTLER_MODE_TO_HVAC.get(mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction | None:
        device = self._get_device()
        if device is None:
            return None
        state = device.get("params", {}).get(PARAM_CURRENT_STATE, "")
        return _BUTLER_STATE_TO_ACTION.get(state)

    @property
    def current_temperature(self) -> float | None:
        device = self._get_device()
        if device is None:
            return None
        room_id = device.get("room_id")
        if room_id is None:
            return None
        for room in self.coordinator.data.get("rooms", []):
            if room.get("id") == room_id:
                temp_sensor_id = room.get("main_devices", {}).get("temperature_sensor")
                if temp_sensor_id:
                    for d in self.coordinator.data.get("devices", []):
                        if d.get("id") == temp_sensor_id:
                            return d.get("params", {}).get("Value")
        return None

    @property
    def target_temperature(self) -> float | None:
        if not self._has_setpoint:
            return None
        device = self._get_device()
        if device is None:
            return None
        setpoints = device.get("params", {}).get(PARAM_CURRENT_SETPOINTS, {})
        if isinstance(setpoints, dict):
            return setpoints.get("Heat") or setpoints.get("Cool")
        return None

    @property
    def target_temperature_step(self) -> float:
        return 0.5

    def _get_device(self) -> dict[str, Any] | None:
        for device in self.coordinator.data.get("devices", []):
            if device.get("id") == self._device_id:
                return device
        return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        butler_mode = _HVAC_TO_BUTLER_MODE.get(hvac_mode, "Off")
        await self.coordinator.client.call_device_action(
            self._device_id, "setMode", {"mode": butler_mode}
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if ATTR_TEMPERATURE in kwargs:
            temp = kwargs[ATTR_TEMPERATURE]
            mode = self.hvac_mode or HVACMode.HEAT
            butler_mode = _HVAC_TO_BUTLER_MODE.get(mode, "Heat")
            await self.coordinator.client.call_device_action(
                self._device_id,
                "setSetpoint",
                {"setpoint": temp, "setpointType": butler_mode},
            )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()
