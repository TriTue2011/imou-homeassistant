# Changelog

## 0.2.0 - 2026-09-26

### Camera EZVIZ / Hikvision / ONVIF: nói qua kênh tiếng ngược RTSP
Ô mới **Cách nói ra loa** khi thêm (hoặc cấu hình lại) camera: *Dahua/Imou — cổng 37777*
(như cũ, mặc định) hoặc *RTSP/ONVIF*. RTSP: hỏi luồng kèm `Require:
www.onvif.org/ver20/backchannel`, mở đường tiếng `sendonly`, gửi RTP G.711 (PCMU, hoặc PCMA
nếu camera chỉ có PCMA) đúng nhịp; xác thực Digest; giữ phiên bằng `GET_PARAMETER`. Loa,
thông báo, vệ tinh Assist và bộ đàm dùng chung như camera Imou.

- Đo trên camera EZVIZ thật: không có ISAPI (404) nhưng RTSP có kênh ngược PCMU 8 kHz.
- Lúc thêm camera chỉ HỎI camera có kênh ngược (không phát tiếng); không có thì báo lỗi riêng.
- Chọn RTSP mà để cổng 37777 mặc định thì tự hiểu là 554.
- Mục cũ (không có ô cách nói) vẫn là Dahua — không phải cấu hình lại.
- G.711 tự mã hoá (audioop bị bỏ khỏi Python 3.13), khớp audioop cả 65.536 giá trị.
- Hướng dẫn riêng: `README_EZVIZ.md`.

## 0.1.3 - 2026-09-25

### Cấu hình lại camera mà không phải xoá
Menu ⋮ của camera (Thiết bị & dịch vụ → Dahua/Imou Talk) có thêm **Cấu hình lại**: sửa
IP, cổng, tài khoản, mật khẩu, *URL tiếng mic*. **Khoá bộ đàm được giữ** — dòng `exec:`
đã dán trong `go2rtc.yaml` vẫn đúng. Trước đây muốn thêm URL mic phải xoá camera rồi thêm
lại, khoá đổi, phải chép lại dòng go2rtc.

- Mật khẩu không điền sẵn (không gửi mật khẩu cũ ra trình duyệt); để trống là giữ cũ.
- Chỉ đổi *URL tiếng mic* thì không đăng nhập lại camera; đổi IP/tài khoản/mật khẩu thì
  đăng nhập thử **một** lần như lúc thêm.

## 0.1.2 - 2026-09-25

### Không kéo tiếng mic về khi pipeline đang lỗi
Pipeline Assist lỗi (chưa có từ gọi/STT…) thì vệ tinh nghỉ — nhưng ffmpeg vẫn đọc mic
camera liên tục cho không ai dùng (đo trên máy ARM: ~2,3% CPU cộng băng thông). Nay
trong lúc nghỉ, ffmpeg được tắt; hết nghỉ mới mở lại.

### README
Tên thực thể đúng như HA sinh ra (`entity_id` theo tên tiếng Anh, vd
`media_player.<camera>_speaker`), kể cả khi HA để tiếng Việt.

## 0.1.1 - 2026-09-25

### Sửa: HA treo cứng khi pipeline Assist lỗi ngay từ đầu
Có *URL tiếng mic* mà pipeline chưa dùng được (chưa có engine từ gọi — vd máy mới
cài chưa có openWakeWord — hoặc STT/TTS hỏng), pipeline báo lỗi và kết thúc trong vài
mili-giây; vệ tinh mở lại tức thì, hàng nghìn lượt mỗi giây, làm HA treo cứng (thêm
camera thì hộp thoại quay mãi). Nay pipeline lỗi thì vệ tinh nghỉ 5 giây, tăng dần tới
60 giây, ghi **một** dòng cảnh báo nói rõ lỗi; hai lượt luôn cách nhau ít nhất 1 giây.

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
