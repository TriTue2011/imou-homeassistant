"""Camera thành vệ tinh Assist gốc của HA (không qua Wyoming, không cần dịch vụ ngoài).

Vòng nghe: ffmpeg đọc mic camera (URL go2rtc/RTSP) → PCM16 mono 16 kHz → đưa vào
``async_accept_pipeline_from_satellite`` bắt đầu từ bước bắt từ gọi (từ gọi chọn
trong pipeline, vd okay_nabu của openWakeWord). Trả lời TTS xin sẵn WAV 8 kHz một
kênh (``tts_options``) — đúng định dạng loa Dahua, HA tự đổi — rồi phát ra loa.

Hội thoại nối tiếp: khi hiểu lệnh báo ``continue_conversation`` (câu trả lời là
câu hỏi lại), lượt sau bắt đầu thẳng từ bước nghe câu nói, không cần từ gọi.

Khuôn: ``homeassistant/components/voip/assist_satellite.py`` (HA 2026.9.3).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import struct
from typing import Any

from homeassistant.components import tts
from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType, PipelineStage
from homeassistant.components.assist_satellite import (
    AssistSatelliteAnnouncement,
    AssistSatelliteConfiguration,
    AssistSatelliteEntity,
    AssistSatelliteEntityFeature,
)
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DahuaTalkConfigEntry
from .const import DOMAIN, MIC_CHUNK, MIC_RATE
from .entity import DahuaTalkEntity
from .talk import TalkError

_LOGGER = logging.getLogger(__name__)

#: Chờ tối đa ngần này giây sau phần tiếng TTS rồi coi như đã phát xong.
_TTS_THEM_GIAY = 5.0
#: Gom tiếng TTS / tiếng ting tối đa ngần này giây — quá thì bỏ, vệ tinh về nghe tiếp.
_TTS_GOM_TOI_DA = 30.0
_TING_TOI_DA = 5.0
#: Hai lượt pipeline cách nhau ít nhất ngần này giây, dù lượt trước kết thúc thế nào.
_LUOT_TOI_THIEU = 1.0
#: Pipeline lỗi (chưa có từ gọi, STT/TTS hỏng…) thì nghỉ, tăng dần tới mức này.
_NGHI_LOI_TOI_DA = 60.0
#: Chỉ lượt hỏng NGAY (dưới ngần này giây) mới nghỉ — đó là pipeline cấu hình hỏng, mở lại
#: tức thì là quay vòng. Lượt đã nghe lâu hơn mà hỏng (STT không ra chữ…) thì nghe lại ngay.
_LUOT_LOI_NHANH = 3.0
#: Chờ ô chọn pipeline / độ nhạy sẵn sàng tối đa ngần này giây trước lượt nghe đầu.
#: Vệ tinh nạp NHANH hơn hai ô chọn của chính nó: lượt đầu đọc ô chọn còn "unavailable"
#: thì HA ném lỗi ('unavailable' is not a valid VadSensitivity) — đo thật 26/09/2026 mỗi
#: lần nạp lại tích hợp; vệ tinh coi là pipeline lỗi, tắt mic và nghỉ tăng dần.
_CHO_O_CHON_GIAY = 30.0
#: ffmpeg xuất PCM ĐỀU kể cả lúc phòng yên — ngần này giây không có byte nào là luồng đứng
#: (đứt mà không đóng). Đo thật 26/09/2026: vệ tinh "idle" hàng giờ, go2rtc không còn kết
#: nối nào của HA, log không một dòng — không có đồng hồ này thì không ai biết.
_MIC_IM_GIAY = 10.0


def tieng_ting(tan_so: int = 8000) -> bytes:
    """Hai nốt ngắn đi lên (Đô 6 → Son 6, ~0,3 s) PCM16 mono — báo "đã nghe, nói đi".

    Ngắn có chủ ý: camera tự TẮT MIC lúc loa đang phát (đo thật trên Imou và EZVIZ), tiếng
    báo dài là nuốt mất đầu câu lệnh. Sinh bằng mã, không cần tệp âm thanh."""
    ra = bytearray()
    for hz, giay in ((1047.0, 0.12), (1568.0, 0.18)):
        n = int(tan_so * giay)
        mem = int(tan_so * 0.01)                         # 10 ms vào/ra — khỏi tiếng "bụp"
        for i in range(n):
            bao = min(1.0, i / mem, (n - 1 - i) / mem)
            ra += struct.pack("<h", int(0.35 * 32767 * bao * math.sin(2 * math.pi * hz * i / tan_so)))
    return bytes(ra)


def loc_mic(tang_db: float) -> str:
    """Bộ lọc ffmpeg cho tiếng mic camera.

    Mic camera lệch một chiều (DC): đo trên camera Imou, DC ≈ +0,004 trong khi tiếng
    nền thật chỉ ~-64 dBFS — khuếch đại luôn cả DC là mất chỗ cho tiếng. Lọc thông cao
    80 Hz bỏ DC (không đụng dải tiếng nói) TRƯỚC khi tăng, rồi chặn đỉnh để nói gần
    mic không vỡ tiếng.
    """
    loc = "highpass=f=80"
    if tang_db > 0:
        loc += f",volume={tang_db:g}dB,alimiter=limit=0.9:attack=5:release=50:level=false"
    return loc


async def async_setup_entry(hass: HomeAssistant, entry: DahuaTalkConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([DahuaTalkSatellite(entry)])


class DahuaTalkSatellite(DahuaTalkEntity, AssistSatelliteEntity):
    _attr_name = None
    _attr_supported_features = (AssistSatelliteEntityFeature.ANNOUNCE
                                | AssistSatelliteEntityFeature.START_CONVERSATION)

    def __init__(self, entry: DahuaTalkConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}-satellite"
        self._data = entry.runtime_data
        self._hang: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=64)
        self._dang_noi = False           # đang phát ra loa: bỏ tiếng mic (khỏi tự nghe mình)
        self._tts_xong = asyncio.Event()
        self._co_tts = False
        self._tiep = False               # lượt sau nghe thẳng, không cần từ gọi
        self._vong: asyncio.Task | None = None
        self._mic_proc: asyncio.subprocess.Process | None = None
        self._mo_lai_mic = False         # tự tắt ffmpeg để đổi mức tăng mic
        self._loi_luot: str | None = None  # lỗi pipeline của lượt vừa chạy
        # Được đọc mic. Hạ xuống khi vệ tinh nghỉ vì pipeline lỗi: không kéo tiếng
        # về liên tục cho không ai dùng (đo trên máy ARM: ffmpeg 2,3% CPU + băng thông).
        self._duoc_nghe = asyncio.Event()
        self._duoc_nghe.set()

    # ── Cấu hình HA đòi ───────────────────────────────────────────────────────

    def _o_chon(self, khoa: str) -> str | None:
        """Mã ô chọn — chỉ khi nó ĐÃ có giá trị. "unavailable"/"unknown" thì None để HA dùng
        mặc định thay vì ném lỗi làm hỏng lượt nghe (xem `_CHO_O_CHON_GIAY`)."""
        ma = er.async_get(self.hass).async_get_entity_id(
            "select", DOMAIN, f"{self._entry.entry_id}-{khoa}")
        st = self.hass.states.get(ma) if ma else None
        return ma if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) else None

    @property
    def pipeline_entity_id(self) -> str | None:
        return self._o_chon("pipeline")

    @property
    def vad_sensitivity_entity_id(self) -> str | None:
        return self._o_chon("vad_sensitivity")

    @property
    def tts_options(self) -> dict[str, Any] | None:
        return {tts.ATTR_PREFERRED_FORMAT: "wav", tts.ATTR_PREFERRED_SAMPLE_RATE: 8000,
                tts.ATTR_PREFERRED_SAMPLE_CHANNELS: 1, tts.ATTR_PREFERRED_SAMPLE_BYTES: 2}

    @callback
    def async_get_configuration(self) -> AssistSatelliteConfiguration:
        # Từ gọi do pipeline quyết (bắt ở HA), vệ tinh không tự bắt.
        raise NotImplementedError

    async def async_set_configuration(self, config: AssistSatelliteConfiguration) -> None:
        raise NotImplementedError

    # ── Vòng đời ──────────────────────────────────────────────────────────────

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._data.mic_url:
            self._vong = self._entry.async_create_background_task(
                self.hass, self._chay(), f"{self.entity_id} listen")
        else:
            _LOGGER.info("%s: no mic URL — speaker/announce only", self.entity_id)
        self.async_on_remove(self._data.listen_mute(self._khi_tat_mic))
        self.async_on_remove(self._data.listen_gain(self._khi_doi_tang))

    async def async_will_remove_from_hass(self) -> None:
        if self._vong is not None:
            self._vong.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._vong
        await super().async_will_remove_from_hass()

    @callback
    def _khi_tat_mic(self, tat: bool) -> None:
        if tat:
            self._cat_luot()

    @callback
    def _khi_doi_tang(self, _db: float) -> None:
        """Đổi mức tăng mic: tắt ffmpeg đang chạy, vòng đọc mở lại với mức mới."""
        if self._mic_proc is not None and self._mic_proc.returncode is None:
            self._mo_lai_mic = True
            self._mic_proc.kill()

    @callback
    def _dung_doc_mic(self) -> None:
        """Tạm dừng đọc mic (tắt ffmpeg) cho tới khi ``_duoc_nghe`` bật lại."""
        self._duoc_nghe.clear()
        if self._mic_proc is not None and self._mic_proc.returncode is None:
            self._mo_lai_mic = True
            self._mic_proc.kill()

    @callback
    def _cat_luot(self) -> None:
        """Kết thúc luồng tiếng của lượt đang chạy để vòng nghe mở lượt mới."""
        while not self._hang.empty():
            self._hang.get_nowait()
        self._hang.put_nowait(None)

    # ── Tai ───────────────────────────────────────────────────────────────────

    async def _cho_o_chon(self) -> None:
        """Đợi hai ô chọn của vệ tinh có giá trị — lượt đầu mà dùng mặc định thì chạy nhầm
        pipeline ưu tiên (lượt chờ từ gọi kéo dài hàng giờ)."""
        het = self.hass.loop.time() + _CHO_O_CHON_GIAY
        while self.hass.loop.time() < het and (
                self.pipeline_entity_id is None or self.vad_sensitivity_entity_id is None):
            await asyncio.sleep(0.1)

    async def _chay(self) -> None:
        await self._cho_o_chon()
        mic = self._entry.async_create_background_task(self.hass, self._doc_mic(),
                                                       f"{self.entity_id} mic")
        # Pipeline hỏng NGAY từ đầu (chưa có engine từ gọi, STT/TTS lỗi…) kết thúc
        # trong vài mili-giây; mở lại tức thì là hàng nghìn lượt mỗi giây và HA treo
        # cứng — đã xảy ra thật trên một máy HA ARM mới cài, pipeline chưa có từ gọi.
        # Nên: lỗi thì nghỉ (tăng dần), và hai lượt luôn cách nhau tối thiểu.
        nghi_loi = 0.0
        loi_da_bao = None
        try:
            while True:
                if self._data.mic_muted:
                    await asyncio.sleep(1)
                    continue
                bat_dau = PipelineStage.STT if self._tiep else PipelineStage.WAKE_WORD
                self._tiep = False
                self._co_tts = False
                self._loi_luot = None
                self._tts_xong.clear()
                t0 = self.hass.loop.time()
                try:
                    await self.async_accept_pipeline_from_satellite(
                        audio_stream=self._luong_stt(), start_stage=bat_dau)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 — một lượt hỏng không được làm điếc vệ tinh
                    _LOGGER.debug("%s: pipeline failed", self.entity_id, exc_info=True)
                    self._loi_luot = str(exc) or type(exc).__name__
                if self._co_tts and self._loi_luot is None:
                    await self._tts_xong.wait()
                if self._tiep:
                    # Bị cắt để hỏi–đáp tiếp (start_conversation / câu hỏi lại):
                    # lượt sau phải nghe ngay, không nghỉ.
                    nghi_loi = 0.0
                    continue
                if self._loi_luot is not None and self.hass.loop.time() - t0 >= _LUOT_LOI_NHANH:
                    # Hỏng SAU khi đã nghe một lúc (gọi xong không nói gì → STT không ra chữ,
                    # tác tử hội thoại lỗi…): đó là chuyện của lượt ấy, không phải pipeline hỏng
                    # — nghe lại ngay, không tắt mic nghỉ (người dùng hay gọi lại liền).
                    _LOGGER.debug("%s: pipeline run failed after listening (%s) — listening again",
                                  self.entity_id, self._loi_luot)
                    self._loi_luot = None
                if self._loi_luot is not None:
                    nghi_loi = min(_NGHI_LOI_TOI_DA, max(5.0, nghi_loi * 2))
                    if self._loi_luot != loi_da_bao:
                        loi_da_bao = self._loi_luot
                        _LOGGER.warning(
                            "%s: Assist pipeline error (%s) — retrying every %.0f s. "
                            "Check the pipeline selected for this camera (wake word "
                            "engine, STT, TTS).", self.entity_id, self._loi_luot, nghi_loi)
                    self._dung_doc_mic()
                    try:
                        await asyncio.sleep(nghi_loi)
                    finally:
                        self._duoc_nghe.set()
                    continue
                nghi_loi, loi_da_bao = 0.0, None
                con = _LUOT_TOI_THIEU - (self.hass.loop.time() - t0)
                if con > 0:
                    await asyncio.sleep(con)
        finally:
            mic.cancel()

    async def _luong_stt(self):
        """Tiếng mic cho MỘT lượt pipeline."""
        # Bỏ tiếng tồn từ lúc đang nói / lượt trước.
        while not self._hang.empty():
            self._hang.get_nowait()
        while (khuc := await self._hang.get()) is not None:
            yield khuc

    async def _doc_mic(self) -> None:
        """ffmpeg đọc mic camera liên tục; đứt hay ĐỨNG (camera rớt mạng…) thì mở lại.
        Lỗi bất ngờ ghi log rồi thử lại — vòng này chết là vệ tinh điếc mà không ai biết."""
        while True:
            try:
                await self._mot_lan_doc_mic()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                _LOGGER.exception("%s: mic reader failed, reopening", self.entity_id)
                await asyncio.sleep(2)

    async def _mot_lan_doc_mic(self) -> None:
        """Một lần mở ffmpeg, đọc tới khi luồng đứt / đứng / bị tắt."""
        await self._duoc_nghe.wait()
        lenh = [get_ffmpeg_manager(self.hass).binary, "-nostdin", "-hide_banner",
                "-loglevel", "error"]
        if self._data.mic_url.lower().startswith("rtsp://"):
            lenh += ["-rtsp_transport", "tcp"]
        lenh += ["-i", self._data.mic_url, "-vn", "-af", loc_mic(self._data.mic_gain_db),
                 "-ac", "1", "-ar", str(MIC_RATE), "-f", "s16le", "pipe:"]
        proc = self._mic_proc = await asyncio.create_subprocess_exec(
            *lenh, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        try:
            while True:
                try:
                    khuc = await asyncio.wait_for(proc.stdout.readexactly(MIC_CHUNK), _MIC_IM_GIAY)
                except TimeoutError:
                    _LOGGER.warning("%s: no audio from mic for %.0f s, reopening",
                                    self.entity_id, _MIC_IM_GIAY)
                    break
                if self._dang_noi or self._data.mic_muted:
                    continue
                if self._hang.full():
                    self._hang.get_nowait()      # tụt hậu thì bỏ khúc cũ nhất
                self._hang.put_nowait(khuc)
        except asyncio.IncompleteReadError:
            if not self._mo_lai_mic:
                _LOGGER.warning("%s: mic stream ended, reopening", self.entity_id)
        finally:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
        # Tự tắt để đổi mức tăng mic thì mở lại ngay; đứt / đứng thật thì nghỉ 2 giây.
        if self._mo_lai_mic:
            self._mo_lai_mic = False
        else:
            await asyncio.sleep(2)

    # ── Miệng ─────────────────────────────────────────────────────────────────

    def on_pipeline_event(self, event: PipelineEvent) -> None:
        if event.type is PipelineEventType.WAKE_WORD_END:
            # Bắt được từ gọi (output rỗng là luồng tiếng kết thúc mà không bắt được).
            if (event.data or {}).get("wake_word_output") and self._data.ting:
                self._entry.async_create_background_task(
                    self.hass, self._phat_ting(), f"{self.entity_id} ting")
        elif event.type is PipelineEventType.INTENT_END:
            ra = (event.data or {}).get("intent_output") or {}
            self._tiep = bool(ra.get("continue_conversation"))
        elif event.type is PipelineEventType.TTS_END:
            ra = (event.data or {}).get("tts_output") or {}
            luong = tts.async_get_stream(self.hass, ra["token"]) if ra.get("token") else None
            if luong is None:
                self._tts_xong.set()
                return
            self._co_tts = True
            self._entry.async_create_background_task(
                self.hass, self._phat_tts(luong), f"{self.entity_id} tts")
        elif event.type is PipelineEventType.ERROR:
            # Không đụng ``_tiep``: lượt chờ từ gọi bị cắt (bắt đầu hội thoại) cũng
            # báo lỗi, mà lượt sau vẫn phải nghe thẳng.
            _LOGGER.debug("%s: pipeline error %s", self.entity_id, event.data)
            d = event.data or {}
            self._loi_luot = str(d.get("message") or d.get("code") or "error")
            self._tts_xong.set()

    async def _phat_ting(self) -> None:
        """Tiếng báo đã bắt được từ gọi. KHÔNG bỏ tiếng mic lúc kêu: camera tự tắt mic khi loa
        phát, còn bỏ tiếng tới lúc đóng xong phiên loa thì nuốt mất đầu câu người nói ngay sau
        tiếng ting (chủ máy 26/09/2026: "người dùng nghe thấy ting là nói luôn rồi"). Có hạn:
        phiên loa treo thì tiếng báo bỏ, vệ tinh không được treo theo."""
        try:
            pcm = tieng_ting()

            async def _mot():
                yield pcm
            async with asyncio.timeout(_TING_TOI_DA):
                await self._data.speaker.async_play_pcm(_mot())
        except (TalkError, OSError, TimeoutError) as exc:
            _LOGGER.debug("%s: cannot play wake sound: %s", self.entity_id, exc)

    async def _phat_tts(self, luong: tts.ResultStream) -> None:
        self._dang_noi = True
        try:
            # Gom tiếng TTS CÓ HẠN: dịch vụ TTS trả luồng mà không đóng thì vệ tinh kẹt ở
            # "Đang phản hồi" mãi, không về nghe (đo thật 26/09/2026: kẹt 13 phút tới khi nạp lại).
            async with asyncio.timeout(_TTS_GOM_TOI_DA):
                wav = b"".join([k async for k in luong.async_stream_result()])
            async with asyncio.timeout(len(wav) / 16000 + _TTS_THEM_GIAY + 10):
                await self._data.speaker.async_play_wav(wav)
        except (TalkError, OSError, TimeoutError) as exc:
            _LOGGER.warning("%s: cannot play reply: %s", self.entity_id, exc)
        finally:
            self._dang_noi = False
            self.tts_response_finished()
            self._tts_xong.set()

    async def async_announce(self, announcement: AssistSatelliteAnnouncement) -> None:
        self._dang_noi = True
        try:
            if announcement.tts_token and (
                    luong := tts.async_get_stream(self.hass, announcement.tts_token)):
                async with asyncio.timeout(_TTS_GOM_TOI_DA):
                    wav = b"".join([k async for k in luong.async_stream_result()])
                async with asyncio.timeout(len(wav) / 16000 + _TTS_THEM_GIAY + 10):
                    await self._data.speaker.async_play_wav(wav)
            else:
                await self._data.speaker.async_play_url(announcement.media_id)
        except (TalkError, OSError, TimeoutError) as exc:
            _LOGGER.warning("%s: cannot play announcement: %s", self.entity_id, exc)
        finally:
            self._dang_noi = False

    async def async_start_conversation(self, start_announcement: AssistSatelliteAnnouncement
                                       ) -> None:
        """Nói trước rồi nghe câu trả lời ngay (không cần từ gọi)."""
        await self.async_announce(start_announcement)
        self._tiep = True
        self._cat_luot()     # lượt đang chờ từ gọi kết thúc, lượt mới nghe thẳng
