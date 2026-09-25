"""Thêm một camera: IP, tài khoản, cách nói (Dahua 37777 hay RTSP/ONVIF) và URL tiếng mic;
sửa lại bằng "Cấu hình lại"."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .const import (CONF_MIC_URL, CONF_RTSP_PATH, CONF_TALK, DEFAULT_PORT, DEFAULT_RTSP_PATH,
                    DEFAULT_RTSP_PORT, DOMAIN, TALK_DAHUA, TALK_RTSP)
from .rtsp_talk import NoBackchannelError, check_rtsp_talk
from .talk import AuthError, TalkError, check_login

_CACH_NOI = SelectSelector(SelectSelectorConfig(
    options=[TALK_DAHUA, TALK_RTSP], mode=SelectSelectorMode.LIST, translation_key=CONF_TALK))

_LOGGER = logging.getLogger(__name__)


def _schema(v: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_NAME, default=v.get(CONF_NAME, "")): str,
        vol.Required(CONF_HOST, default=v.get(CONF_HOST, "")): str,
        vol.Required(CONF_TALK, default=v.get(CONF_TALK, TALK_DAHUA)): _CACH_NOI,
        vol.Required(CONF_PORT, default=v.get(CONF_PORT, DEFAULT_PORT)): int,
        vol.Optional(CONF_RTSP_PATH, default=v.get(CONF_RTSP_PATH, DEFAULT_RTSP_PATH)): str,
        vol.Required(CONF_USERNAME, default=v.get(CONF_USERNAME, "admin")): str,
        vol.Required(CONF_PASSWORD, default=v.get(CONF_PASSWORD, "")): str,
        vol.Optional(CONF_MIC_URL, default=v.get(CONF_MIC_URL, "")): str,
    })


def _schema_sua(v: dict[str, Any]) -> vol.Schema:
    # Mật khẩu KHÔNG điền sẵn (không gửi mật khẩu cũ ra trình duyệt): để trống là giữ cũ.
    return vol.Schema({
        vol.Required(CONF_HOST, default=v.get(CONF_HOST, "")): str,
        vol.Required(CONF_TALK, default=v.get(CONF_TALK, TALK_DAHUA)): _CACH_NOI,
        vol.Required(CONF_PORT, default=v.get(CONF_PORT, DEFAULT_PORT)): int,
        vol.Optional(CONF_RTSP_PATH, default=v.get(CONF_RTSP_PATH, DEFAULT_RTSP_PATH)): str,
        vol.Required(CONF_USERNAME, default=v.get(CONF_USERNAME, "admin")): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
        vol.Optional(CONF_MIC_URL, default=v.get(CONF_MIC_URL, "")): str,
    })


def _url_mic(v: dict[str, Any]) -> str | None:
    """URL mic đã gọt; None nếu sai dạng."""
    mic = str(v.get(CONF_MIC_URL) or "").strip()
    if mic and not mic.lower().startswith(("rtsp://", "http://", "https://")):
        return None
    return mic


def _chuan_hoa(v: dict[str, Any]) -> dict[str, Any]:
    """Chọn RTSP mà để nguyên cổng 37777 mặc định thì hiểu là cổng RTSP 554."""
    v = {**v}
    v.setdefault(CONF_TALK, TALK_DAHUA)
    if v[CONF_TALK] == TALK_RTSP:
        if v.get(CONF_PORT) == DEFAULT_PORT:
            v[CONF_PORT] = DEFAULT_RTSP_PORT
        duong = str(v.get(CONF_RTSP_PATH) or DEFAULT_RTSP_PATH).strip()
        v[CONF_RTSP_PATH] = duong if duong.startswith("/") else "/" + duong
    return v


def _ket_noi(v: dict[str, Any]) -> tuple:
    """Những gì quyết định cách nói với camera — đổi thì phải đăng nhập thử lại."""
    t = (v.get(CONF_HOST), v.get(CONF_TALK), v.get(CONF_PORT), v.get(CONF_USERNAME),
         v.get(CONF_PASSWORD))
    return t + ((v.get(CONF_RTSP_PATH),) if v.get(CONF_TALK) == TALK_RTSP else ())


class DahuaTalkConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _dang_nhap_thu(self, v: dict[str, Any], errors: dict[str, str]) -> bool:
        # Đăng nhập thử MỘT lần: sai thì báo, không thử lại — camera khoá phiên sau vài
        # lần sai. RTSP thì chỉ hỏi camera có kênh ngược (DESCRIBE), không phát gì.
        try:
            if v[CONF_TALK] == TALK_RTSP:
                await self.hass.async_add_executor_job(
                    check_rtsp_talk, v[CONF_HOST], v[CONF_USERNAME], v[CONF_PASSWORD],
                    v[CONF_PORT], v[CONF_RTSP_PATH])
            else:
                await self.hass.async_add_executor_job(
                    check_login, v[CONF_HOST], v[CONF_USERNAME], v[CONF_PASSWORD], v[CONF_PORT])
        except AuthError:
            errors["base"] = "invalid_auth"
        except NoBackchannelError:
            errors["base"] = "no_backchannel"
        except (TalkError, OSError) as exc:
            _LOGGER.debug("dahua_talk login check failed: %s", exc)
            errors["base"] = "cannot_connect"
        return not errors

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = _chuan_hoa(user_input)
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            if (mic := _url_mic(user_input)) is None:
                errors[CONF_MIC_URL] = "invalid_mic_url"
            elif await self._dang_nhap_thu(user_input, errors):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={**user_input, CONF_MIC_URL: mic})
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}),
                                    errors=errors)

    async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Sửa IP / tài khoản / URL mic mà GIỮ khoá bộ đàm (dòng go2rtc đã dán vẫn đúng).

        Trước đây phải xoá rồi thêm lại camera: khoá mới, phải chép lại dòng exec vào
        go2rtc.yaml chỉ để sửa một ô.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            moi = _chuan_hoa({**user_input, CONF_PASSWORD: user_input.get(CONF_PASSWORD)
                              or entry.data[CONF_PASSWORD]})
            uid = f"{moi[CONF_HOST]}:{moi[CONF_PORT]}"
            if uid != entry.unique_id:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()
            if (mic := _url_mic(moi)) is None:
                errors[CONF_MIC_URL] = "invalid_mic_url"
            elif (_ket_noi(moi) == _ket_noi(_chuan_hoa(dict(entry.data)))
                  or await self._dang_nhap_thu(moi, errors)):
                # Chỉ đổi URL mic thì không đăng nhập lại camera.
                return self.async_update_reload_and_abort(
                    entry, unique_id=uid, data_updates={**moi, CONF_MIC_URL: mic})
        return self.async_show_form(step_id="reconfigure",
                                    data_schema=_schema_sua(user_input or dict(entry.data)),
                                    errors=errors)
