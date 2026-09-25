"""Nói ra loa camera qua kênh tiếng ngược RTSP/ONVIF (EZVIZ, Hikvision, camera ONVIF).

Python thuần, không phụ thuộc Home Assistant — cùng giao diện với ``talk.TalkSession``
(``with``, ``send_pcm``) để ``Speaker`` dùng chung.

Camera có kênh ngược thì khi được hỏi ``DESCRIBE`` kèm ``Require:
www.onvif.org/ver20/backchannel`` sẽ trả thêm một đường tiếng ``a=sendonly`` (chiều
camera NHẬN). Mở đường đó bằng ``SETUP`` (RTP chèn trong kết nối RTSP, TCP), ``PLAY``,
rồi gửi gói RTP G.711 đúng nhịp. Đo thật 26/09/2026 trên camera EZVIZ: không có ISAPI
(404), nhưng RTSP có kênh ngược PCMU 8 kHz; đủ năm bước đều 200.
"""

from __future__ import annotations

import array
import functools
import hashlib
import random
import re
import socket
import struct
import threading
import time

from .talk import KHOI, TAN_SO, AuthError, TalkError


class NoBackchannelError(TalkError):
    """Camera nói RTSP nhưng luồng này không có kênh tiếng ngược (không có loa, hoặc sai luồng)."""

CONG_RTSP = 554
#: Đường dẫn luồng chính kiểu Hikvision — EZVIZ dùng đúng đường này.
DUONG_MAC_DINH = "/Streaming/Channels/101"

_BACKCHANNEL = "Require: www.onvif.org/ver20/backchannel\r\n"
#: 20 ms mỗi gói RTP (160 mẫu 8 kHz) — nhịp chuẩn của G.711.
_MAU_GOI = 160
#: Nhắc camera là phiên còn sống; máy chủ RTSP thường cắt phiên im quá 60 giây.
_GIU_GIAY = 25.0


# ── G.711 (ITU-T), bản chuẩn của Sun g711.c. audioop đã bị bỏ khỏi Python 3.13. ──

def _doan(v: int, bien: tuple[int, ...]) -> int:
    for i, b in enumerate(bien):
        if v <= b:
            return i
    return len(bien)


def _ulaw(s: int) -> int:
    v = s >> 2
    mask = 0xFF
    if v < 0:
        v, mask = -v, 0x7F
    v = min(v, 8159) + 33
    seg = _doan(v, (0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF))
    if seg >= 8:
        return 0x7F ^ mask
    return ((seg << 4) | ((v >> (seg + 1)) & 0xF)) ^ mask


def _alaw(s: int) -> int:
    v = s >> 3
    if v >= 0:
        mask = 0xD5
    else:
        mask, v = 0x55, -v - 1
    seg = _doan(v, (0x1F, 0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF))
    if seg >= 8:
        return 0x7F ^ mask
    a = seg << 4
    a |= ((v >> 1) if seg < 2 else (v >> seg)) & 0xF
    return a ^ mask


@functools.lru_cache(maxsize=2)
def _bang(loai: int) -> bytes:
    """Bảng tra 65.536 mẫu PCM16 → một byte G.711, dựng lần đầu cần (không tốn lúc nạp)."""
    ham = _ulaw if loai == 0 else _alaw
    return bytes(ham(i - 65536 if i >= 32768 else i) for i in range(65536))


def ma_hoa(pcm: bytes, loai: int) -> bytes:
    """PCM16 LE mono → G.711 (``loai`` 0 = PCMU/µ-law, 8 = PCMA/A-law)."""
    bang = _bang(loai)
    return bytes(bang[x & 0xFFFF] for x in array.array("h", pcm))


# ── RTSP ────────────────────────────────────────────────────────────────────────

def _md5(x: str) -> str:
    # MD5 do giao thức (RFC 2617, xác thực Digest của RTSP) bắt buộc.
    return hashlib.md5(x.encode(), usedforsecurity=False).hexdigest()


def duong_tieng_nguoc(sdp: str) -> tuple[str, int] | None:
    """(control, payload) của đường tiếng camera NHẬN (sendonly) mang G.711; None nếu không có."""
    for m in re.split(r"\r?\n(?=m=)", sdp)[1:]:
        dong = m.splitlines()
        if not dong[0].startswith("m=audio") or "a=sendonly" not in dong:
            continue
        loai = [int(x) for x in dong[0].split()[3:] if x.isdigit()]
        ctl = next((d.split(":", 1)[1] for d in dong if d.startswith("a=control:")), "")
        for chon in (0, 8):                     # ưu tiên µ-law — bản mẫu ONVIF và EZVIZ đều có
            if chon in loai:
                return ctl, chon
    return None


class RtspTalkSession:
    """Một phiên nói qua kênh ngược RTSP. Dùng với ``with``. Chặn (blocking)."""

    def __init__(self, host: str, username: str, password: str, *, port: int = CONG_RTSP,
                 path: str = DUONG_MAC_DINH, timeout: float = 5.0) -> None:
        self.host, self.username, self.password = host, username, password
        self.port, self.timeout = port, timeout
        self.url = f"rtsp://{host}:{port}{path if path.startswith('/') else '/' + path}"
        self.sock: socket.socket | None = None
        self._cseq = 0
        self._xac_thuc: dict[str, str] | None = None
        self._phien = ""
        self._loai = 0
        self._seq = random.randint(0, 0xFFFF)
        self._ts = random.randint(0, 0xFFFFFFFF)
        self._ssrc = random.randint(0, 0xFFFFFFFF)
        self._dau = True
        self._khoa_gui = threading.Lock()
        self._dung = threading.Event()
        self._luong: list[threading.Thread] = []

    def __enter__(self) -> "RtspTalkSession":
        try:
            self._mo()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # -- yêu cầu / trả lời (chỉ dùng trước khi luồng nhận chạy) --

    def _doc_tra_loi(self) -> tuple[int, str, str]:
        du = b""
        while b"\r\n\r\n" not in du:
            c = self.sock.recv(4096)
            if not c:
                raise ConnectionError("camera closed the RTSP connection")
            du += c
            # Gói RTP/RTCP chèn giữa ("$" + kênh + độ dài) đứng trước trả lời: bỏ qua.
            while du[:1] == b"$" and len(du) >= 4:
                n = struct.unpack(">H", du[2:4])[0]
                if len(du) < 4 + n:
                    break
                du = du[4 + n:]
        dau, _, than = du.partition(b"\r\n\r\n")
        dau_s = dau.decode(errors="replace")
        m = re.search(r"Content-Length:\s*(\d+)", dau_s, re.I)
        while m and len(than) < int(m.group(1)):
            c = self.sock.recv(4096)
            if not c:
                break
            than += c
        ma = re.match(r"RTSP/1\.0 (\d{3})", dau_s)
        if not ma:
            raise TalkError("device does not speak RTSP on this port")
        return int(ma.group(1)), dau_s, than.decode(errors="replace")

    def _dau_xac_thuc(self, method: str, uri: str) -> str:
        x = self._xac_thuc
        if not x:
            return ""
        ha1 = _md5(f"{self.username}:{x['realm']}:{self.password}")
        ha2 = _md5(f"{method}:{uri}")
        if "qop" in x:
            nc, cn = "00000001", f"{random.getrandbits(64):016x}"
            r = _md5(f"{ha1}:{x['nonce']}:{nc}:{cn}:auth:{ha2}")
            them = f', qop=auth, nc={nc}, cnonce="{cn}"'
        else:
            r, them = _md5(f"{ha1}:{x['nonce']}:{ha2}"), ""
        return (f'Authorization: Digest username="{self.username}", realm="{x["realm"]}", '
                f'nonce="{x["nonce"]}", uri="{uri}", response="{r}"{them}\r\n')

    def _yeu_cau(self, method: str, uri: str, them: str = "", *, cho: bool = True
                 ) -> tuple[int, str, str]:
        for lan in range(2):
            self._cseq += 1
            with self._khoa_gui:
                self.sock.sendall((f"{method} {uri} RTSP/1.0\r\nCSeq: {self._cseq}\r\n"
                                   f"User-Agent: dahua_talk\r\n{_BACKCHANNEL}{them}"
                                   f"{self._dau_xac_thuc(method, uri)}\r\n").encode())
            if not cho:
                return 0, "", ""
            ma, dau, than = self._doc_tra_loi()
            if ma == 401 and lan == 0:
                w = re.search(r'WWW-Authenticate:\s*Digest\s+(.+)', dau, re.I)
                if not w:
                    raise AuthError("login refused: camera wants an unsupported auth scheme")
                self._xac_thuc = dict(re.findall(r'(\w+)="?([^",]+)"?', w.group(1)))
                continue
            if ma == 401:
                raise AuthError("login refused: wrong username or password")
            return ma, dau, than
        raise AuthError("login refused")

    # -- mở / phát / đóng --

    def _mo(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        ma, dau, sdp = self._yeu_cau("DESCRIBE", self.url, "Accept: application/sdp\r\n")
        if ma != 200:
            raise TalkError(f"DESCRIBE failed ({ma})")
        tim = duong_tieng_nguoc(sdp)
        if tim is None:
            raise NoBackchannelError("camera has no RTSP/ONVIF audio backchannel on this stream")
        ctl, self._loai = tim
        goc = re.search(r"Content-Base:\s*(\S+)", dau, re.I)
        goc = goc.group(1) if goc else self.url
        if not ctl.startswith("rtsp://"):
            ctl = goc.rstrip("/") + "/" + ctl.lstrip("/")
        ma, dau, _ = self._yeu_cau("SETUP", ctl, "Transport: RTP/AVP/TCP;unicast;interleaved=0-1\r\n")
        phien = re.search(r"Session:\s*([^;\r\n]+)", dau, re.I)
        if ma != 200 or not phien:
            raise TalkError(f"SETUP of the backchannel failed ({ma})")
        self._phien = phien.group(1).strip()
        ma, _, _ = self._yeu_cau("PLAY", goc, f"Session: {self._phien}\r\nRange: npt=0.000-\r\n")
        if ma != 200:
            raise TalkError(f"PLAY failed ({ma})")
        self.sock.settimeout(None)
        for dich, ten in ((self._xa, "rtsp-talk-rx"), (self._giu, "rtsp-talk-keepalive")):
            self._luong.append(threading.Thread(target=dich, name=ten, daemon=True))
            self._luong[-1].start()

    def _xa(self) -> None:
        """Đọc bỏ mọi thứ camera gửi (RTCP, trả lời giữ phiên) — không đọc thì đầy bộ đệm."""
        try:
            while not self._dung.is_set() and self.sock.recv(4096):
                pass
        except OSError:
            pass

    def _giu(self) -> None:
        goc = self.url
        while not self._dung.wait(_GIU_GIAY):
            try:
                self._yeu_cau("GET_PARAMETER", goc, f"Session: {self._phien}\r\n", cho=False)
            except OSError:
                return

    def send_pcm(self, pcm: bytes) -> None:
        """PCM16 LE mono 8 kHz → gói RTP G.711 20 ms, gửi đúng nhịp thời gian thực."""
        t0 = time.monotonic()
        buoc = _MAU_GOI * 2
        for i in range(0, len(pcm), buoc):
            tai = ma_hoa(pcm[i:i + buoc], self._loai)
            rtp = struct.pack(">BBHII", 0x80, (0x80 if self._dau else 0) | self._loai,
                              self._seq, self._ts, self._ssrc) + tai
            with self._khoa_gui:
                self.sock.sendall(b"$\x00" + struct.pack(">H", len(rtp)) + rtp)
            self._dau = False
            self._seq = (self._seq + 1) & 0xFFFF
            self._ts = (self._ts + len(tai)) & 0xFFFFFFFF
            cho = t0 + (i + buoc) / (2 * TAN_SO) - time.monotonic()
            if cho > 0:
                time.sleep(cho)

    def close(self) -> None:
        self._dung.set()
        if self.sock is not None:
            if self._phien:
                try:
                    self._yeu_cau("TEARDOWN", self.url, f"Session: {self._phien}\r\n", cho=False)
                except OSError:
                    pass
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
        self.sock = None
        for t in self._luong:
            if t is not threading.current_thread():
                t.join(2)


def check_rtsp_talk(host: str, username: str, password: str, port: int = CONG_RTSP,
                    path: str = DUONG_MAC_DINH) -> None:
    """Hỏi camera có kênh ngược (đăng nhập + DESCRIBE), không phát gì. Ném như ``talk.check_login``."""
    s = RtspTalkSession(host, username, password, port=port, path=path)
    try:
        s.sock = socket.create_connection((host, port), timeout=s.timeout)
        ma, _, sdp = s._yeu_cau("DESCRIBE", s.url, "Accept: application/sdp\r\n")
        if ma != 200:
            raise TalkError(f"DESCRIBE failed ({ma})")
        if duong_tieng_nguoc(sdp) is None:
            raise NoBackchannelError("camera has no RTSP/ONVIF audio backchannel on this stream")
    finally:
        s.close()


__all__ = ["CONG_RTSP", "DUONG_MAC_DINH", "KHOI", "NoBackchannelError", "RtspTalkSession",
           "check_rtsp_talk", "ma_hoa"]
