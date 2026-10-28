"""Loa camera khai lý do idle (``idle_reason``) để tích hợp phát nhạc (YouTube) phân biệt hết bài / Stop / bị bài mới thay / lỗi,
thay vì đoán bằng thời lượng bài (chủ máy 28/10/2026: «Stop hay không thì lấy event hoặc trigger là được mà nhỉ»)."""

import asyncio
from unittest import mock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.dahua_talk.const import DOMAIN
from custom_components.dahua_talk.talk import TalkError


async def _nap(hass):
    muc = MockConfigEntry(domain=DOMAIN, title="Cam cửa", data={
        "name": "Cam cửa", "host": "192.168.1.64", "port": 37777, "username": "admin", "password": "mk", "mic_url": ""})
    assert await async_setup_component(hass, "homeassistant", {})
    muc.add_to_hass(hass)
    assert await hass.config_entries.async_setup(muc.entry_id)
    await hass.async_block_till_done()
    mp = next(e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), muc.entry_id)
              if e.domain == "media_player")
    return muc, mp


async def _phat(hass, mp):
    await hass.services.async_call("media_player", "play_media", {
        "entity_id": mp, "media_content_id": "http://x/a.mp3", "media_content_type": "music"}, blocking=True)


def _ly_do(hass, mp):
    st = hass.states.get(mp)
    return st.state, st.attributes.get("idle_reason")


async def test_bai_tu_het_thi_idle_reason_la_finished(hass):
    muc, mp = await _nap(hass)
    with mock.patch.object(muc.runtime_data.speaker, "async_play_url", return_value=1.0):
        await _phat(hass, mp)
        await hass.async_block_till_done()
    assert _ly_do(hass, mp) == ("idle", "finished")


async def test_nguoi_dung_bam_stop_thi_idle_reason_la_stopped(hass):
    muc, mp = await _nap(hass)
    xong = asyncio.Event()

    async def phat_mai(url, huy, tu_giay=0.0):
        while not huy.is_set():
            await asyncio.sleep(0.01)
        xong.set()
        return 1.0

    with mock.patch.object(muc.runtime_data.speaker, "async_play_url", side_effect=phat_mai):
        await _phat(hass, mp)
        assert hass.states.get(mp).state == "playing" and "idle_reason" not in hass.states.get(mp).attributes
        await hass.services.async_call("media_player", "media_stop", {"entity_id": mp}, blocking=True)
        await hass.async_block_till_done()
    assert _ly_do(hass, mp) == ("idle", "stopped")


async def test_phat_bai_moi_de_len_bai_cu_thi_bao_interrupted(hass):
    muc, mp = await _nap(hass)
    cac_lan_idle = []

    @callback
    def ghi(event):
        st = event.data["new_state"]
        if event.data["entity_id"] == mp and st is not None and st.state == "idle":
            cac_lan_idle.append(st.attributes.get("idle_reason"))

    hass.bus.async_listen("state_changed", ghi)

    async def phat_mai(url, huy, tu_giay=0.0):
        while not huy.is_set():
            await asyncio.sleep(0.01)
        return 1.0

    with mock.patch.object(muc.runtime_data.speaker, "async_play_url", side_effect=phat_mai):
        await _phat(hass, mp)
        await _phat(hass, mp)                               # bài mới thay bài đang phát
        await hass.services.async_call("media_player", "media_stop", {"entity_id": mp}, blocking=True)
        await hass.async_block_till_done()
    assert cac_lan_idle[0] == "interrupted", cac_lan_idle
    assert cac_lan_idle[-1] == "stopped"


async def test_loi_phat_thi_idle_reason_la_error(hass):
    muc, mp = await _nap(hass)
    with mock.patch.object(muc.runtime_data.speaker, "async_play_url", side_effect=TalkError("camera từ chối")):
        await _phat(hass, mp)
        await hass.async_block_till_done()
    assert _ly_do(hass, mp) == ("idle", "error")
