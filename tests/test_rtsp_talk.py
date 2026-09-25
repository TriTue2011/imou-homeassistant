"""Kênh tiếng ngược RTSP/ONVIF — camera giả nói đúng trình tự RTSP của camera EZVIZ thật.

SDP của camera giả chép từ camera EZVIZ thật (26/09/2026): chỉ khi được hỏi kèm
``Require: www.onvif.org/ver20/backchannel`` mới có đường tiếng ``sendonly`` (trackID=4).
"""

import hashlib
import re
import socket
import struct
import threading

import pytest

from custom_components.dahua_talk import rtsp_talk
from custom_components.dahua_talk.talk import AuthError


@pytest.fixture(autouse=True)
def _mo_socket(socket_enabled):
    yield


SDP_EZVIZ = """v=0
o=- 1 1 IN IP4 192.168.1.203
s=Media Presentation
t=0 0
a=control:rtsp://{host}/Streaming/Channels/101/
m=video 0 RTP/AVP 96
a=control:rtsp://{host}/Streaming/Channels/101/trackID=1
a=rtpmap:96 H264/90000
m=audio 0 RTP/AVP 104
a=recvonly
a=control:rtsp://{host}/Streaming/Channels/101/trackID=2
a=rtpmap:104 mpeg4-generic/16000/1
{nguoc}"""
NGUOC = """m=audio 0 RTP/AVP {pt} 104
a=rtpmap:{pt} {ten}/8000/1
a=sendonly
a=control:rtsp://{host}/Streaming/Channels/101/trackID=4
a=rtpmap:104 mpeg4-generic/16000/1
"""


class CameraRtsp:
    """Máy chủ RTSP giả: Digest bắt buộc, có/không có kênh ngược, ghi lại gói RTP nhận."""

    def __init__(self, mat_khau="mk", co_nguoc=True, pt=0):
        self.mat_khau, self.co_nguoc, self.pt = mat_khau, co_nguoc, pt
        self.ln = socket.create_server(("127.0.0.1", 0))
        self.ln.settimeout(0.1)
        self.cong = self.ln.getsockname()[1]
        self.dung = threading.Event()
        self.yeu_cau, self.rtp = [], []
        self.luong = [threading.Thread(target=self._nghe, daemon=True)]
        self.luong[0].start()

    def dong(self):
        self.dung.set()
        self.ln.close()
        for t in self.luong:
            t.join(5)

    def _nghe(self):
        while not self.dung.is_set():
            try:
                c, _ = self.ln.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            t = threading.Thread(target=self._phuc_vu, args=(c,), daemon=True)
            self.luong.append(t)
            t.start()

    def _dung_mk(self, dau, method, uri):
        m = re.search(r'response="([0-9a-f]+)"', dau)
        if not m:
            return False
        ha1 = hashlib.md5(f"admin:cam:{self.mat_khau}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        return m.group(1) == hashlib.md5(f"{ha1}:n0nce:{ha2}".encode()).hexdigest()

    def _tra(self, c, cseq, ma="200 OK", them="", than=""):
        c.sendall((f"RTSP/1.0 {ma}\r\nCSeq: {cseq}\r\n{them}"
                   f"Content-Length: {len(than.encode())}\r\n\r\n{than}").encode())

    def _phuc_vu(self, c):
        c.settimeout(0.2)
        du = b""
        while not self.dung.is_set():
            try:
                k = c.recv(65536)
            except TimeoutError:
                continue
            except OSError:
                break
            if not k:
                break
            du += k
            while du:
                if du[:1] == b"$":
                    if len(du) < 4:
                        break
                    n = struct.unpack(">H", du[2:4])[0]
                    if len(du) < 4 + n:
                        break
                    self.rtp.append((du[1], du[4:4 + n]))
                    du = du[4 + n:]
                    continue
                if b"\r\n\r\n" not in du:
                    break
                dau, _, du = du.partition(b"\r\n\r\n")
                dau = dau.decode()
                method, uri = dau.split(" ", 2)[:2]
                cseq = re.search(r"CSeq: (\d+)", dau).group(1)
                self.yeu_cau.append((method, uri, "Require: www.onvif.org/ver20/backchannel" in dau))
                if method in ("GET_PARAMETER", "TEARDOWN"):
                    self._tra(c, cseq)
                    continue
                if not self._dung_mk(dau, method, uri):
                    self._tra(c, cseq, "401 Unauthorized",
                              'WWW-Authenticate: Digest realm="cam", nonce="n0nce"\r\n')
                    continue
                host = f"127.0.0.1:{self.cong}"
                if method == "DESCRIBE":
                    nguoc = (NGUOC.format(pt=self.pt, ten="PCMU" if self.pt == 0 else "PCMA", host=host)
                             if self.co_nguoc and self.yeu_cau[-1][2] else "")
                    self._tra(c, cseq, them="Content-Type: application/sdp\r\n",
                              than=SDP_EZVIZ.format(host=host, nguoc=nguoc).replace("\n", "\r\n"))
                elif method == "SETUP":
                    self._tra(c, cseq, them="Session: 7777;timeout=60\r\n"
                              "Transport: RTP/AVP/TCP;unicast;interleaved=0-1\r\n")
                else:
                    self._tra(c, cseq, them="Session: 7777\r\n")
        c.close()


@pytest.fixture
def cam():
    cams = []

    def _tao(**kw):
        cams.append(CameraRtsp(**kw))
        return cams[-1]
    yield _tao
    for c in cams:
        c.dong()


def _cho_dong(c):
    """Camera giả đọc ở luồng riêng: chờ nó nhận tới TEARDOWN rồi mới xét gói đã nhận."""
    for _ in range(100):
        if any(m == "TEARDOWN" for m, _, _ in c.yeu_cau):
            return
        threading.Event().wait(0.02)


def test_ma_hoa_g711_dung_ban_chuan():
    """Giá trị lấy từ audioop.lin2ulaw / lin2alaw (bản chuẩn ITU; audioop bị bỏ ở Python 3.13)."""
    mau = struct.pack("<7h", 0, 1, -1, 1000, -1000, 32767, -32768)
    assert rtsp_talk.ma_hoa(mau, 0) == bytes([0xFF, 0xFF, 0x7E, 0xCE, 0x4E, 0x80, 0x00])
    assert rtsp_talk.ma_hoa(mau, 8) == bytes([0xD5, 0xD5, 0x55, 0xFA, 0x7A, 0xAA, 0x2A])


def test_tim_duong_tieng_nguoc_tu_sdp_ezviz():
    co = SDP_EZVIZ.format(host="h", nguoc=NGUOC.format(pt=0, ten="PCMU", host="h"))
    assert rtsp_talk.duong_tieng_nguoc(co) == ("rtsp://h/Streaming/Channels/101/trackID=4", 0)
    # Không hỏi kiểu ONVIF thì camera chỉ trả đường tiếng recvonly — không phải kênh ngược.
    assert rtsp_talk.duong_tieng_nguoc(SDP_EZVIZ.format(host="h", nguoc="")) is None


def test_phien_noi_gui_rtp_pcmu_dung_nhip_va_dong_phien(cam):
    c = cam()
    pcm = struct.pack("<800h", *([1000] * 800))                    # 0,1 giây 8 kHz
    with rtsp_talk.RtspTalkSession("127.0.0.1", "admin", "mk", port=c.cong) as s:
        s.send_pcm(pcm)
    _cho_dong(c)
    cac = [m for m, _, _ in c.yeu_cau]
    assert cac[:4] == ["DESCRIBE", "DESCRIBE", "SETUP", "PLAY"] and cac[-1] == "TEARDOWN"
    assert all(req for _, _, req in c.yeu_cau)                    # luôn hỏi kiểu ONVIF
    assert c.yeu_cau[2][1].endswith("/trackID=4")                  # SETUP đúng đường tiếng ngược
    goi = [g for kenh, g in c.rtp if kenh == 0]
    assert len(goi) == 5 and all(len(g) == 12 + 160 for g in goi)
    assert goi[0][1] == 0x80 and all(g[1] == 0 for g in goi[1:])   # marker gói đầu, PT 0 = PCMU
    seq = [struct.unpack(">H", g[2:4])[0] for g in goi]
    ts = [struct.unpack(">I", g[4:8])[0] for g in goi]
    assert all((b - a) & 0xFFFF == 1 for a, b in zip(seq, seq[1:]))
    assert all((b - a) & 0xFFFFFFFF == 160 for a, b in zip(ts, ts[1:]))
    assert goi[0][12:] == bytes([0xCE]) * 160


def test_camera_chi_co_pcma(cam):
    c = cam(pt=8)
    with rtsp_talk.RtspTalkSession("127.0.0.1", "admin", "mk", port=c.cong) as s:
        s.send_pcm(b"\x00\x00" * 160)
    _cho_dong(c)
    goi = [g for kenh, g in c.rtp if kenh == 0]
    assert goi and goi[0][1] & 0x7F == 8 and goi[0][12:] == bytes([0xD5]) * 160


def test_sai_mat_khau_bao_auth_error(cam):
    c = cam()
    with pytest.raises(AuthError):
        rtsp_talk.check_rtsp_talk("127.0.0.1", "admin", "sai", port=c.cong)


def test_luong_khong_co_kenh_nguoc(cam):
    c = cam(co_nguoc=False)
    with pytest.raises(rtsp_talk.NoBackchannelError):
        rtsp_talk.check_rtsp_talk("127.0.0.1", "admin", "mk", port=c.cong)
    assert not any(m == "SETUP" for m, _, _ in c.yeu_cau)          # chỉ hỏi, không mở phiên
