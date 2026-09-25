"""Loa của một camera, phía Home Assistant: nhận âm thanh (luồng PCM, WAV, URL) rồi phát.

Mỗi camera một lúc chỉ một phiên nói (``asyncio.Lock``): thông báo và câu trả lời
Assist cùng tới thì lần lượt. Phiên nói chạy trong luồng executor vì giao thức
chặn (socket đồng bộ, phát đúng nhịp thời gian thực).
"""

from __future__ import annotations

import asyncio
import io
import logging
import queue
import wave
from collections.abc import AsyncIterator

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.core import HomeAssistant

from .talk import KHOI, TAN_SO, TalkSession

_LOGGER = logging.getLogger(__name__)


class Speaker:
    def __init__(self, hass: HomeAssistant, host: str, port: int, username: str,
                 password: str) -> None:
        self.hass = hass
        self._host, self._port, self._user, self._pw = host, port, username, password
        self._lock = asyncio.Lock()
        self.playing = False

    def _phien(self, hang: "queue.Queue[bytes | None]") -> float:
        """Luồng executor: mở kênh nói, rút PCM 8 kHz từ hàng đợi và phát. Trả số giây."""
        giay = 0.0
        with TalkSession(self._host, self._user, self._pw, port=self._port) as s:
            du = b""
            while (khuc := hang.get()) is not None:
                du += khuc
                n = len(du) // KHOI * KHOI
                if n:
                    s.send_pcm(du[:n])
                    giay += n / (2 * TAN_SO)
                    du = du[n:]
            if du:
                s.send_pcm(du)
                giay += len(du) / (2 * TAN_SO)
        return giay

    async def async_play_pcm(self, chunks: AsyncIterator[bytes]) -> float:
        """Phát luồng PCM16 mono 8 kHz. Trả số giây đã phát."""
        async with self._lock:
            hang: queue.Queue[bytes | None] = queue.Queue()
            self.playing = True
            viec = self.hass.async_add_executor_job(self._phien, hang)
            try:
                try:
                    async for khuc in chunks:
                        hang.put(khuc)
                finally:
                    hang.put(None)          # luôn đóng phiên nói, kể cả khi nguồn hỏng
                return await viec
            finally:
                self.playing = False

    async def _ffmpeg_8k(self, args_vao: list[str], du_lieu: bytes | None = None
                         ) -> AsyncIterator[bytes]:
        """Đổi nguồn bất kỳ sang PCM16 mono 8 kHz bằng ffmpeg của HA, nhả dần."""
        proc = await asyncio.create_subprocess_exec(
            get_ffmpeg_manager(self.hass).binary, "-nostdin", "-hide_banner",
            "-loglevel", "error", *args_vao,
            "-vn", "-ac", "1", "-ar", str(TAN_SO), "-f", "s16le", "pipe:",
            stdin=asyncio.subprocess.PIPE if du_lieu is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        if du_lieu is not None:
            proc.stdin.write(du_lieu)
            proc.stdin.close()
        try:
            while khuc := await proc.stdout.read(KHOI * 8):
                yield khuc
        finally:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()

    async def async_play_url(self, url: str) -> float:
        """Phát một URL (media source đã phân giải, tệp, luồng HTTP…)."""
        return await self.async_play_pcm(self._ffmpeg_8k(
            ["-protocol_whitelist", "http,https,file,tcp,tls", "-i", url]))

    async def async_play_wav(self, data: bytes) -> float:
        """Phát một tệp WAV. Đúng sẵn PCM16 mono 8 kHz thì khỏi qua ffmpeg."""
        try:
            with wave.open(io.BytesIO(data), "rb") as w:
                dung = (w.getframerate(), w.getsampwidth(), w.getnchannels()) == (TAN_SO, 2, 1)
                pcm = w.readframes(w.getnframes()) if dung else b""
        except (wave.Error, EOFError):
            dung = False
        if dung:
            async def _mot():
                yield pcm
            return await self.async_play_pcm(_mot())
        return await self.async_play_pcm(self._ffmpeg_8k(["-i", "pipe:"], data))
