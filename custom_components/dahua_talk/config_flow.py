"""Thêm một camera: IP, tài khoản (cổng nói 37777) và URL tiếng mic."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from .const import CONF_MIC_URL, DEFAULT_PORT, DOMAIN
from .talk import AuthError, TalkError, check_login

_LOGGER = logging.getLogger(__name__)


def _schema(v: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_NAME, default=v.get(CONF_NAME, "")): str,
        vol.Required(CONF_HOST, default=v.get(CONF_HOST, "")): str,
        vol.Required(CONF_PORT, default=v.get(CONF_PORT, DEFAULT_PORT)): int,
        vol.Required(CONF_USERNAME, default=v.get(CONF_USERNAME, "admin")): str,
        vol.Required(CONF_PASSWORD, default=v.get(CONF_PASSWORD, "")): str,
        vol.Optional(CONF_MIC_URL, default=v.get(CONF_MIC_URL, "")): str,
    })


class DahuaTalkConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            mic = user_input.get(CONF_MIC_URL, "").strip()
            if mic and not mic.lower().startswith(("rtsp://", "http://", "https://")):
                errors[CONF_MIC_URL] = "invalid_mic_url"
            else:
                try:
                    # Đăng nhập thử MỘT lần: sai thì báo, không thử lại — camera khoá
                    # phiên sau vài lần sai.
                    await self.hass.async_add_executor_job(
                        check_login, user_input[CONF_HOST], user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD], user_input[CONF_PORT])
                except AuthError:
                    errors["base"] = "invalid_auth"
                except (TalkError, OSError) as exc:
                    _LOGGER.debug("dahua_talk login check failed: %s", exc)
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={**user_input, CONF_MIC_URL: mic})
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}),
                                    errors=errors)
