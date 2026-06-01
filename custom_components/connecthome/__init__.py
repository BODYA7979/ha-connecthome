import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import ButlerApiClient
from .const import DOMAIN, PLATFORMS
from .coordinator import ButlerCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

    class ButlerConfigEntry(ConfigEntry):
        runtime_data: ButlerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: "ConfigType") -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: "ButlerConfigEntry"
) -> bool:
    client = ButlerApiClient(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await client.login()
    except Exception as err:
        await client.close()
        raise ConfigEntryNotReady(f"Failed to login: {err}") from err

    coordinator = ButlerCoordinator(hass, client, poll_enabled=True)
    await coordinator._async_setup()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: "ButlerConfigEntry"
) -> bool:
    coordinator = entry.runtime_data
    await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        await coordinator.client.close()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
