import asyncio
import json
import logging
import socket
from typing import Any

import aiohttp

from .const import DISCOVERY_MESSAGE, DISCOVERY_PORT, DISCOVERY_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class ButlerApiError(Exception):
    pass


class ButlerAuthError(ButlerApiError):
    pass


class ButlerApiClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._host = host.rstrip("/")
        self._username = username
        self._password = password
        self._base_url = f"http://{self._host}/api/v2"
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._session = session
        self._own_session = False

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    def _auth_headers(self) -> dict[str, str]:
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        _is_retry: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        session = await self._ensure_session()
        url = f"{self._base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers.update(self._auth_headers())

        async with session.request(
            method, url, headers=headers, **kwargs
        ) as resp:
            data = await resp.json()
            if resp.status == 401:
                if self._refresh_token and not _is_retry:
                    await self._do_refresh()
                    return await self._request(
                        method, path, _is_retry=True, **kwargs
                    )
                raise ButlerAuthError(
                    data.get("errorMessage", "Authentication failed")
                )
            if resp.status >= 400:
                raise ButlerApiError(
                    data.get("errorMessage", f"HTTP {resp.status}")
                )
            return data

    async def login(self) -> None:
        session = await self._ensure_session()
        import base64

        credentials = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode()
        url = f"{self._base_url}/auth/login"
        body = {
            "client": {
                "id": "ha-connecthome",
                "name": "Home Assistant",
                "type": "other",
                "push_type": "Any",
            }
        }

        async with session.post(
            url,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            json=body,
        ) as resp:
            data = await resp.json()
            if resp.status != 200 or not data.get("success"):
                raise ButlerAuthError(
                    data.get("errorMessage", "Login failed")
                )
            self._token = data["token"]
            self._refresh_token = data["refresh_token"]
            _LOGGER.debug("Login successful")

    async def _do_refresh(self) -> None:
        if not self._refresh_token:
            raise ButlerAuthError("No refresh token available")
        session = await self._ensure_session()
        url = f"{self._base_url}/auth/get-new-access-token"
        params = {"token": self._refresh_token}

        async with session.post(url, params=params) as resp:
            data = await resp.json()
            if resp.status != 200 or not data.get("success"):
                self._token = None
                self._refresh_token = None
                raise ButlerAuthError("Token refresh failed")
            self._token = data.get("token", self._token)
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            _LOGGER.debug("Token refreshed")

    async def get_devices(
        self,
        show_hidden: bool = False,
        compact: bool = False,
        with_actions: bool = False,
    ) -> list[dict[str, Any]]:
        params = {
            "show_hidden": str(show_hidden).lower(),
            "compact": str(compact).lower(),
            "with_actions": str(with_actions).lower(),
            "fields": "all",
        }
        result = await self._request("GET", "/devices", params=params)
        if isinstance(result, dict):
            return result.get("devices", [])
        return result

    async def get_device(self, device_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/devices/{device_id}")

    async def get_device_actions(self, device_id: int) -> list[dict[str, Any]]:
        result = await self._request("GET", f"/devices/{device_id}/actions")
        if isinstance(result, dict):
            return result.get("actions", [])
        return result

    async def call_device_action(
        self, device_id: int, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"method": method}
        if params:
            body["params"] = params
        return await self._request(
            "POST", f"/devices/{device_id}/actions", json=body
        )

    async def get_rooms(self) -> list[dict[str, Any]]:
        result = await self._request("GET", "/rooms")
        if isinstance(result, dict):
            return result.get("rooms", [])
        return result

    async def get_sections(self) -> list[dict[str, Any]]:
        result = await self._request("GET", "/sections")
        if isinstance(result, dict):
            return result.get("sections", [])
        return result

    async def get_home_structure(self) -> dict[str, Any]:
        result = await self._request("GET", "/home")
        if isinstance(result, dict) and "home" in result:
            return result["home"]
        return result

    async def get_system(self) -> dict[str, Any]:
        result = await self._request("GET", "/system")
        if isinstance(result, dict):
            return result
        return {}

    async def get_poll(self, last: int | None = None) -> tuple[list[dict[str, Any]], int]:
        params = {}
        if last is not None:
            params["last"] = last
        result = await self._request("GET", "/poll", params=params)
        if isinstance(result, dict):
            events = result.get("events", [])
            new_last = result.get("last", last or 0)
            return events, new_last
        return [], last or 0

    async def get_info(self) -> dict[str, Any]:
        return await self._request("GET", "/info")

    async def get_parameter_history(
        self, device_id: int, param_name: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        params = {"param": param_name, "limit": limit}
        result = await self._request(
            "GET", f"/devices/{device_id}/parameter-history", params=params
        )
        if isinstance(result, dict):
            return result.get("history", [])
        return result

    @staticmethod
    async def discover_controllers() -> list[dict[str, Any]]:
        controllers: list[dict[str, Any]] = []
        loop = asyncio.get_event_loop()

        class DiscoveryProtocol(asyncio.DatagramProtocol):
            def __init__(self):
                self.transport = None

            def connection_made(self, transport):
                self.transport = transport

            def datagram_received(self, data, addr):
                try:
                    info = json.loads(data.decode())
                    controllers.append(info)
                    _LOGGER.debug("Discovered controller: %s", info)
                except Exception:
                    pass

        transport, protocol = await loop.create_datagram_endpoint(
            DiscoveryProtocol, local_addr=("0.0.0.0", 0)
        )

        sock = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        listen_port = sock.getsockname()[1]
        message = f"{DISCOVERY_MESSAGE}{listen_port}".encode()
        transport.sendto(message, ("255.255.255.255", DISCOVERY_PORT))

        await asyncio.sleep(DISCOVERY_TIMEOUT)
        transport.close()

        return controllers
