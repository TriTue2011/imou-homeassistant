"""Hằng số của tích hợp Dahua/Imou Talk."""

DOMAIN = "dahua_talk"

CONF_MIC_URL = "mic_url"
DEFAULT_PORT = 37777

#: Tiếng mic đưa vào pipeline: PCM16 mono 16 kHz — định dạng Assist đòi.
MIC_RATE = 16000
MIC_CHUNK = 2048

#: Khuếch đại mic tối đa (dB). Cao hơn thì tiếng ồn nền cũng lớn theo.
MIC_GAIN_MAX = 30
