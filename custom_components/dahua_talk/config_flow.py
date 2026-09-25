"""Thêm một camera: chọn LOẠI camera trước, rồi chỉ điền đúng những ô loại đó cần.

* **Imou / Dahua** — nói qua cổng 37777: IP, cổng, tài khoản, mật khẩu.
* **EZVIZ** — kênh tiếng ngược RTSP: chỉ IP và MÃ XÁC MINH (tài khoản luôn ``admin``, cổng
  554, luồng ``/Streaming/Channels/101`` — cố định với EZVIZ).
* **Hikvision / camera ONVIF khác** — kênh tiếng ngược RTSP: IP, cổng, đường dẫn luồng,
  tài khoản, mật khẩu.

Sửa sau khi thêm bằng "Cấu hình lại" — cùng các ô của đúng loại camera ấy, khoá bộ đàm giữ.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from .const import (CONF_LOAI, CONF_MIC_URL, CONF_RTSP_PATH, CONF_TALK, DEFAULT_PORT,
                    DEFAULT_RTSP_PATH, DEFAULT_RTSP_PORT, DOMAIN, LOAI_EZVIZ, LOAI_IMOU,
                    LOAI_ONVIF, TALK_DAHUA, TALK_RTSP)
from .rtsp_talk import NoBackchannelError, check_rtsp_talk
from .talk import AuthError, TalkError, check_login

_LOGGER = logging.getLogger(__name__)


def loai_cua(d: dict[str, Any]) -> str:
    """Loại camera của một mục; mục cũ (trước 0.2.1) suy ra từ cách nói."""
    return d.get(CONF_LOAI) or (LOAI_ONVIF if d.get(CONF_TALK) == TALK_RTSP else LOAI_IMOU)


def _schema(loai: str, v: dict[str, Any], *, sua: bool = False) -> vol.Schema:
    """Ô của đúng loại camera. ``sua``: mật khẩu KHÔNG điền sẵn (không gửi mật khẩu cũ ra
    trình duyệt), để trống là giữ cũ; tên đổi bằng "Đổi tên" của HA."""
    s: dict[Any, Any] = {}
    if not sua:
        s[vol.Required(CONF_NAME, default=v.get(CONF_NAME, ""))] = str
    s[vol.Required(CONF_HOST, default=v.get(CONF_HOST, ""))] = str
    if loai == LOAI_IMOU:
        s[vol.Required(CONF_PORT, default=v.get(CONF_PORT, DEFAULT_PORT))] = int
    elif loai == LOAI_ONVIF:
        s[vol.Required(CONF_PORT, default=v.get(CONF_PORT, DEFAULT_RTSP_PORT))] = int
        s[vol.Required(CONF_RTSP_PATH, default=v.get(CONF_RTSP_PATH, DEFAULT_RTSP_PATH))] = str
    if loai != LOAI_EZVIZ:
        s[vol.Required(CONF_USERNAME, default=v.get(CONF_USERNAME, "admin"))] = str
    if sua:
        s[vol.Optional(CONF_PASSWORD, default="")] = str
    else:
        s[vol.Required(CONF_PASSWORD, default=v.get(CONF_PASSWORD, ""))] = str
    s[vol.Optional(CONF_MIC_URL, default=v.get(CONF_MIC_URL, ""))] = str
    return vol.Schema(s)


def _day_du(loai: str, v: dict[str, Any]) -> dict[str, Any]:
    """Điền những gì loại camera đã cố định (cách nói, cổng, tài khoản, luồng)."""
    v = {**v, CONF_LOAI: loai}
    if loai == LOAI_IMOU:
        v[CONF_TALK] = TALK_DAHUA
        v.setdefault(CONF_PORT, DEFAULT_PORT)
        return v
    v[CONF_TALK] = TALK_RTSP
    if loai == LOAI_EZVIZ:
        v.update({CONF_USERNAME: "admin", CONF_PORT: DEFAULT_RTSP_PORT,
                  CONF_RTSP_PATH: DEFAULT_RTSP_PATH})
    duong = str(v.get(CONF_RTSP_PATH) or DEFAULT_RTSP_PATH).strip()
    v[CONF_RTSP_PATH] = duong if duong.startswith("/") else "/" + duong
    return v


def _url_mic(v: dict[str, Any]) -> str | None:
    """URL mic đã gọt; None nếu sai dạng."""
    mic = str(v.get(CONF_MIC_URL) or "").strip()
    if mic and not mic.lower().startswith(("rtsp://", "http://", "https://")):
        return None
    return mic


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
        return self.async_show_menu(step_id="user", menu_options=[LOAI_IMOU, LOAI_EZVIZ, LOAI_ONVIF])

    async def async_step_imou(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._them(LOAI_IMOU, user_input)

    async def async_step_ezviz(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._them(LOAI_EZVIZ, user_input)

    async def async_step_onvif(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._them(LOAI_ONVIF, user_input)

    async def _them(self, loai: str, user_input: dict[str, Any] | None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            v = _day_du(loai, user_input)
            await self.async_set_unique_id(f"{v[CONF_HOST]}:{v[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            if (mic := _url_mic(v)) is None:
                errors[CONF_MIC_URL] = "invalid_mic_url"
            elif await self._dang_nhap_thu(v, errors):
                return self.async_create_entry(title=v[CONF_NAME], data={**v, CONF_MIC_URL: mic})
        return self.async_show_form(step_id=loai, data_schema=_schema(loai, user_input or {}),
                                    errors=errors)

    async def async_step_reconfigure(
            self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Sửa IP / tài khoản / URL mic mà GIỮ khoá bộ đàm (dòng go2rtc đã dán vẫn đúng)."""
        entry = self._get_reconfigure_entry()
        loai = loai_cua(entry.data)
        errors: dict[str, str] = {}
        if user_input is not None:
            moi = _day_du(loai, {**entry.data, **user_input, CONF_PASSWORD:
                                 user_input.get(CONF_PASSWORD) or entry.data[CONF_PASSWORD]})
            uid = f"{moi[CONF_HOST]}:{moi[CONF_PORT]}"
            if uid != entry.unique_id:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()
            if (mic := _url_mic(moi)) is None:
                errors[CONF_MIC_URL] = "invalid_mic_url"
            elif (_ket_noi(moi) == _ket_noi(_day_du(loai, dict(entry.data)))
                  or await self._dang_nhap_thu(moi, errors)):
                # Chỉ đổi URL mic thì không đăng nhập lại camera.
                return self.async_update_reload_and_abort(
                    entry, unique_id=uid, data_updates={**moi, CONF_MIC_URL: mic})
        return self.async_show_form(
            step_id="reconfigure", data_schema=_schema(loai, user_input or dict(entry.data), sua=True),
            errors=errors, description_placeholders={"loai": loai})
