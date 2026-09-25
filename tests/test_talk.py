"""Giao thức nói Dahua 37777 — camera giả nói đúng trình tự khung byte.

Băm mật khẩu đã đo trên máy thật: bốn camera Imou nhận đăng nhập, loa phát được.
"""

import socket
import struct
import threading
import time
from unittest import mock

import pytest

from custom_components.dahua_talk import talk

# Camera giả nghe trên 127.0.0.1 — bộ test HA chặn socket nên mở riêng cho tệp này.
@pytest.fixture(autouse=True)
def _mo_socket(socket_enabled):
    yield


class CameraGia:
    def __init__(self, phien=1002, ly_do=0):
        self.phien, self.ly_do = phien, ly_do
        self.ln = socket.create_server(("127.0.0.1", 0))
        self.ln.settimeout(0.1)        # accept() không tự thức khi đóng từ luồng khác
        self.dung = threading.Event()
        self.cong = self.ln.getsockname()[1]
        self.chu, self.tieng, self.dang_nhap = [], [], 0
        self.luong = [threading.Thread(target=self._nghe, daemon=True)]
        self.luong[0].start()

    def dong(self):
        """Bộ test HA đòi không còn luồng nào sống sau mỗi test."""
        self.dung.set()
        self.ln.close()
        for t in self.luong:
            t.join(5)

    def _gui(self, c, cmd, than=b"", phien=0, ly_do=0):
        h = bytearray(32)
        h[0] = cmd
        h[4:8] = struct.pack("<I", len(than))
        h[8] = ly_do
        h[16:20] = struct.pack("<I", phien)
        c.sendall(bytes(h) + than)

    def _nghe(self):
        while not self.dung.is_set():
            try:
                c, _ = self.ln.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            c.settimeout(None)
            t = threading.Thread(target=self._phuc_vu, args=(c,), daemon=True)
            self.luong.append(t)
            t.start()

    def _phuc_vu(self, c):
        try:
            while True:
                h, b = talk.doc_khung(c)
                if h[0] == 0xA0 and not b:
                    self._gui(c, 0xB0, b"Realm:Login to GIA\r\nRandom:12345\r\n")
                elif h[0] == 0xA0:
                    self.dang_nhap += 1
                    self._gui(c, 0xB0, phien=self.phien, ly_do=self.ly_do)
                elif h[0] == 0xF4:
                    s = b.decode()
                    self.chu.append(s)
                    if "AddObject" in s and "DeleteObject" not in s:
                        self._gui(c, 0xF4, b"AddObjectResponse\r\nFaultCode:OK\r\nConnectionID:77\r\n")
                    elif "AckSubChannel" in s:
                        self._gui(c, 0xF4, b"AckSubChannel\r\nFaultCode:OK\r\n")
                elif h[0] == 0x1D:
                    self.tieng.append(h + b)
        except (OSError, ConnectionError):
            pass


def test_phien_noi_dung_trinh_tu_va_khung_tieng():
    cam = CameraGia()
    pcm = b"\x10\x00" * 1000
    with mock.patch.object(talk.time, "sleep"):
        with talk.TalkSession("127.0.0.1", "admin", "mk", port=cam.cong) as s:
            s.send_pcm(pcm)
    for _ in range(250):
        if any("DeleteObject" in x for x in cam.chu) and sum(len(t) - 40 for t in cam.tieng) == len(pcm):
            break
        time.sleep(0.02)
    thu_tu = [next(m for m in ("AddObject", "AckSubChannel", "State:1", "State:0", "DeleteObject") if m in x)
              for x in cam.chu]
    assert thu_tu == ["AddObject", "AckSubChannel", "State:1", "State:0", "DeleteObject"]
    assert "Channel:0" in cam.chu[2] and "Frequency:8000" in cam.chu[2]
    assert [len(t) - 40 for t in cam.tieng] == [640, 640, 640, 80]
    assert cam.tieng[0][32:38] == b"\x00\x00\x01\xF0\x0C\x02"
    assert b"".join(t[40:] for t in cam.tieng) == pcm
    cam.dong()


def test_sai_mat_khau_khong_thu_lai():
    cam = CameraGia(phien=0, ly_do=1)
    with pytest.raises(talk.AuthError, match="wrong password"):
        talk.check_login("127.0.0.1", "admin", "sai", cam.cong)
    assert cam.dang_nhap == 1
    cam.dong()


def test_khong_phai_camera_dahua():
    ln = socket.create_server(("127.0.0.1", 0))

    def tra_rac():
        c, _ = ln.accept()
        c.recv(64)
        c.sendall(b"\xB0" + b"\x00" * 31)
    t = threading.Thread(target=tra_rac, daemon=True)
    t.start()
    with pytest.raises(talk.TalkError, match="does not speak"):
        talk.check_login("127.0.0.1", "u", "p", ln.getsockname()[1])
    ln.close()
    t.join(5)
