"""Dahua/Imou Talk — mic và loa của camera Dahua/Imou thành vệ tinh Assist và loa trong HA.

Mỗi camera là một mục cấu hình, sinh ra:

* ``assist_satellite`` — nghe mic camera, chạy pipeline Assist của HA (từ gọi,
  nhận giọng, hiểu lệnh, đọc trả lời), trả lời ra loa camera; hội thoại nối tiếp
  khi câu trả lời là câu hỏi lại; ``assist_satellite.announce`` phát thông báo.
* ``media_player`` — ``tts.speak`` / ``media_player.play_media`` ra loa camera.
* ô chọn pipeline, ô chọn độ nhạy "nói xong", công tắc tắt mic, mức tăng mic.
* bộ đàm: mic điện thoại qua thẻ WebRTC Camera (go2rtc) → loa camera; dịch vụ
  ``dahua_talk.get_intercom_source`` trả dòng dán vào go2rtc.yaml.

Loa đi qua cổng 37777 của camera (giao thức nói của Dahua), hoặc qua kênh tiếng ngược
RTSP/ONVIF với camera EZVIZ/Hikvision/ONVIF (``rtsp_talk``). Mic đọc từ một URL
(luồng go2rtc hoặc RTSP) bằng ffmpeg của HA. Không cần dịch vụ nào ngoài HA.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (CONF_MIC_URL, CONF_RTSP_PATH, CONF_TALK, DEFAULT_PORT, DEFAULT_RTSP_PATH,
                    DOMAIN, TALK_RTSP)
from .intercom import CONF_INTERCOM_KEY, IntercomView, go2rtc_source
from .rtsp_talk import RtspTalkSession
from .speaker import Speaker
from .talk import TalkSession

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.ASSIST_SATELLITE, Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SELECT,
             Platform.SWITCH]


@dataclass
class DahuaTalkData:
    speaker: Speaker
    mic_url: str
    mic_muted: bool = False
    #: Khuếch đại mic (dB) trước khi đưa vào pipeline — mic camera nhỏ, nói cách
    #: 3 m không tới ngưỡng từ gọi (đo thật: phải +18 dB).
    mic_gain_db: float = 0.0
    _nghe_doi: list = field(default_factory=list)
    _nghe_tang: list = field(default_factory=list)

    @callback
    def set_mic_muted(self, tat: bool) -> None:
        self.mic_muted = tat
        for ham in list(self._nghe_doi):
            ham(tat)

    @callback
    def listen_mute(self, ham) -> callable:
        self._nghe_doi.append(ham)
        return lambda: self._nghe_doi.remove(ham)

    @callback
    def set_mic_gain(self, db: float) -> None:
        if db == self.mic_gain_db:
            return
        self.mic_gain_db = db
        for ham in list(self._nghe_tang):
            ham(db)

    @callback
    def listen_gain(self, ham) -> callable:
        self._nghe_tang.append(ham)
        return lambda: self._nghe_tang.remove(ham)


type DahuaTalkConfigEntry = ConfigEntry[DahuaTalkData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.http.register_view(IntercomView())

    async def _nguon_bo_dam(call: ServiceCall) -> ServiceResponse:
        entity_id = call.data["entity_id"]
        rec = er.async_get(hass).async_get(entity_id)
        entry = hass.config_entries.async_get_entry(rec.config_entry_id) if rec else None
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(f"{entity_id} is not a Dahua/Imou Talk entity")
        return {"source": go2rtc_source(hass, entry.entry_id, entry.data[CONF_INTERCOM_KEY],
                                        call.data.get("ha_url", ""))}

    hass.services.async_register(
        DOMAIN, "get_intercom_source", _nguon_bo_dam,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
            # Địa chỉ HA mà go2rtc gọi tới — bỏ trống khi go2rtc chung mạng với HA.
            vol.Optional("ha_url"): vol.All(
                str, vol.Match(r"^https?://[^\s#]+$",
                               msg="ha_url phải dạng http(s)://địa-chỉ:cổng, không dấu cách hay #")),
        }),
        supports_response=SupportsResponse.ONLY)
    return True


def _mo_phien_noi(d) -> callable:
    """Hàm mở một phiên nói theo cách camera hỗ trợ (mục cũ không có khoá này là Dahua)."""
    host, user, pw = d[CONF_HOST], d[CONF_USERNAME], d[CONF_PASSWORD]
    port = int(d.get(CONF_PORT, DEFAULT_PORT))
    if d.get(CONF_TALK) == TALK_RTSP:
        path = d.get(CONF_RTSP_PATH) or DEFAULT_RTSP_PATH
        return lambda: RtspTalkSession(host, user, pw, port=port, path=path)
    return lambda: TalkSession(host, user, pw, port=port)


async def async_setup_entry(hass: HomeAssistant, entry: DahuaTalkConfigEntry) -> bool:
    if not entry.data.get(CONF_INTERCOM_KEY):
        # Khoá bộ đàm riêng camera này, sinh một lần rồi giữ: dòng đã dán vào
        # go2rtc.yaml phải còn đúng sau mỗi lần khởi động lại HA.
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_INTERCOM_KEY: secrets.token_urlsafe(24)})
    d = entry.data
    entry.runtime_data = DahuaTalkData(
        speaker=Speaker(hass, _mo_phien_noi(d)),
        mic_url=str(d.get(CONF_MIC_URL) or ""),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DahuaTalkConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
