"""A fresh Butler snapshot must not be overwritten by historical poll events."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame

from custom_components.connecthome.coordinator import ButlerCoordinator


def make_coordinator(tmp_path, poll_enabled=True):
    hass = HomeAssistant(str(tmp_path))
    frame.async_setup(hass)
    client = AsyncMock()
    client.get_devices.return_value = [
        {"id": 50, "type": "DevThermostat", "alive": True, "params": {}}
    ]
    client.get_rooms.return_value = []
    client.get_sections.return_value = []
    coordinator = ButlerCoordinator(hass, client)
    coordinator.config_entry = SimpleNamespace(options={"poll_enabled": poll_enabled})
    return coordinator, client


@pytest.mark.parametrize("poll_enabled", [False, True])
def test_setup_primes_cursor_before_snapshot(tmp_path, poll_enabled):
    async def run():
        coordinator, client = make_coordinator(tmp_path, poll_enabled)
        client.get_poll.return_value = (
            [{"type": "DeviceChanged", "device_id": 50, "alive": False}],
            38,
        )
        with patch.object(coordinator, "_poll_loop", new=AsyncMock()):
            await coordinator._async_setup()
            if poll_enabled:
                assert client.mock_calls[:2] == [
                    call.get_poll(last=0),
                    call.get_devices(),
                ]
                assert coordinator._last_poll_index == 38
            else:
                client.get_poll.assert_not_called()
            assert coordinator.data["devices"][0]["alive"] is True
            await coordinator.async_shutdown()

    asyncio.run(run())


def test_restarting_polling_primes_cursor_before_snapshot(tmp_path):
    async def run():
        coordinator, client = make_coordinator(tmp_path)
        client.get_poll.return_value = ([], 38)
        with patch.object(coordinator, "_poll_loop", new=AsyncMock()):
            await coordinator.apply_options()
            assert client.mock_calls[:2] == [
                call.get_poll(last=0),
                call.get_devices(),
            ]
            assert coordinator._last_poll_index == 38
            await coordinator.async_shutdown()

    asyncio.run(run())


def test_controller_cursor_reset_refreshes_instead_of_replaying_history(tmp_path):
    async def run():
        coordinator, client = make_coordinator(tmp_path)
        coordinator._read_options()
        coordinator._last_poll_index = 281232
        client.get_poll.side_effect = [
            ([{"type": "DeviceChanged", "device_id": 50, "alive": False}], 38),
            asyncio.CancelledError(),
        ]

        with pytest.raises(asyncio.CancelledError):
            await coordinator._poll_loop()

        client.get_devices.assert_awaited_once()
        assert coordinator._last_poll_index == 38
        assert coordinator.data["devices"][0]["alive"] is True

    asyncio.run(run())
