"""Thermostat selection and registry migration must follow Butler's visible device."""

import asyncio
from copy import deepcopy
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import frame

from custom_components.connecthome import _cleanup_orphaned_entities
from custom_components.connecthome.climate import async_setup_entry
from custom_components.connecthome.const import (
    CONF_ENTITY_PREFIX,
    CONF_FORCE_REFRESH,
    CONF_ROOM_NAME_IN_TITLE,
    CONF_SHOW_HIDDEN,
)
from custom_components.connecthome.coordinator import ButlerCoordinator


@pytest.fixture
def devices():
    return [
        {
            "id": 50,
            "type": "DevThermostat",
            "name": "Boiler",
            "hidden": False,
            "alive": True,
            "interfaces": ["MultichannelRoot", "ParentDevice", "ThermostatSetpoint"],
            "params": {
                "Value": 21.37,
                "currentMode": "Heat",
                "availableModes": ["Off", "Heat", "Cool", "Auto", "Heat", "Cool"],
                "currentSetpoints": {"Heat": 20.5},
            },
        },
        {
            "id": 51,
            "type": "DevThermostat",
            "name": "Boiler.1",
            "hidden": True,
            "interfaces": ["MultichannelEndpoint", "ThermostatSetpoint"],
            "params": {
                "parentDeviceId": 50,
                "endpointId": 1,
                "Value": 21.31,
                "currentMode": "Heat",
                "currentSetpoints": {"Heat": 21.5},
            },
        },
        {"id": 52, "type": "DevBinarySensor", "params": {"parentDeviceId": 50}},
    ]


def filtered(devices, show_hidden=True):
    coordinator = SimpleNamespace(
        _options={
            CONF_SHOW_HIDDEN: show_hidden,
            CONF_ROOM_NAME_IN_TITLE: False,
            CONF_ENTITY_PREFIX: "",
        }
    )
    return ButlerCoordinator._filter_devices(coordinator, devices, [])


@pytest.mark.parametrize("show_hidden", [False, True])
def test_visible_thermostat_root_replaces_single_hidden_endpoint(devices, show_hidden):
    result = filtered(devices, show_hidden)

    assert [d["id"] for d in result] == [50, 52]
    assert result[0]["_legacy_climate_device_id"] == 51
    assert result[0]["params"]["currentSetpoints"]["Heat"] == 20.5


def test_visible_thermostat_endpoint_remains_independent(devices):
    devices[1]["hidden"] = False

    assert [d["id"] for d in filtered(devices)] == [50, 51, 52]
    assert "_legacy_climate_device_id" not in devices[0]


def test_multiple_thermostat_endpoints_are_not_collapsed(devices):
    other_endpoint = deepcopy(devices[1])
    other_endpoint["id"] = 54
    other_endpoint["params"]["endpointId"] = 4
    devices.append(other_endpoint)

    assert [d["id"] for d in filtered(devices)] == [50, 51, 52, 54]
    assert "_legacy_climate_device_id" not in devices[0]


@pytest.mark.parametrize("show_hidden, expected", [(False, [52]), (True, [51, 52])])
def test_hidden_root_does_not_replace_endpoint(devices, show_hidden, expected):
    devices[0]["hidden"] = True

    assert [d["id"] for d in filtered(devices, show_hidden)] == expected


def test_generic_parent_filter_is_unchanged(devices):
    devices[0]["type"] = "DevSwitch"

    assert [d["id"] for d in filtered(devices)] == [51, 52]


def test_root_without_climate_controls_is_only_a_container(devices):
    devices[0]["interfaces"] = ["MultichannelRoot", "ParentDevice"]

    assert [d["id"] for d in filtered(devices)] == [51, 52]


@pytest.mark.parametrize("registry_conflict", [False, True])
def test_setup_preserves_entity_id_and_commands_use_root(
    devices, tmp_path, registry_conflict
):
    async def run():
        hass = HomeAssistant(str(tmp_path))
        frame.async_setup(hass)
        hass.config_entries = ConfigEntries(hass, {})
        dr.async_setup(hass)
        await dr.async_load(hass, load_empty=True)
        await er.async_load(hass, load_empty=True)
        registry = er.async_get(hass)
        entry = ConfigEntry(
            entry_id="test",
            domain="connecthome",
            title="Butler",
            source="user",
            data={},
            options={CONF_FORCE_REFRESH: False},
            version=1,
            minor_version=1,
            unique_id=None,
            discovery_keys=MappingProxyType({}),
            subentries_data=[],
        )
        hass.config_entries._entries[entry.entry_id] = entry
        legacy = registry.async_get_or_create(
            "climate",
            "connecthome",
            "test_climate_51",
            suggested_object_id="my_boiler",
            config_entry=entry,
        )
        registry.async_update_entity(legacy.entity_id, name="My custom name")
        if registry_conflict:
            registry.async_get_or_create("climate", "connecthome", "test_climate_50")
        coordinator = ButlerCoordinator(hass, AsyncMock())
        coordinator.config_entry = entry
        coordinator._read_options()
        coordinator.data = {"devices": filtered(devices), "rooms": []}
        entry.runtime_data = coordinator
        entities = []

        await async_setup_entry(hass, entry, entities.extend)

        preserved = registry.async_get(legacy.entity_id)
        assert preserved.name == "My custom name"
        assert preserved.unique_id == (
            "test_climate_51" if registry_conflict else "test_climate_50"
        )
        _cleanup_orphaned_entities(hass, entry, {50, 51, 52})
        assert registry.async_get(legacy.entity_id) is not None
        assert len(entities) == 1
        thermostat = entities[0]
        assert thermostat.unique_id == "test_climate_50"
        assert thermostat.current_temperature == 21.37
        assert thermostat.target_temperature == 20.5
        assert len(thermostat.hvac_modes) == 4

        await thermostat.async_set_temperature(temperature=21.5)
        coordinator.client.call_device_action.assert_awaited_once_with(
            50, "setSetpoint", {"setpoint": 21.5, "setpointType": "Heat"}
        )

        for device_id, value, expected in [(51, 21.5, 20.5), (50, 21, 21)]:
            await coordinator._handle_events(
                [
                    {
                        "type": "DeviceChanged",
                        "device_id": device_id,
                        "params": [
                            {"name": "currentSetpoints", "new_value": {"Heat": value}}
                        ],
                    }
                ]
            )
            assert thermostat.target_temperature == expected

    asyncio.run(run())
