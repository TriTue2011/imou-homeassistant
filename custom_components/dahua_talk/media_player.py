"""Loa camera thành một media_player: ``tts.speak`` và ``play_media`` phát ra loa camera.

Nhạc (``play_media`` không kèm ``announce``) phát NỀN: lệnh trả về ngay, bài mới thay bài đang phát,
Stop dừng được. Đo 30/09/2026: YouTube đẩy một bài vào loa camera thì lệnh phát treo suốt bài, loa
không có Stop — cách duy nhất để im là khởi động lại HA, và HA còn mất 1 phút mới tắt xong vì luồng
phát đang gửi dở. Thông báo (``announce``, ``tts.speak``) vẫn chờ phát xong như cũ để nối tiếp nhau.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import ATTR_MEDIA_ANNOUNCE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import DahuaTalkConfigEntry
from .entity import DahuaTalkEntity
from .speaker import HE_SO_TOI_DA
from .talk import TalkError

_LOGGER = logging.getLogger(__name__)

#: Nút Stop / Pause chờ luồng phát thoát tối đa ngần này giây rồi huỷ — không bao giờ treo.
_CHO_DUNG_GIAY = 8.0
#: Camera cắt kênh nói giữa bài: tự nối lại nếu lượt vừa rồi đã phát ít nhất ngần này giây, tối đa ngần ấy lần một bài.
_NOI_LAI_KHI_DA_PHAT_GIAY = 5.0
_NOI_LAI_TOI_DA = 20


async def async_setup_entry(hass: HomeAssistant, entry: DahuaTalkConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([DahuaTalkPlayer(entry)])


class DahuaTalkPlayer(DahuaTalkEntity, MediaPlayerEntity, RestoreEntity):
    _attr_translation_key = "speaker"
    _attr_supported_features = (MediaPlayerEntityFeature.PLAY_MEDIA
                                 | MediaPlayerEntityFeature.BROWSE_MEDIA
                                 | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
                                 | MediaPlayerEntityFeature.STOP
                                 | MediaPlayerEntityFeature.PAUSE
                                 | MediaPlayerEntityFeature.PLAY
                                 | MediaPlayerEntityFeature.SEEK
                                 | MediaPlayerEntityFeature.VOLUME_SET
                                 | MediaPlayerEntityFeature.VOLUME_STEP)
    #: 50% = tiếng gốc của camera (xem `speaker.HE_SO_TOI_DA`): camera mới thêm vẫn kêu như trước.
    _attr_volume_level = 0.5

    def __init__(self, entry: DahuaTalkConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}-speaker"
        self._attr_state = MediaPlayerState.IDLE
        #: Bài nhạc đang phát nền và cờ dừng của nó.
        self._bai: asyncio.Task | None = None
        self._huy: threading.Event | None = None
        #: Bài đang phát / tạm dừng: URL, giây bắt đầu của lượt phát này, lúc lượt ấy bắt đầu (monotonic) —
        #: để Pause rồi Play, hay thông báo chen ngang, phát TIẾP đúng chỗ (chủ máy 30/09/2026: "khi phát tts
        #: thì dừng nhạc, xong tts phát tiếp"; "nút stop, play trên media cam phải hoạt động bình thường").
        self._url: str | None = None
        self._tu_giay = 0.0
        self._bat_dau = 0.0
        #: Số lần đã tự nối lại trong bài này (camera cắt kênh nói giữa bài).
        self._noi_lai = 0
        self._vi_tri: int | None = None
        self._vi_tri_luc = None
        self._ly_do_idle: str | None = None

    async def async_play_media(self, media_type: MediaType | str, media_id: str,
                               **kwargs: Any) -> None:
        goc = media_id
        if media_source.is_media_source_id(media_id):
            play = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
            media_id = play.url
        url = async_process_play_media_url(self.hass, media_id)
        if kwargs.get(ATTR_MEDIA_ANNOUNCE):
            # Thông báo / TTS chen ngang: tạm dừng nhạc (nhớ chỗ), đọc xong phát tiếp.
            dang_phat = self._attr_state == MediaPlayerState.PLAYING and self._url is not None
            if dang_phat:
                await self.async_media_pause()
            await self._phat(url, threading.Event(), thong_bao=True)
            if dang_phat:
                await self.async_media_play()
            return
        await self._dung_han("interrupted")
        self._noi_lai = 0
        # Bài đang phát (id gốc) + vị trí: thẻ phát nhạc dựng thanh TUA từ đây (chủ máy 30/09/2026: "chế độ chỉ
        # nghe không có thanh tua nhạc").
        self._attr_media_content_id, self._attr_media_content_type = goc, media_type
        self._bat_dau_bai(url, 0.0)

    def _bat_dau_bai(self, url: str, tu_giay: float) -> None:
        self._url, self._tu_giay, self._bat_dau = url, tu_giay, time.monotonic()
        self._dat_vi_tri(tu_giay)
        self._huy = huy = threading.Event()
        self._bai = self.hass.async_create_background_task(
            self._phat(url, huy, tu_giay=tu_giay), f"{self.entity_id} play_media")

    async def _phat(self, url: str, huy: threading.Event, *, tu_giay: float = 0.0,
                    thong_bao: bool = False) -> None:
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()
        het_bai = loi_phat = False
        luc_mo = time.monotonic()
        try:
            await self._entry.runtime_data.speaker.async_play_url(url, huy, tu_giay)
            het_bai = not huy.is_set()
        except (TalkError, OSError) as exc:
            da_phat = time.monotonic() - luc_mo
            if (not thong_bao and not huy.is_set() and self._huy is huy
                    and da_phat >= _NOI_LAI_KHI_DA_PHAT_GIAY and self._noi_lai < _NOI_LAI_TOI_DA):
                # Camera cắt kênh nói GIỮA BÀI (đo 30/09/2026: Imou cắt cổng 8086 sau ~70 s, "Broken pipe") — nối
                # lại và phát tiếp đúng chỗ thay vì im luôn (chủ máy: "đang phát nhạc local thì dừng không thấy phát
                # nữa"). Chỉ nối khi lượt vừa rồi đã phát được một lúc: camera từ chối ngay thì không thử mãi.
                self._noi_lai += 1
                _LOGGER.info("%s: camera dropped the talk channel after %.0f s (%s), resuming at %.0f s (%d/%d)",
                             self.entity_id, da_phat, exc, tu_giay + da_phat, self._noi_lai, _NOI_LAI_TOI_DA)
                self._bat_dau_bai(url, tu_giay + da_phat)
                return
            _LOGGER.warning("%s: cannot play to camera speaker: %s", self.entity_id, exc)
            het_bai = True
            loi_phat = True
        finally:
            if thong_bao:
                # Nhạc đang tạm dừng chờ phát tiếp thì báo PAUSED, đừng «idle» một nhịp: tích hợp phát nhạc (YouTube)
                # đọc idle là HẾT BÀI rồi chuyển bài khác.
                self._attr_state = MediaPlayerState.PAUSED if self._url is not None else MediaPlayerState.IDLE
            elif self._huy is huy and het_bai:     # bài tự hết (không phải bị dừng / thay)
                self._ly_do_idle = "error" if loi_phat else "finished"
                self._attr_state = MediaPlayerState.IDLE
                self._url = self._huy = self._bai = None
                self._xoa_bai()
            self.async_write_ha_state()

    async def _dung_bai(self) -> None:
        """Dừng luồng phát nền. Không chờ vô hạn: luồng gửi thoát sau khúc đang gửi, và các phiên nói đều có
        hạn thời gian mạng — quá ``_CHO_DUNG_GIAY`` thì huỷ task, nút Stop không bao giờ treo HA."""
        bai, huy = self._bai, self._huy
        if huy is not None:
            huy.set()
        if bai is not None and not bai.done():
            _xong, con = await asyncio.wait({bai}, timeout=_CHO_DUNG_GIAY)
            if con:
                _LOGGER.warning("%s: playback did not stop within %s s, cancelling", self.entity_id,
                                _CHO_DUNG_GIAY)
                bai.cancel()
        self._bai = self._huy = None

    async def async_media_stop(self) -> None:
        """Dừng hẳn bài đang phát (hay đang tạm dừng): lệnh của người dùng / tự động hoá."""
        await self._dung_han("stopped")

    async def _dung_han(self, ly_do: str) -> None:
        """Dừng hẳn rồi ghi lý do để tích hợp phát nhạc phân biệt Stop / bị bài mới thay / hết bài (``idle_reason``)."""
        await self._dung_bai()
        self._url = None
        self._xoa_bai()
        self._ly_do_idle = ly_do
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """``idle_reason``: vì sao loa đang idle (``finished`` hết bài / ``stopped`` người dùng dừng / ``interrupted`` bị bài mới
        thay / ``error`` lỗi phát). Chỉ có khi idle; tích hợp phát nhạc (YouTube) đọc nó thay vì đoán bằng thời lượng bài."""
        if self._attr_state == MediaPlayerState.IDLE and self._ly_do_idle:
            return {"idle_reason": self._ly_do_idle}
        return None

    async def async_media_pause(self) -> None:
        """Tạm dừng: nhớ đã phát tới giây nào để Play phát tiếp."""
        if self._url is None or self._attr_state != MediaPlayerState.PLAYING:
            return
        self._tu_giay += time.monotonic() - self._bat_dau
        await self._dung_bai()
        self._dat_vi_tri(self._tu_giay)
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Phát tiếp bài đã tạm dừng từ chỗ dừng."""
        if self._url is None or self._attr_state == MediaPlayerState.PLAYING:
            return
        self._bat_dau_bai(self._url, self._tu_giay)

    async def async_media_seek(self, position: float) -> None:
        """Tua: phát lại từ giây ``position`` (ffmpeg ``-ss``); đang tạm dừng thì chỉ dời chỗ sẽ phát tiếp."""
        if self._url is None:
            return
        position = max(0.0, float(position))
        if self._attr_state == MediaPlayerState.PLAYING:
            await self._dung_bai()
            self._bat_dau_bai(self._url, position)
        else:
            self._tu_giay = position
            self._dat_vi_tri(position)
        self.async_write_ha_state()

    # Vị trí khai bằng THUỘC TÍNH RIÊNG, không qua ``_attr_media_position``: đo 30/09/2026 trên HA 2026.9.4 (Python
    # 3.14) gán ``_attr_media_position`` mà trạng thái vẫn KHÔNG có ``media_position`` (``media_content_id`` gán cùng
    # lúc thì có) — thanh tua hiện mà đứng yên. Trên HA 2026.2 của bộ test thì có. Tự trả biến của mình thì bản nào
    # cũng đúng.
    @property
    def media_position(self) -> int | None:
        return self._vi_tri

    @property
    def media_position_updated_at(self):
        return self._vi_tri_luc

    def _dat_vi_tri(self, giay: float) -> None:
        self._vi_tri = int(giay)
        self._vi_tri_luc = dt_util.utcnow()

    def _xoa_bai(self) -> None:
        self._vi_tri = self._vi_tri_luc = None
        self._attr_media_content_id = self._attr_media_content_type = None

    async def async_will_remove_from_hass(self) -> None:
        await self._dung_bai()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        cu = await self.async_get_last_state()
        muc = (cu.attributes.get("volume_level") if cu is not None else None)
        if isinstance(muc, (int, float)):
            self._dat_am_luong(float(muc))

    def _dat_am_luong(self, muc: float) -> None:
        self._attr_volume_level = min(1.0, max(0.0, muc))
        self._entry.runtime_data.speaker.he_so = HE_SO_TOI_DA * self._attr_volume_level

    async def async_set_volume_level(self, volume: float) -> None:
        """Âm lượng loa từng camera (phần mềm, mọi loại camera) — đổi lúc đang phát thì khúc kế tiếp theo ngay."""
        self._dat_am_luong(volume)
        self.async_write_ha_state()

    async def async_browse_media(self, media_content_type: MediaType | str | None = None,
                                 media_content_id: str | None = None) -> BrowseMedia:
        return await media_source.async_browse_media(
            self.hass, media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"))
