"""Thêm camera qua giao diện: đăng nhập thử một lần, lỗi thì báo đúng chỗ."""

from unittest import mock

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from custom_components.dahua_talk.const import DOMAIN
from custom_components.dahua_talk.talk import AuthError, TalkError

NHAP = {"name": "Cam cửa", "host": "192.168.1.64", "port": 37777, "username": "admin",
        "password": "mk", "mic_url": "http://192.168.1.10:1984/api/stream.mp4?src=front_sub&video=none&audio=all"}


async def _mo(hass, loai="imou"):
    # assist_pipeline cần conversation, conversation cần lõi "homeassistant" dựng trước.
    assert await async_setup_component(hass, "homeassistant", {})
    kq = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert kq["type"] is FlowResultType.MENU and kq["menu_options"] == ["imou", "ezviz", "onvif"]
    kq = await hass.config_entries.flow.async_configure(kq["flow_id"], {"next_step_id": loai})
    assert kq["type"] is FlowResultType.FORM and kq["step_id"] == loai
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

async def test_ezviz_chi_hoi_ip_va_ma_xac_minh(hass):
    flow = await _mo(hass, "ezviz")
    with mock.patch("custom_components.dahua_talk.config_flow.check_rtsp_talk") as hoi, \
            mock.patch("custom_components.dahua_talk.config_flow.check_login") as dn, \
            mock.patch("custom_components.dahua_talk.async_setup_entry", return_value=True):
        kq = await hass.config_entries.flow.async_configure(
            flow, {"name": "Cam EZVIZ", "host": "192.168.1.203", "password": "ABCDEF"})
    assert kq["type"] is FlowResultType.CREATE_ENTRY
    d = kq["data"]
    assert (d["camera_type"], d["talk_protocol"], d["port"], d["username"], d["rtsp_path"]) == \
        ("ezviz", "rtsp", 554, "admin", "/Streaming/Channels/101")
    hoi.assert_called_once_with("192.168.1.203", "admin", "ABCDEF", 554, "/Streaming/Channels/101")
    dn.assert_not_called()


async def test_form_ezviz_khong_co_o_tai_khoan_cong(hass):
    assert await async_setup_component(hass, "homeassistant", {})
    kq = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    kq = await hass.config_entries.flow.async_configure(kq["flow_id"], {"next_step_id": "ezviz"})
    o = [str(k) for k in kq["data_schema"].schema]
    assert o == ["name", "host", "password", "nghe_mic", "mic_url"]


async def test_onvif_khong_co_kenh_nguoc_bao_rieng(hass):
    from custom_components.dahua_talk.rtsp_talk import NoBackchannelError
    flow = await _mo(hass, "onvif")
    with mock.patch("custom_components.dahua_talk.config_flow.check_rtsp_talk",
                    side_effect=NoBackchannelError("x")):
        kq = await hass.config_entries.flow.async_configure(flow, {
            "name": "Cam", "host": "192.168.1.9", "port": 554, "rtsp_path": "Streaming/Channels/101",
            "username": "admin", "password": "mk"})
    assert kq["errors"] == {"base": "no_backchannel"}


async def test_cau_hinh_lai_ezviz_dung_o_cua_ezviz(hass):
    assert await async_setup_component(hass, "homeassistant", {})
    entry = MockConfigEntry(domain=DOMAIN, title="Cam EZVIZ", unique_id="192.168.1.203:554", data={
        "name": "Cam EZVIZ", "host": "192.168.1.203", "camera_type": "ezviz", "talk_protocol": "rtsp",
        "port": 554, "username": "admin", "password": "ABCDEF",
        "rtsp_path": "/Streaming/Channels/101", "mic_url": "", "intercom_key": KHOA})
    entry.add_to_hass(hass)
    kq = await entry.start_reconfigure_flow(hass)
    assert [str(k) for k in kq["data_schema"].schema] == ["host", "password", "nghe_mic", "mic_url"]
    with mock.patch("custom_components.dahua_talk.config_flow.check_rtsp_talk") as hoi, \
            mock.patch("custom_components.dahua_talk.async_setup_entry", return_value=True):
        kq = await hass.config_entries.flow.async_configure(
            kq["flow_id"], {"host": "192.168.1.204", "password": "", "mic_url": ""})
    assert kq["reason"] == "reconfigure_successful"
    hoi.assert_called_once_with("192.168.1.204", "admin", "ABCDEF", 554, "/Streaming/Channels/101")
    assert entry.data["intercom_key"] == KHOA and entry.unique_id == "192.168.1.204:554"


def test_chon_phien_noi_theo_cau_hinh():
    from custom_components.dahua_talk import _mo_phien_noi
    from custom_components.dahua_talk.rtsp_talk import RtspTalkSession
    from custom_components.dahua_talk.talk import TalkSession
    cu = _mo_phien_noi({"host": "h", "port": 37777, "username": "u", "password": "p"})()
    assert isinstance(cu, TalkSession)                                  # mục cũ: Dahua
    moi = _mo_phien_noi({"host": "h", "port": 554, "username": "u", "password": "p",
                         "talk_protocol": "rtsp", "rtsp_path": "/Streaming/Channels/101"})()
    assert isinstance(moi, RtspTalkSession) and moi.url == "rtsp://h:554/Streaming/Channels/101"


async def test_ezviz_tick_nghe_mic_tu_dung_url(hass):
    """Mật khẩu có "@" — URL tự dựng phải mã hoá thành %40 (lỗi hay gặp khi gõ tay)."""
    flow = await _mo(hass, "ezviz")
    with mock.patch("custom_components.dahua_talk.config_flow.check_rtsp_talk"), \
            mock.patch("custom_components.dahua_talk.async_setup_entry", return_value=True):
        kq = await hass.config_entries.flow.async_configure(
            flow, {"name": "Cam", "host": "192.168.1.203", "password": "Ab@12", "nghe_mic": True})
    assert kq["data"]["mic_url"] == "rtsp://admin:Ab%4012@192.168.1.203:554/Streaming/Channels/102"


async def test_ezviz_url_mic_tu_go_thang_url_tu_dung(hass):
    flow = await _mo(hass, "ezviz")
    rieng = "http://192.168.1.10:1984/api/stream.mp4?src=cam_sub&video=none&audio=all"
    with mock.patch("custom_components.dahua_talk.config_flow.check_rtsp_talk"), \
            mock.patch("custom_components.dahua_talk.async_setup_entry", return_value=True):
        kq = await hass.config_entries.flow.async_configure(
            flow, {"name": "Cam", "host": "192.168.1.203", "password": "X", "nghe_mic": True,
                   "mic_url": rieng})
    assert kq["data"]["mic_url"] == rieng


async def test_ezviz_doi_mat_khau_url_mic_doi_theo_va_form_khong_lo_mat_khau(hass):
    assert await async_setup_component(hass, "homeassistant", {})
    cu = "rtsp://admin:OLDPW@192.168.1.203:554/Streaming/Channels/102"
    entry = MockConfigEntry(domain=DOMAIN, title="Cam", unique_id="192.168.1.203:554", data={
        "name": "Cam", "host": "192.168.1.203", "camera_type": "ezviz", "talk_protocol": "rtsp",
        "port": 554, "username": "admin", "password": "OLDPW", "rtsp_path": "/Streaming/Channels/101",
        "nghe_mic": True, "mic_url": cu, "mic_url_rieng": "", "intercom_key": KHOA})
    entry.add_to_hass(hass)
    kq = await entry.start_reconfigure_flow(hass)
    assert "OLDPW" not in str(kq["data_schema"]({}))           # URL có mật khẩu không ra form
    with mock.patch("custom_components.dahua_talk.config_flow.check_rtsp_talk"), \
            mock.patch("custom_components.dahua_talk.async_setup_entry", return_value=True):
        kq = await hass.config_entries.flow.async_configure(
            kq["flow_id"], {"host": "192.168.1.203", "password": "NEWPW", "nghe_mic": True, "mic_url": ""})
    assert kq["reason"] == "reconfigure_successful"
    assert entry.data["mic_url"] == "rtsp://admin:NEWPW@192.168.1.203:554/Streaming/Channels/102"
