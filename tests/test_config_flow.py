"""Thêm camera qua giao diện: đăng nhập thử một lần, lỗi thì báo đúng chỗ."""

from unittest import mock

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from custom_components.dahua_talk.const import DOMAIN
from custom_components.dahua_talk.talk import AuthError, TalkError

NHAP = {"name": "Cam cửa", "host": "192.168.1.64", "port": 37777, "username": "admin",
        "password": "mk", "mic_url": "http://192.168.1.10:1984/api/stream.mp4?src=front_sub&video=none&audio=all"}


async def _mo(hass):
    # assist_pipeline cần conversation, conversation cần lõi "homeassistant" dựng trước.
    assert await async_setup_component(hass, "homeassistant", {})
    kq = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert kq["type"] is FlowResultType.FORM
    return kq["flow_id"]


async def test_them_camera_thanh_cong(hass):
    flow = await _mo(hass)
    with mock.patch("custom_components.dahua_talk.config_flow.check_login") as dn, \
            mock.patch("custom_components.dahua_talk.async_setup_entry", return_value=True):
        kq = await hass.config_entries.flow.async_configure(flow, NHAP)
    assert kq["type"] is FlowResultType.CREATE_ENTRY
    assert kq["title"] == "Cam cửa" and kq["data"]["mic_url"] == NHAP["mic_url"]
    dn.assert_called_once_with("192.168.1.64", "admin", "mk", 37777)


async def test_sai_mat_khau_bao_invalid_auth(hass):
    flow = await _mo(hass)
    with mock.patch("custom_components.dahua_talk.config_flow.check_login",
                    side_effect=AuthError("login refused: wrong password")):
        kq = await hass.config_entries.flow.async_configure(flow, NHAP)
    assert kq["type"] is FlowResultType.FORM and kq["errors"] == {"base": "invalid_auth"}


async def test_khong_noi_duoc(hass):
    flow = await _mo(hass)
    with mock.patch("custom_components.dahua_talk.config_flow.check_login", side_effect=OSError("timed out")):
        kq = await hass.config_entries.flow.async_configure(flow, NHAP)
    assert kq["errors"] == {"base": "cannot_connect"}
    # Form báo lỗi vẫn mở — thử lại ngay trên đó như người dùng.
    with mock.patch("custom_components.dahua_talk.config_flow.check_login", side_effect=TalkError("x")):
        kq = await hass.config_entries.flow.async_configure(flow, NHAP)
    assert kq["errors"] == {"base": "cannot_connect"}


async def test_url_mic_sai_khong_dang_nhap_thu(hass):
    flow = await _mo(hass)
    with mock.patch("custom_components.dahua_talk.config_flow.check_login") as dn:
        kq = await hass.config_entries.flow.async_configure(flow, {**NHAP, "mic_url": "ftp://x"})
    assert kq["errors"] == {"mic_url": "invalid_mic_url"}
    dn.assert_not_called()
