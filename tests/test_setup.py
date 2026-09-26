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
    assert loai == ["assist_satellite", "media_player", "number", "select", "select", "switch", "switch"]


async def test_loa_phat_url_va_tat_mic(hass):
    muc = _muc()
    await _nap(hass, muc)
    reg = er.async_get(hass)
    mp = next(e.entity_id for e in er.async_entries_for_config_entry(reg, muc.entry_id)
              if e.domain == "media_player")
    sw = next(e.entity_id for e in er.async_entries_for_config_entry(reg, muc.entry_id)
              if e.domain == "switch" and e.unique_id.endswith("-mute"))
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


async def test_pipeline_loi_thi_dung_doc_mic_trong_luc_nghi(hass):
    """Đo trên máy ARM: pipeline lỗi mà ffmpeg vẫn kéo tiếng mic về liên tục (2,3% CPU
    + băng thông) cho không ai dùng. Nghỉ vì lỗi thì tắt ffmpeg, hết nghỉ mới mở lại."""
    muc = _muc(mic="http://mic")
    tien_trinh = []

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
        if "-af" not in lenh:
            return await that(*lenh, **kw)
        p = ProcGia()
        tien_trinh.append(p)
        return p

    async def accept_loi(self, audio_stream, start_stage=PipelineStage.STT, **_kw):
        await asyncio.sleep(0.05)          # để ffmpeg kịp mở như ngoài đời
        self.on_pipeline_event(PipelineEvent(PipelineEventType.ERROR,
                                             {"code": "x", "message": "no stt"}))

    from custom_components.dahua_talk import assist_satellite as sat
    with mock.patch.object(sat.asyncio, "create_subprocess_exec", exec_gia), \
            mock.patch.object(sat.DahuaTalkSatellite, "async_accept_pipeline_from_satellite", accept_loi):
        await _nap(hass, muc)
        await asyncio.sleep(0.5)
        con_chay = [p for p in tien_trinh if p.returncode is None]
        so_mo = len(tien_trinh)
        await hass.config_entries.async_unload(muc.entry_id)
    assert so_mo == 1, f"mở ffmpeg {so_mo} lần trong lúc nghỉ"
    assert con_chay == [], "đang nghỉ vì pipeline lỗi mà ffmpeg vẫn đọc mic"


async def test_o_chon_chua_san_sang_thi_ha_dung_mac_dinh(hass):
    """Sự cố thật 26/09/2026: nạp lại tích hợp, lượt nghe đầu đọc ô chọn còn "unavailable"
    → HA ném "'unavailable' is not a valid VadSensitivity", vệ tinh tắt mic nghỉ tăng dần."""
    muc = _muc()
    await _nap(hass, muc)
    reg = er.async_get(hass)
    sat_id = next(e.entity_id for e in er.async_entries_for_config_entry(reg, muc.entry_id)
                  if e.domain == "assist_satellite")
    vad = next(e.entity_id for e in er.async_entries_for_config_entry(reg, muc.entry_id)
               if e.unique_id.endswith("-vad_sensitivity"))
    sat = hass.data["entity_components"]["assist_satellite"].get_entity(sat_id)
    assert sat.vad_sensitivity_entity_id == vad
    hass.states.async_set(vad, "unavailable")
    assert sat.vad_sensitivity_entity_id is None
    assert sat._resolve_vad_sensitivity() > 0          # HA dùng mặc định, không ném lỗi


async def test_mic_dung_im_thi_mo_lai(hass, caplog):
    """Sự cố thật 26/09/2026: ffmpeg nối mà không ra byte nào — vệ tinh điếc hàng giờ, log
    trống. Quá `_MIC_IM_GIAY` không có tiếng thì mở lại và ghi cảnh báo."""
    muc = _muc(mic="http://mic")
    lenh_da_chay: list[list[str]] = []

    class ProcDung:
        def __init__(self):
            self.returncode = None
            self.stdout = self

        async def readexactly(self, n):
            await asyncio.Event().wait()                  # đứng: không byte, không đóng

        def kill(self):
            self.returncode = -9

        async def wait(self):
            return self.returncode

    that = asyncio.create_subprocess_exec

    async def exec_gia(*lenh, **kw):
        if "-af" not in lenh:
            return await that(*lenh, **kw)
        lenh_da_chay.append(list(lenh))
        return ProcDung()

    async def accept_gia(self, audio_stream, **_kw):
        await asyncio.Event().wait()

    from custom_components.dahua_talk import assist_satellite as sat
    with mock.patch.object(sat.asyncio, "create_subprocess_exec", exec_gia), \
            mock.patch.object(sat, "_MIC_IM_GIAY", 0.05), \
            mock.patch.object(sat.asyncio, "sleep", _ngu_nhanh(asyncio.sleep)), \
            mock.patch.object(sat.DahuaTalkSatellite, "async_accept_pipeline_from_satellite", accept_gia):
        await _nap(hass, muc)
        for _ in range(200):
            if len(lenh_da_chay) >= 2:
                break
            await asyncio.sleep(0.01)
        await hass.config_entries.async_unload(muc.entry_id)
    assert len(lenh_da_chay) >= 2, "luồng đứng phải được mở lại"
    assert "no audio from mic" in caplog.text


def _ngu_nhanh(ngu_that):
    """asyncio.sleep rút ngắn cho vòng mở lại mic (nghỉ 2 s) — không đụng các sleep ≤ 0,05 s."""
    async def ngu(giay, *a, **k):
        return await ngu_that(min(giay, 0.01), *a, **k)
    return ngu


async def test_bat_duoc_tu_goi_thi_loa_keu_ting(hass):
    """Chủ máy 26/09/2026: "khi nó wake up thì có tiếng ting để người dùng còn biết để giao
    tiếp". Tắt công tắc thì im; lượt kết thúc mà KHÔNG bắt được thì im. Mic bỏ tiếng từ lúc
    bắt được tới khi tiếng ting DỨT (không tới lúc đóng phiên loa): đo 22:53–22:55 không chặn
    thì nhận giọng bịa "Không" từ tiếng ting khi chủ máy chưa nói gì."""
    import time
    from custom_components.dahua_talk import assist_satellite as sat

    pcm = sat.tieng_ting()
    assert 0.25 < len(pcm) / 2 / 8000 < 0.4, "ngắn: camera tắt mic lúc loa phát"
    muc = _muc()
    await _nap(hass, muc)
    reg = er.async_get(hass)
    ma = next(e.entity_id for e in er.async_entries_for_config_entry(reg, muc.entry_id)
              if e.domain == "assist_satellite")
    ting = next(e.entity_id for e in er.async_entries_for_config_entry(reg, muc.entry_id)
                if e.unique_id.endswith("-wake_sound"))
    assert hass.states.get(ting).state == "on", "mặc định bật"
    ve_tinh = hass.data["entity_components"]["assist_satellite"].get_entity(ma)
    phat: list[bytes] = []

    loa = muc.runtime_data.speaker
    dong_phien = asyncio.Event()

    async def play_gia(chunks):
        phat.append(b"".join([c async for c in chunks]))
        assert ve_tinh._chan_ting, "đang kêu ting thì bỏ tiếng mic"
        loa.het_tieng = time.monotonic()            # gói tiếng cuối vừa gửi
        await dong_phien.wait()                     # đóng phiên loa còn lâu
        return 0.3

    with mock.patch.object(muc.runtime_data.speaker, "async_play_pcm", play_gia):
        ve_tinh.on_pipeline_event(PipelineEvent(PipelineEventType.WAKE_WORD_END, {"wake_word_output": {}}))
        await hass.async_block_till_done()
        assert phat == [], "không bắt được thì không kêu"
        ve_tinh.on_pipeline_event(PipelineEvent(
            PipelineEventType.WAKE_WORD_END, {"wake_word_output": {"wake_word_id": "okay_nabu"}}))
        assert ve_tinh._chan_ting, "chặn ngay lúc bắt được — phủ cả đuôi từ gọi"
        await asyncio.sleep(sat._TING_DEM + 0.2)
        assert phat == [pcm] and not ve_tinh._chan_ting, "ting dứt thì mở mic, KHÔNG chờ đóng phiên"
        dong_phien.set()
        await hass.async_block_till_done()
        assert not ve_tinh._dang_noi
        await hass.services.async_call("switch", "turn_off", {"entity_id": ting}, blocking=True)
        ve_tinh.on_pipeline_event(PipelineEvent(
            PipelineEventType.WAKE_WORD_END, {"wake_word_output": {"wake_word_id": "okay_nabu"}}))
        await hass.async_block_till_done()
        assert len(phat) == 1


async def test_hong_sau_khi_da_nghe_thi_nghe_lai_ngay(hass):
    """Gọi xong không nói gì → STT báo lỗi sau vài giây nghe: không được tắt mic nghỉ 5–60 s
    (người dùng hay gọi lại liền). Chỉ lượt hỏng NGAY mới nghỉ."""
    muc = _muc(mic="http://mic")
    lan: list[float] = []

    async def accept_hong_muon(self, audio_stream, start_stage=PipelineStage.STT, **_kw):
        lan.append(self.hass.loop.time())
        await asyncio.sleep(0.2)                       # "nghe" lâu hơn _LUOT_LOI_NHANH (đã rút)
        self.on_pipeline_event(PipelineEvent(PipelineEventType.ERROR,
                                             {"code": "stt-no-text-recognized", "message": "No text"}))

    async def mic_gia(self):
        await asyncio.Event().wait()

    from custom_components.dahua_talk import assist_satellite as sat
    with mock.patch.object(sat.DahuaTalkSatellite, "async_accept_pipeline_from_satellite", accept_hong_muon), \
            mock.patch.object(sat.DahuaTalkSatellite, "_doc_mic", mic_gia), \
            mock.patch.object(sat, "_LUOT_LOI_NHANH", 0.1), mock.patch.object(sat, "_LUOT_TOI_THIEU", 0.05):
        await _nap(hass, muc)
        for _ in range(300):
            if len(lan) >= 3:
                break
            await asyncio.sleep(0.01)
        await hass.config_entries.async_unload(muc.entry_id)
    assert len(lan) >= 3, "phải nghe lại ngay, không nghỉ ≥ 5 s"
    assert max(b - a for a, b in zip(lan, lan[1:])) < 1.0



async def test_tts_treo_khong_lam_ve_tinh_ket(hass):
    """Sự cố thật 26/09/2026: kẹt "Đang phản hồi" 13 phút — luồng TTS không bao giờ đóng."""
    from custom_components.dahua_talk import assist_satellite as sat

    muc = _muc()
    await _nap(hass, muc)
    ma = next(e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), muc.entry_id)
              if e.domain == "assist_satellite")
    ve_tinh = hass.data["entity_components"]["assist_satellite"].get_entity(ma)

    class LuongTreo:
        async def async_stream_result(self):
            yield b"RIFF"
            await asyncio.Event().wait()

    xong: list[int] = []
    with mock.patch.object(sat, "_TTS_GOM_TOI_DA", 0.05), \
            mock.patch.object(ve_tinh, "tts_response_finished", lambda: xong.append(1)):
        await ve_tinh._phat_tts(LuongTreo())
    assert xong == [1] and not ve_tinh._dang_noi and ve_tinh._tts_xong.is_set()
