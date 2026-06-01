import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .api import ButlerApiClient, ButlerAuthError
from .const import (
    CONF_ENTITY_PREFIX,
    CONF_FORCE_REFRESH,
    CONF_POLL_ENABLED,
    CONF_POLL_INTERVAL,
    CONF_ROOM_NAME_IN_TITLE,
    CONF_SHOW_HIDDEN,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ROOM_NAME_IN_TITLE, default=True): bool,
        vol.Optional(CONF_POLL_ENABLED, default=True): bool,
        vol.Optional(
            CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
        ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
        vol.Optional(CONF_ENTITY_PREFIX, default=""): str,
        vol.Optional(CONF_FORCE_REFRESH, default=True): bool,
        vol.Optional(CONF_SHOW_HIDDEN, default=False): bool,
    }
)


class ConnectHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = ButlerApiClient(
                    host=user_input[CONF_HOST],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                await client.login()
                info = await client.get_info()
                await client.close()
            except ButlerAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    info.get("id", user_input[CONF_HOST])
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.get("name", "ConnectHome Butler"),
                    data=user_input,
                )

        discovered = await self._async_discover()
        discovered_text = ""
        if discovered:
            discovered.sort(key=lambda d: d.get("name", ""))
            discovered_text = "\n".join(
                f"{d['name']} ({d['ip']})" for d in discovered
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"discovered": discovered_text},
        )

    async def _async_discover(self) -> list[dict[str, Any]]:
        try:
            return await ButlerApiClient.discover_controllers()
        except Exception:
            _LOGGER.debug("Controller discovery failed", exc_info=True)
            return []

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return ConnectHomeOptionsFlow(config_entry)


class ConnectHomeOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self._config_entry.options
            ),
        )
