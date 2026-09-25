"""Nạp tích hợp: đủ thực thể, loa phát được, tắt mic, hội thoại nối tiếp."""

import asyncio
from unittest import mock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType, PipelineStage
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.dahua_talk.const import DOMAIN


def _muc(mic=""):
    return MockConfigEntry(domain=DOMAIN, title="Cam cửa", data={
        "name": "Cam cửa", "host": "192.168.1.64", "port": 37777, "username": "admin",
        "password": "mk", "mic_url": mic})


async def _nap(hass, muc):
    assert await async_setup_component(hass, "homeassistant", {})
    muc.add_to_hass(hass)
    assert await hass.config_entries.async_setup(muc.entry_id)
    await hass.async_block_till_done()


async def test_du_thuc_the_cua_mot_camera(hass):
    muc = _muc()
    await _nap(hass, muc)
    reg = er.async_get(hass)
    loai = sorted(e.entity_id.split(".")[0] for e in er.async_entries_for_config_entry(reg, muc.entry_id))
    assert loai == ["assist_satellite", "media_player", "number", "select", "select", "switch"]


async def test_loa_phat_url_va_tat_mic(hass):
    muc = _muc()
    await _nap(hass, muc)
    reg = er.async_get(hass)
    mp = next(e.entity_id for e in er.async_entries_for_config_entry(reg, muc.entry_id)
              if e.domain == "media_player")
    sw = next(e.entity_id for e in er.async_entries_for_config_entry(reg, muc.entry_id)
              if e.domain == "switch")
    with mock.patch.object(muc.runtime_data.speaker, "async_play_url", return_value=1.0) as phat:
        await hass.services.async_call("media_player", "play_media", {
            "entity_id": mp, "media_content_id": "http://x/a.mp3", "media_content_type": "music"},
            blocking=True)
    phat.assert_awaited_once_with("http://x/a.mp3")
    await hass.services.async_call("switch", "turn_on", {"entity_id": sw}, blocking=True)
    assert muc.runtime_data.mic_muted and hass.states.get(sw).state == "on"


async def test_cau_tra_loi_hoi_lai_thi_luot_sau_nghe_thang(hass):
    """``continue_conversation`` → lượt sau bắt đầu từ STT, không cần từ gọi."""
    muc = _muc(mic="http://mic")
    lan: list[PipelineStage] = []

    async def gia_accept(self, audio_stream, start_stage=PipelineStage.STT, **_kw):
        lan.append(start_stage)
        if len(lan) == 1:
            self.on_pipeline_event(PipelineEvent(PipelineEventType.INTENT_END,
                                                 {"intent_output": {"continue_conversation": True}}))
        elif len(lan) == 2:
            self.on_pipeline_event(PipelineEvent(PipelineEventType.INTENT_END,
                                                 {"intent_output": {"continue_conversation": False}}))
        await asyncio.sleep(0)

    async def mic_gia(self):
        await asyncio.Event().wait()

    from custom_components.dahua_talk import assist_satellite as sat
    with mock.patch.object(sat.DahuaTalkSatellite, "async_accept_pipeline_from_satellite", gia_accept), \
            mock.patch.object(sat.DahuaTalkSatellite, "_doc_mic", mic_gia):
        await _nap(hass, muc)
        # Lượt hỏi lại (STT) chạy NGAY; lượt thường sau đó cách tối thiểu 1 giây.
        for _ in range(300):
            if len(lan) >= 3:
                break
            await asyncio.sleep(0.01)
        await hass.config_entries.async_unload(muc.entry_id)
    assert lan[:3] == [PipelineStage.WAKE_WORD, PipelineStage.STT, PipelineStage.WAKE_WORD]


async def test_tang_mic_ap_vao_ffmpeg_va_doi_la_mo_lai(hass):
    """Mic camera nhỏ: phải tăng được trong HA (đo thật cần +18 dB ở 3 m)."""
    from custom_components.dahua_talk.assist_satellite import loc_mic

    assert loc_mic(0) == "highpass=f=80"                 # luôn bỏ DC, không tăng
    assert loc_mic(18).startswith("highpass=f=80,volume=18dB,alimiter=")

    muc = _muc(mic="http://mic")
    lenh_da_chay: list[list[str]] = []

    class ProcGia:
        def __init__(self):
            self.returncode = None
            self._dung = asyncio.Event()
            self.stdout = self

        async def readexactly(self, n):
            await self._dung.wait()
            raise asyncio.IncompleteReadError(b"", n)

        def kill(self):
            self.returncode = -9
            self._dung.set()

        async def wait(self):
            return self.returncode

    that = asyncio.create_subprocess_exec

    async def exec_gia(*lenh, **kw):
        if "-af" not in lenh:                 # không phải lệnh đọc mic (vd ffmpeg -version của HA)
            return await that(*lenh, **kw)
        lenh_da_chay.append(list(lenh))
        return ProcGia()

    async def accept_gia(self, audio_stream, **_kw):
        await asyncio.Event().wait()

    from custom_components.dahua_talk import assist_satellite as sat
    with mock.patch.object(sat.asyncio, "create_subprocess_exec", exec_gia), \
            mock.patch.object(sat.DahuaTalkSatellite, "async_accept_pipeline_from_satellite", accept_gia):
        await _nap(hass, muc)
        so = next(e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), muc.entry_id)
                  if e.domain == "number")
        for _ in range(50):
            if lenh_da_chay:
                break
            await asyncio.sleep(0.01)
        assert "highpass=f=80" in lenh_da_chay[0]
        await hass.services.async_call("number", "set_value", {"entity_id": so, "value": 18},
                                       blocking=True)
        for _ in range(50):
            if len(lenh_da_chay) >= 2:
                break
            await asyncio.sleep(0.01)
        assert muc.runtime_data.mic_gain_db == 18
        await hass.config_entries.async_unload(muc.entry_id)
    assert any(a.startswith("highpass=f=80,volume=18dB") for a in lenh_da_chay[1])


async def test_pipeline_loi_ngay_khong_quay_vong_lam_treo_ha(hass, caplog):
    """Sự cố thật: HA mới cài, pipeline chưa có từ gọi → pipeline báo lỗi và kết thúc
    trong vài mili-giây; vòng nghe mở lại tức thì → hàng nghìn lượt/giây, HA treo cứng.
    Nay lỗi thì nghỉ (5 s, tăng dần) và báo MỘT dòng cảnh báo."""
    muc = _muc(mic="http://mic")
    lan = []

    async def accept_loi(self, audio_stream, start_stage=PipelineStage.STT, **_kw):
        lan.append(start_stage)
        self.on_pipeline_event(PipelineEvent(PipelineEventType.ERROR,
                                             {"code": "wake-engine-missing",
                                              "message": "No wake word engine"}))

    async def mic_gia(self):
        await asyncio.Event().wait()

    from custom_components.dahua_talk import assist_satellite as sat
    with mock.patch.object(sat.DahuaTalkSatellite, "async_accept_pipeline_from_satellite", accept_loi), \
            mock.patch.object(sat.DahuaTalkSatellite, "_doc_mic", mic_gia):
        await _nap(hass, muc)
        await asyncio.sleep(0.5)
        so_lan = len(lan)
        await hass.config_entries.async_unload(muc.entry_id)
    assert so_lan == 1, f"{so_lan} lượt trong 0,5 s — vòng nghe đang quay vòng"
    canh_bao = [r for r in caplog.records if "Assist pipeline error" in r.getMessage()]
    assert len(canh_bao) == 1 and "No wake word engine" in canh_bao[0].getMessage()


async def test_pipeline_ket_thuc_ngay_khong_loi_van_cach_toi_thieu(hass):
    """Kể cả lượt kết thúc ngay mà KHÔNG báo lỗi, hai lượt vẫn cách nhau ≥ 1 giây."""
    muc = _muc(mic="http://mic")
    lan = []

    async def accept_ngay(self, audio_stream, start_stage=PipelineStage.STT, **_kw):
        lan.append(start_stage)

    async def mic_gia(self):
        await asyncio.Event().wait()

    from custom_components.dahua_talk import assist_satellite as sat
    with mock.patch.object(sat.DahuaTalkSatellite, "async_accept_pipeline_from_satellite", accept_ngay), \
            mock.patch.object(sat.DahuaTalkSatellite, "_doc_mic", mic_gia):
        await _nap(hass, muc)
        await asyncio.sleep(0.5)
        so_lan = len(lan)
        await hass.config_entries.async_unload(muc.entry_id)
    assert so_lan == 1
