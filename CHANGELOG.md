# Changelog

## 0.1.0 - 2026-09-25

Bản công khai đầu tiên.

### Loa camera
- `media_player.<camera>_loa`: `tts.speak`, `media_player.play_media` (tệp, URL,
  media source) ra loa camera Imou/Dahua qua cổng TCP 37777 — cho cả camera không có
  kênh ngược RTSP/ONVIF.

### Vệ tinh Assist
- `assist_satellite.<camera>`: nghe mic camera (URL go2rtc/RTSP), chạy pipeline
  Assist, trả lời ra loa. Câu trả lời là câu hỏi lại thì nghe tiếp, không cần từ gọi.
- `number.<camera>_tang_mic`: tăng mic 0–30 dB; luôn lọc bỏ độ lệch DC của mic
  camera trước khi tăng, chặn đỉnh để không vỡ tiếng.
- `switch.<camera>_tat_mic`, chọn pipeline, chọn độ nhạy "nói xong".

### Bộ đàm
- Nói qua camera bằng mic điện thoại trong thẻ WebRTC Camera: go2rtc (≥ 1.9.10) đẩy
  tiếng qua kênh ngược `exec` vào HA, HA phát ra loa camera. Loa chỉ mở khi có tiếng
  người và đóng sau 1,5 giây im (camera tắt mic lúc loa mở).
- Dịch vụ `dahua_talk.get_intercom_source` trả dòng dán vào `go2rtc.yaml`; trường
  `ha_url` cho go2rtc chạy ở máy/VM/container khác hoặc trong Frigate.
