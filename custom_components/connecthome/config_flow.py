import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .api import ButlerApiClient, ButlerAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
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
