"""Regression tests for Butler thermostat temperature reporting."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame

from custom_components.connecthome.climate import ConnectHomeClimate
from custom_components.connecthome.const import (
    CONF_ENTITY_PREFIX,
    CONF_ROOM_NAME_IN_TITLE,
)
from custom_components.connecthome.coordinator import ButlerCoordinator


@pytest.fixture
def coordinator():
    """Use the temperature fields observed on Butler's thermostat endpoint."""
    return SimpleNamespace(
        config_entry=SimpleNamespace(entry_id="test"),
        data={
            "devices": [
                {
                    "id": 51,
                    "type": "DevThermostat",
                    "room_id": 4,
                    "alive": True,
                    "params": {
                        "Value": 21.25,
                        "sensorType": "AirTemperature",
                        "currentMode": "Heat",
                        "currentSetpoints": {"Auto": 23, "Cool": 24, "Heat": 22},
                    },
                },
                {"id": 60, "params": {"Value": 19.5}},
            ],
            "rooms": [
                {"id": 4, "main_devices": {"temperature_sensor": 60}},
            ],
        },
    )


@pytest.fixture
def climate(coordinator):
    return ConnectHomeClimate(
        coordinator=coordinator,
        device_id=51,
        name="Thermostat",
        unique_id_suffix="climate_51",
        hvac_modes=[HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO],
        supported_features=ClimateEntityFeature.TARGET_TEMPERATURE,
        has_setpoint=True,
    )


def test_thermostat_temperature_takes_priority_over_room_sensor(climate):
    assert climate.current_temperature == 21.25
    assert climate.target_temperature == 22


def test_thermostat_temperature_does_not_require_room(coordinator, climate):
    coordinator.data["devices"][0].pop("room_id")
    coordinator.data["rooms"] = []

    assert climate.current_temperature == 21.25


def test_zero_is_a_valid_measured_temperature(coordinator, climate):
    coordinator.data["devices"][0]["params"]["Value"] = 0

    assert climate.current_temperature == 0


@pytest.mark.parametrize("params", [{}, {"Value": None}])
def test_room_sensor_remains_a_fallback(coordinator, climate, params):
    coordinator.data["devices"][0]["params"] = params

    assert climate.current_temperature == 19.5


def test_missing_device_has_no_temperatures(coordinator, climate):
    coordinator.data["devices"] = []

    assert climate.current_temperature is None
    assert climate.target_temperature is None


@pytest.mark.parametrize(
    ("mode", "expected"), [("Heat", 22), ("Cool", 24), ("Auto", 23), ("Off", 22)]
)
def test_setpoint_matches_current_mode(coordinator, climate, mode, expected):
    coordinator.data["devices"][0]["params"]["currentMode"] = mode

    assert climate.target_temperature == expected


def test_zero_is_a_valid_setpoint(coordinator, climate):
    coordinator.data["devices"][0]["params"]["currentSetpoints"]["Heat"] = 0

    assert climate.target_temperature == 0


def test_setpoint_only_device_has_no_measured_temperature(coordinator, climate):
    coordinator.data["devices"][0]["params"].pop("Value")
    coordinator.data["rooms"] = []

    assert climate.current_temperature is None
    assert climate.target_temperature == 22


def test_poll_events_update_both_temperatures(coordinator, climate, tmp_path):
    async def run():
        hass = HomeAssistant(str(tmp_path))
        frame.async_setup(hass)
        real_coordinator = ButlerCoordinator(hass, AsyncMock())
        real_coordinator._options = {
            CONF_ROOM_NAME_IN_TITLE: False,
            CONF_ENTITY_PREFIX: "",
        }
        real_coordinator.data = coordinator.data
        climate.coordinator = real_coordinator
        climate.hass = hass

        await real_coordinator._handle_events(
            [
                {
                    "type": "DeviceChanged",
                    "device_id": 51,
                    "params": [{"name": "Value", "new_value": 21.5}],
                },
                {
                    "type": "DeviceChanged",
                    "device_id": 51,
                    "params": [
                        {"name": "currentSetpoints", "new_value": {"Heat": 22.5}},
                    ],
                },
            ]
        )

        assert climate.current_temperature == 21.5
        assert climate.target_temperature == 22.5
        assert climate.state_attributes["current_temperature"] == 21.5
        assert climate.state_attributes["temperature"] == 22.5

    asyncio.run(run())
