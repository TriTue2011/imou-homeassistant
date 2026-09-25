"""Bộ đàm: mic điện thoại (thẻ WebRTC Camera qua go2rtc) → loa camera, ngay trong HA.

Thẻ ``custom:webrtc-camera`` có ``media: video,audio,microphone`` gửi mic vào
go2rtc; go2rtc (từ 1.9.10) đẩy tiếng vào stdin một lệnh ``exec:…#backchannel=1``;
lệnh ấy (ffmpeg) POST luồng A-law 8 kHz tới view dưới đây, và view phát ra loa
camera qua ``Speaker`` — dùng chung khoá phiên với TTS và thông báo.

Kênh nói chỉ mở KHI CÓ TIẾNG NGƯỜI và đóng sau một quãng im: camera tự tắt mic
của nó suốt lúc kênh nói mở, mà trình duyệt gửi tiếng liên tục suốt lúc thẻ còn
mở — mở kênh suốt thì không bao giờ nghe được người bên camera trả lời.

go2rtc không gửi được header ``Authorization`` từ lệnh exec, nên đường POST dùng
khoá ngẫu nhiên riêng từng camera trong URL; khoá chỉ phát được tiếng ra loa của
đúng camera ấy.
"""

from __future__ import annotations

import array
import asyncio
import hmac
import logging
import math
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .talk import TAN_SO

if TYPE_CHECKING:
    from .speaker import Speaker

_LOGGER = logging.getLogger(__name__)

#: Mức coi là có tiếng người (dBFS, RMS từng khúc). Mic tắt trong trình duyệt gửi
#: số 0; phòng yên sau lọc ồn của trình duyệt dưới -55.
NGUONG_DB = -45.0
#: Im ngần này giây thì đóng kênh để nghe bên kia.
IM_GIAY = 1.5
#: Giữ ngần này giây tiếng ngay trước lúc có tiếng — khỏi mất âm đầu câu.
DEM_GIAY = 0.3

#: Cờ bắt buộc cho ffmpeg đọc ống dẫn theo luồng: thiếu chúng, ffmpeg gom tiếng để
#: dò định dạng rồi mới nhả — đo 24/09/2026: 2,5 giây vào mà 0 byte ra.
_FFMPEG_TRUC_TIEP = "-probesize 32 -analyzeduration 0 -fflags nobuffer"


def _bang_alaw() -> list[int]:
    """G.711 A-law → PCM16 (đúng ``alaw2linear`` bản mẫu ITU; khớp ffmpeg 256/256 mã)."""
    bang = []
    for a in range(256):
        a ^= 0x55
        t = (a & 0x0F) << 4
        seg = (a & 0x70) >> 4
        t = t + 8 if seg == 0 else (t + 0x108) << (seg - 1)
        bang.append(t if a & 0x80 else -t)
    return bang


_ALAW = _bang_alaw()


def alaw_to_pcm(b: bytes) -> bytes:
    return array.array("h", (_ALAW[x] for x in b)).tobytes()


def _muc_db(pcm: bytes) -> float:
    a = array.array("h", pcm[: len(pcm) // 2 * 2])
    tong = sum(x * x for x in a)
    return 10 * math.log10(tong / len(a) / 32768.0 ** 2) if tong else -120.0


class Intercom:
    """Một phiên bộ đàm: nhận PCM16 8 kHz, mở loa khi có tiếng, đóng khi im."""

    def __init__(self, hass: HomeAssistant, speaker: "Speaker") -> None:
        self.hass, self.speaker = hass, speaker
        self.seconds = 0.0            # tổng số giây đã phát ra loa
        self._hang: asyncio.Queue[bytes | None] | None = None
        self._viec: list[asyncio.Task] = []
        self._dem = b""
        self._im = 0.0

    async def _nguon(self, hang: asyncio.Queue) -> AsyncIterator[bytes]:
        while (khuc := await hang.get()) is not None:
            yield khuc

    async def _phat(self, hang: asyncio.Queue) -> None:
        try:
            self.seconds += await self.speaker.async_play_pcm(self._nguon(hang))
        except Exception as exc:  # noqa: BLE001 — loa hỏng một lượt không được giết cả phiên
            _LOGGER.warning("intercom: cannot play to camera: %s", exc)
            # Nguồn còn đang đợi thì rút cạn để khỏi treo người đẩy.
            while not hang.empty():
                hang.get_nowait()

    def feed(self, pcm: bytes) -> None:
        pcm = pcm[: len(pcm) // 2 * 2]
        if not pcm:
            return
        co_tieng = _muc_db(pcm) > NGUONG_DB
        self._im = 0.0 if co_tieng else self._im + len(pcm) / (2 * TAN_SO)
        if self._hang is None:
            if not co_tieng:
                self._dem = (self._dem + pcm)[-int(DEM_GIAY * TAN_SO) * 2:]
                return
            self._hang = asyncio.Queue()
            self._viec.append(self.hass.async_create_task(self._phat(self._hang)))
            pcm, self._dem = self._dem + pcm, b""
        self._hang.put_nowait(pcm)
        if self._im >= IM_GIAY:
            self.stop_talking()

    def stop_talking(self) -> None:
        """Đóng kênh nói (camera nghe lại được). Nói tiếp thì mở lại."""
        if self._hang is not None:
            self._hang.put_nowait(None)
            self._hang = None
        self._dem, self._im = b"", 0.0

    async def async_close(self) -> None:
        self.stop_talking()
        if self._viec:
            await asyncio.gather(*self._viec)


class IntercomView(HomeAssistantView):
    """go2rtc POST luồng A-law 8 kHz vào đây (khoá riêng từng camera trong URL)."""

    url = "/api/dahua_talk/intercom/{entry_id}"
    name = "api:dahua_talk:intercom"
    requires_auth = False

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        entry = hass.config_entries.async_get_entry(entry_id)
        khoa = str(entry.data.get(CONF_INTERCOM_KEY) or "") if entry and entry.domain == DOMAIN else ""
        gui = request.query.get("k", "")
        if not khoa or not hmac.compare_digest(khoa.encode(), gui.encode()) \
                or getattr(entry, "runtime_data", None) is None:
            return web.Response(status=401)
        phien = Intercom(hass, entry.runtime_data.speaker)
        _LOGGER.debug("intercom %s: open", entry.title)
        try:
            while khuc := await request.content.readany():
                phien.feed(alaw_to_pcm(khuc))
        finally:
            await phien.async_close()
            _LOGGER.debug("intercom %s: closed, %.1f s played", entry.title, phien.seconds)
        return web.json_response({"seconds": round(phien.seconds, 1)})


CONF_INTERCOM_KEY = "intercom_key"


def go2rtc_source(hass: HomeAssistant, entry_id: str, key: str, ha_url: str = "") -> str:
    """Dòng nguồn dán vào go2rtc.yaml (cuối danh sách nguồn của luồng camera).

    ``ha_url`` = địa chỉ HA mà MÁY CHẠY go2rtc gọi tới được. Bỏ trống thì dùng
    ``127.0.0.1`` — chỉ đúng khi go2rtc dùng chung mạng với HA (add-on go2rtc của HA
    OS, hoặc cả hai container ``network_mode: host`` trên cùng máy). go2rtc ở máy/VM
    khác, trong Frigate, hay container mạng bridge thì phải truyền địa chỉ LAN của HA.

    go2rtc tách lệnh exec theo dấu cách và tham số theo '#': URL không được chứa hai
    ký tự ấy (khoá là token_urlsafe — không có).
    """
    goc = (ha_url or "").strip().rstrip("/")
    if not goc:
        http = getattr(hass, "http", None)
        cong = getattr(http, "server_port", None) or 8123
        # HA bật SSL trên cổng của nó thì phải gọi https (ffmpeg mặc định không kiểm
        # chứng chỉ, nên chứng chỉ cấp cho tên miền vẫn dùng được với 127.0.0.1).
        kieu = "https" if getattr(http, "ssl_certificate", None) else "http"
        goc = f"{kieu}://127.0.0.1:{cong}"
    url = f"{goc}/api/dahua_talk/intercom/{entry_id}?k={key}"
    return (f"exec:ffmpeg -hide_banner -loglevel error {_FFMPEG_TRUC_TIEP} "
            f"-f alaw -ar 8000 -ac 1 -i - -c:a copy -f alaw -flush_packets 1 "
            f"-method POST {url}#backchannel=1#audio=alaw/8000")
