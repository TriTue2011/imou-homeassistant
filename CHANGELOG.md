# Changelog

## 0.2.8 - 2026-09-26

### Tiếng ting không còn bị nghe thành câu lệnh
- Mic bỏ tiếng từ lúc bắt được từ gọi tới khi tiếng ting DỨT (gói cuối gửi đi + 0,4 s), không
  tới lúc đóng phiên loa. Đo thật: bản 0.2.7 để mic mở lúc kêu ting — 0,3 s sau từ gọi bộ dò
  tiếng đã thấy "tiếng" (ting lọt mic, đuôi từ gọi), 1,5 s sau coi là nói xong; nhận giọng
  bịa ra "Không", "Chị" khi người dùng chưa nói gì, câu lệnh thật sau đó bị bỏ, và tác tử
  hiểu "Không" là người dùng bác câu trả lời trước. Giả định "camera tự tắt mic khi loa phát"
  của 0.2.7 sai với ít nhất một camera.
- Từ gọi tiếng Việt «Trợ lý» cho openWakeWord: [wakeword/](wakeword/).

## 0.2.7 - 2026-09-26

### Không còn kẹt "Đang phản hồi"; ting xong là nói được ngay
- Gom tiếng TTS / thông báo có hạn (30 s): dịch vụ TTS trả luồng mà không đóng thì trước đây
  vệ tinh kẹt ở "Đang phản hồi" mãi, không về nghe (sự cố thật: 13 phút tới khi nạp lại).
- Tiếng ting KHÔNG còn chặn mic: trước đây bỏ tiếng mic tới lúc đóng xong phiên loa, nuốt mất
  đầu câu của người nói ngay sau tiếng ting. Camera vốn tự tắt mic khi loa phát. Ting có hạn 5 s.

### Ghi chú đo: gọi xa không phải vì tiếng nhỏ
Giảm giọng thật 12 / 18 / 24 dB (giả người đứng xa), `okay_nabu` vẫn bắt 4/4 với điểm như cũ —
openWakeWord tự chuẩn hoá độ to. Gọi xa hỏng vì vang phòng / tiếng nền, tăng mic không giúp mà
còn làm vỡ tiếng người nói gần. Giữ tăng mic 0 dB.

## 0.2.6 - 2026-09-26

### Lượt hỏng sau khi đã nghe không làm vệ tinh điếc
Gọi xong không nói gì (STT báo không ra chữ), tác tử hội thoại lỗi… trước đây vệ tinh coi là
pipeline hỏng: tắt mic, nghỉ 5 → 60 giây — gọi lại liền là trượt. Nay chỉ lượt hỏng NGAY
(dưới 3 giây, pipeline cấu hình sai) mới nghỉ; lượt đã nghe lâu hơn mà hỏng thì nghe lại ngay.

## 0.2.5 - 2026-09-26

### Tiếng "ting" khi bắt được từ gọi
Camera không có đèn báo như loa thông minh: gọi xong không biết nó đã nghe chưa. Nay bắt được
từ gọi thì loa camera kêu hai nốt ngắn (~0,3 s) — nghe "ting" rồi nói. Ngắn có chủ ý: camera
tự tắt mic lúc loa đang phát; trong lúc kêu, vệ tinh cũng bỏ tiếng mic để tiếng báo không lọt
vào câu lệnh. Tắt được bằng `switch.<camera>_wake_sound` ("Tiếng ting khi gọi").

Vệ tinh đợi ô chọn sẵn sàng theo nhịp 0,1 s (0.2.4 là 0,5 s — mic mở chậm không cần thiết).

## 0.2.4 - 2026-09-26

### Vệ tinh Assist không còn điếc im lặng
Sự cố thật: vệ tinh đứng `idle` hàng giờ, gọi từ gọi không ăn, log không một dòng.
- **Luồng mic đứng** (ffmpeg nối mà không ra byte nào): ffmpeg xuất PCM đều kể cả lúc phòng
  yên, nên quá 10 giây không có tiếng là luồng hỏng → tự mở lại, log
  `no audio from mic for 10 s, reopening`. Lỗi bất ngờ trong vòng đọc mic cũng chỉ ghi log
  rồi thử lại, không làm chết vòng đọc.
- **Nạp lại tích hợp**: vệ tinh chạy trước hai ô chọn của chính nó, lượt nghe đầu gặp
  `'unavailable' is not a valid VadSensitivity`, tắt mic và nghỉ tăng dần. Nay đợi ô chọn
  pipeline / độ nhạy có giá trị (tối đa 30 giây, quá thì dùng mặc định).

### README: tăng mic bắt đầu ở 0 dB
Đo thật: nói cách camera vài mét, `okay_nabu` vượt ngưỡng 5/6 lần ở 0 dB, 2/6 ở +20 dB, 1/6 ở
+30 dB — tăng quá tay làm vỡ tiếng. Chỉ tăng khi nói từ xa mà không bắt được.

## 0.2.3 - 2026-09-26

### Đổi tên hiển thị thành **Assist Camera**
Tích hợp không còn chỉ cho Dahua/Imou (có EZVIZ, Hikvision, camera ONVIF). Mã tích hợp vẫn
là `dahua_talk`: đổi mã là mọi camera, thực thể, automation và dòng `exec` trong
`go2rtc.yaml` đã cài phải làm lại — nên chỉ đổi tên hiển thị.

## 0.2.2 - 2026-09-26

### EZVIZ: tick "Nghe mic camera" thay vì gõ URL mic
URL mic luồng phụ (`/Streaming/Channels/102`) tự dựng từ IP + mật khẩu, mã hoá sẵn ký tự đặc
biệt (`@` → `%40` — lỗi hay gặp khi gõ tay), đổi mật khẩu thì URL đổi theo; form "Cấu hình
lại" không hiện URL có mật khẩu. Ô "URL mic khác" để đọc qua nguồn khác (go2rtc) vẫn thắng.
Nhãn mật khẩu EZVIZ ghi rõ "mã xác minh hoặc mật khẩu đã đổi".

Đo: mic camera EZVIZ tắt về gần 0 đúng lúc loa phát (camera tự tắt mic khi nói, như Imou);
phòng yên −70 dBFS → nên tăng mic +18 dB.

## 0.2.1 - 2026-09-26

### Thêm camera: chọn LOẠI camera trước
Bước đầu là menu **Imou / Dahua**, **EZVIZ**, **Hikvision / camera ONVIF khác**; mỗi loại
chỉ hỏi đúng ô nó cần. EZVIZ chỉ còn Tên, IP, **mã xác minh**, URL mic — tài khoản `admin`,
cổng 554, luồng `/Streaming/Channels/101` tự điền. "Cấu hình lại" hiện đúng ô của loại
camera đã chọn. Mục thêm từ bản cũ tự nhận loại (Dahua → Imou, RTSP → ONVIF).

### Đã gửi tiếng thật tới camera EZVIZ
Câu thử 5 giây (giọng TTS) gửi bằng đúng `RtspTalkSession` của tích hợp: camera mở kênh
trong 0,25 giây, nhận đủ, không lỗi. Chờ xác nhận nghe được ở loa.

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
