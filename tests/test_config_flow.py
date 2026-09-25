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


# ── Cấu hình lại: sửa IP / tài khoản / URL mic mà GIỮ khoá bộ đàm ──────────────────────

from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

KHOA = "khoa-bo-dam-cu"


async def _mo_sua(hass, **them):
    assert await async_setup_component(hass, "homeassistant", {})
    entry = MockConfigEntry(domain=DOMAIN, title="Cam cửa", unique_id="192.168.1.64:37777",
                            data={**NHAP, "intercom_key": KHOA, **them})
    entry.add_to_hass(hass)
    kq = await entry.start_reconfigure_flow(hass)
    assert kq["type"] is FlowResultType.FORM and kq["step_id"] == "reconfigure"
    # Mật khẩu cũ không được gửi ra form.
    assert "mk" not in str(kq["data_schema"]({}))
    return entry, kq["flow_id"]


def _sua(**doi):
    return {"host": NHAP["host"], "port": NHAP["port"], "username": NHAP["username"],
            "password": "", "mic_url": NHAP["mic_url"], **doi}


async def test_sua_url_mic_giu_khoa_khong_dang_nhap_lai(hass):
    entry, flow = await _mo_sua(hass, mic_url="")
    with mock.patch("custom_components.dahua_talk.config_flow.check_login") as dn, \
            mock.patch("custom_components.dahua_talk.async_setup_entry", return_value=True):
        kq = await hass.config_entries.flow.async_configure(flow, _sua())
    assert kq["type"] is FlowResultType.ABORT and kq["reason"] == "reconfigure_successful"
    dn.assert_not_called()
    assert entry.data["mic_url"] == NHAP["mic_url"]
    assert entry.data["intercom_key"] == KHOA and entry.data["password"] == "mk"


async def test_doi_ip_mat_khau_trong_dung_mat_khau_cu(hass):
    entry, flow = await _mo_sua(hass)
    with mock.patch("custom_components.dahua_talk.config_flow.check_login") as dn, \
            mock.patch("custom_components.dahua_talk.async_setup_entry", return_value=True):
        kq = await hass.config_entries.flow.async_configure(flow, _sua(host="192.168.1.65"))
    assert kq["reason"] == "reconfigure_successful"
    dn.assert_called_once_with("192.168.1.65", "admin", "mk", 37777)
    assert entry.unique_id == "192.168.1.65:37777" and entry.data["host"] == "192.168.1.65"
    assert entry.data["intercom_key"] == KHOA


async def test_sua_sai_mat_khau_khong_luu(hass):
    entry, flow = await _mo_sua(hass)
    with mock.patch("custom_components.dahua_talk.config_flow.check_login",
                    side_effect=AuthError("wrong password")):
        kq = await hass.config_entries.flow.async_configure(flow, _sua(password="sai"))
    assert kq["type"] is FlowResultType.FORM and kq["errors"] == {"base": "invalid_auth"}
    assert entry.data["password"] == "mk"


async def test_sua_trung_camera_khac(hass):
    MockConfigEntry(domain=DOMAIN, unique_id="192.168.1.70:37777", data={}).add_to_hass(hass)
    entry, flow = await _mo_sua(hass)
    with mock.patch("custom_components.dahua_talk.config_flow.check_login") as dn:
        kq = await hass.config_entries.flow.async_configure(flow, _sua(host="192.168.1.70"))
    assert kq["type"] is FlowResultType.ABORT and kq["reason"] == "already_configured"
    dn.assert_not_called()
    assert entry.data["host"] == "192.168.1.64"


async def test_sua_url_mic_sai(hass):
    entry, flow = await _mo_sua(hass)
    kq = await hass.config_entries.flow.async_configure(flow, _sua(mic_url="ftp://x"))
    assert kq["errors"] == {"mic_url": "invalid_mic_url"}


# ── Camera EZVIZ / Hikvision / ONVIF: nói qua kênh tiếng ngược RTSP ─────────────────────

async def test_them_camera_rtsp_cong_mac_dinh_thanh_554(hass):
    flow = await _mo(hass)
    with mock.patch("custom_components.dahua_talk.config_flow.check_rtsp_talk") as hoi, \
            mock.patch("custom_components.dahua_talk.config_flow.check_login") as dn, \
            mock.patch("custom_components.dahua_talk.async_setup_entry", return_value=True):
        kq = await hass.config_entries.flow.async_configure(
            flow, {**NHAP, "name": "Cam EZVIZ", "host": "192.168.1.203", "talk_protocol": "rtsp",
                   "rtsp_path": "Streaming/Channels/101"})
    assert kq["type"] is FlowResultType.CREATE_ENTRY
    assert kq["data"]["port"] == 554 and kq["data"]["rtsp_path"] == "/Streaming/Channels/101"
    hoi.assert_called_once_with("192.168.1.203", "admin", "mk", 554, "/Streaming/Channels/101")
    dn.assert_not_called()


async def test_rtsp_khong_co_kenh_nguoc_bao_rieng(hass):
    from custom_components.dahua_talk.rtsp_talk import NoBackchannelError
    flow = await _mo(hass)
    with mock.patch("custom_components.dahua_talk.config_flow.check_rtsp_talk",
                    side_effect=NoBackchannelError("x")):
        kq = await hass.config_entries.flow.async_configure(flow, {**NHAP, "talk_protocol": "rtsp"})
    assert kq["errors"] == {"base": "no_backchannel"}


def test_chon_phien_noi_theo_cau_hinh():
    from custom_components.dahua_talk import _mo_phien_noi
    from custom_components.dahua_talk.rtsp_talk import RtspTalkSession
    from custom_components.dahua_talk.talk import TalkSession
    cu = _mo_phien_noi({"host": "h", "port": 37777, "username": "u", "password": "p"})()
    assert isinstance(cu, TalkSession)                                  # mục cũ: Dahua
    moi = _mo_phien_noi({"host": "h", "port": 554, "username": "u", "password": "p",
                         "talk_protocol": "rtsp", "rtsp_path": "/Streaming/Channels/101"})()
    assert isinstance(moi, RtspTalkSession) and moi.url == "rtsp://h:554/Streaming/Channels/101"
