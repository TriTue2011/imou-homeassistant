"""Hằng số của tích hợp Dahua/Imou Talk."""

DOMAIN = "dahua_talk"

CONF_MIC_URL = "mic_url"
DEFAULT_PORT = 37777

#: Cách nói ra loa camera: giao thức Dahua cổng 37777 (Imou/Dahua), hay kênh tiếng ngược
#: RTSP/ONVIF (EZVIZ, Hikvision, camera ONVIF có loa).
CONF_TALK = "talk_protocol"
TALK_DAHUA = "dahua"
TALK_RTSP = "rtsp"
CONF_RTSP_PATH = "rtsp_path"
DEFAULT_RTSP_PORT = 554
DEFAULT_RTSP_PATH = "/Streaming/Channels/101"

#: Tiếng mic đưa vào pipeline: PCM16 mono 16 kHz — định dạng Assist đòi.
MIC_RATE = 16000
MIC_CHUNK = 2048

#: Khuếch đại mic tối đa (dB). Cao hơn thì tiếng ồn nền cũng lớn theo.
MIC_GAIN_MAX = 30
