"""Bộ đàm trong HA: go2rtc POST A-law 8 kHz → loa camera, không cần dịch vụ ngoài."""

import asyncio
import math
import struct
from unittest import mock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.setup import async_setup_component

from custom_components.dahua_talk import intercom
from custom_components.dahua_talk.const import DOMAIN
from custom_components.dahua_talk.speaker import Speaker


def _song(giay: float, db: float) -> bytes:
    bien = 32767 * 10 ** (db / 20) * math.sqrt(2)
    n = int(giay * 8000)
    return struct.pack(f"<{n}h", *(int(bien * math.sin(2 * math.pi * 440 * i / 8000)) for i in range(n)))


def _im(giay: float) -> bytes:
    return b"\x00" * (int(giay * 8000) * 2)


def _alaw(pcm: bytes) -> bytes:
    """Mã hoá bằng tra ngược bảng giải — đủ cho đo mức."""
    import bisect
    goc = sorted(range(256), key=lambda a: intercom._ALAW[a])
    gt = [intercom._ALAW[a] for a in goc]
    ra = bytearray()
    for (x,) in struct.iter_unpack("<h", pcm):
        i = min(bisect.bisect_left(gt, x), 255)
        if i and abs(gt[i - 1] - x) <= abs(gt[i] - x):
            i -= 1
        ra.append(goc[i])
    return bytes(ra)


class LoaGia:
    def __init__(self):
        self.phien: list[bytes] = []

    async def async_play_pcm(self, chunks):
        du = b""
        async for c in chunks:
            du += c
        self.phien.append(du)
        return len(du) / 16000


def _day(ic, pcm, khuc=320):
    for i in range(0, len(pcm), khuc):
        ic.feed(pcm[i:i + khuc])


def test_giai_alaw_dung_moc_itu():
    # 0xD5 / 0x55 là hai mã gần 0 nhất (+8 / -8) trong bảng G.711 A-law.
    assert struct.unpack("<2h", intercom.alaw_to_pcm(bytes([0xD5, 0x55]))) == (8, -8)


async def test_im_khong_mo_loa_co_tieng_thi_mo_im_thi_dong(hass):
    loa = LoaGia()
    ic = intercom.Intercom(hass, loa)
    _day(ic, _im(2) + _song(1.0, -60))           # mic tắt / phòng yên
    await asyncio.sleep(0)
    assert loa.phien == [] and not ic._viec
    _day(ic, _song(1.0, -20))                    # nói
    _day(ic, _im(intercom.IM_GIAY + 0.1))        # im đủ lâu → đóng để nghe bên kia
    _day(ic, _song(0.5, -20))                    # câu sau → phiên mới
    await ic.async_close()
    assert len(loa.phien) == 2
    # Giữ ~0,3 s trước tiếng: âm đầu câu không mất.
    assert len(loa.phien[0]) >= int((1.0 + intercom.DEM_GIAY - 0.05) * 16000)


def _muc():
    return MockConfigEntry(domain=DOMAIN, title="Cam khách", data={
        "name": "Cam khách", "host": "192.168.1.65", "port": 37777,
        "username": "admin", "password": "mk", "mic_url": ""})


async def _nap(hass, muc):
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "http", {})
    muc.add_to_hass(hass)
    assert await hass.config_entries.async_setup(muc.entry_id)
    await hass.async_block_till_done()


async def test_khoa_sinh_mot_lan_va_giu_nguyen(hass):
    muc = _muc()
    await _nap(hass, muc)
    khoa = muc.data[intercom.CONF_INTERCOM_KEY]
    assert len(khoa) >= 24
    await hass.config_entries.async_reload(muc.entry_id)
    await hass.async_block_till_done()
    assert muc.data[intercom.CONF_INTERCOM_KEY] == khoa   # dòng đã dán vào go2rtc vẫn đúng


async def test_dich_vu_tra_dong_go2rtc(hass):
    muc = _muc()
    await _nap(hass, muc)
    from homeassistant.helpers import entity_registry as er
    mp = next(e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), muc.entry_id)
              if e.domain == "media_player")
    kq = await hass.services.async_call(DOMAIN, "get_intercom_source", {"entity_id": mp},
                                        blocking=True, return_response=True)
    nguon = kq["source"]
    assert nguon.startswith("exec:ffmpeg ") and nguon.endswith("#backchannel=1#audio=alaw/8000")
    assert "-probesize 32 -analyzeduration 0 -fflags nobuffer" in nguon   # trực tiếp, không gom
    url = next(t for t in nguon.split("#")[0].split() if t.startswith("http"))
    assert f"/api/dahua_talk/intercom/{muc.entry_id}?k={muc.data[intercom.CONF_INTERCOM_KEY]}" in url
    assert url.startswith("http://127.0.0.1:")


async def test_post_khoa_sai_bi_chan_khoa_dung_thi_phat(hass, hass_client_no_auth):
    muc = _muc()
    await _nap(hass, muc)
    loa = LoaGia()
    client = await hass_client_no_auth()
    duong = f"/api/dahua_talk/intercom/{muc.entry_id}"
    tieng = _alaw(_song(1.0, -20))
    with mock.patch.object(Speaker, "async_play_pcm", loa.async_play_pcm):
        assert (await client.post(duong, data=tieng)).status == 401
        assert (await client.post(duong + "?k=sai", data=tieng)).status == 401
        assert (await client.post("/api/dahua_talk/intercom/khong-co?k=x", data=tieng)).status == 401
        assert loa.phien == []
        r = await client.post(f"{duong}?k={muc.data[intercom.CONF_INTERCOM_KEY]}", data=tieng)
        assert r.status == 200
        assert (await r.json())["seconds"] > 0.9
    assert len(loa.phien) == 1


async def test_ha_url_cho_go2rtc_o_may_khac(hass):
    """Proxmox / Frigate / container mạng bridge: go2rtc không gọi được 127.0.0.1 của HA."""
    import pytest
    import voluptuous as vol

    muc = _muc()
    await _nap(hass, muc)
    from homeassistant.helpers import entity_registry as er
    mp = next(e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), muc.entry_id)
              if e.domain == "media_player")
    kq = await hass.services.async_call(DOMAIN, "get_intercom_source",
                                        {"entity_id": mp, "ha_url": "http://192.168.1.10:8123/"},
                                        blocking=True, return_response=True)
    assert f" http://192.168.1.10:8123/api/dahua_talk/intercom/{muc.entry_id}?k=" in kq["source"]
    for sai in ("192.168.1.10:8123", "http://a b:8123", "http://ha#x:8123"):
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(DOMAIN, "get_intercom_source",
                                           {"entity_id": mp, "ha_url": sai},
                                           blocking=True, return_response=True)
