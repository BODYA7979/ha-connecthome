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
from homeassistant.helpers import entity_registry as er

from .api import ButlerApiClient
from .const import DOMAIN, PLATFORMS
from .coordinator import ButlerCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

    ButlerConfigEntry = ConfigEntry

_LOGGER = logging.getLogger(__name__)

_PREFIXES = ("sensor_", "binary_", "switch_", "light_", "cover_", "climate_", "lock_")


def _cleanup_orphaned_entities(hass: HomeAssistant, entry: ConfigEntry, valid_device_ids: set[int]) -> None:
    registry = er.async_get(hass)
    for entity in list(registry.entities.values()):
        if entity.config_entry_id != entry.entry_id:
            continue
        for prefix in _PREFIXES:
            if prefix in entity.unique_id:
                try:
                    device_id_str = entity.unique_id.split(prefix, 1)[1]
                    device_id = int(device_id_str)
                    if device_id not in valid_device_ids:
                        registry.async_remove(entity.entity_id)
                        _LOGGER.info("Removed orphaned entity: %s", entity.entity_id)
                except (ValueError, IndexError):
                    pass
                break


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

    coordinator = ButlerCoordinator(hass, client)
    coordinator.config_entry = entry
    await coordinator._async_setup()

    entry.runtime_data = coordinator

    async def _on_options_update(hass: HomeAssistant, entry: "ButlerConfigEntry") -> None:
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_on_options_update))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    valid_ids = {d["id"] for d in coordinator.data.get("devices", [])}
    _cleanup_orphaned_entities(hass, entry, valid_ids)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: "ButlerConfigEntry"
) -> bool:
    coordinator: ButlerCoordinator = entry.runtime_data
    await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        await coordinator.client.close()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant, entry: "ButlerConfigEntry"
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
