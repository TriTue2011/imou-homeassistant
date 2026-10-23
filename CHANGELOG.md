# Changelog

## 0.9.4 - 2026-10-24

- Icon riêng cho tích hợp trong Home Assistant (`brand/`: camera dome kèm bong bóng thoại, có bản cho nền tối).
  Home Assistant có hỗ trợ thư mục `brand/` tự nạp (đã thấy trong 2026.10.3; bản cũ hơn chưa kiểm). Không đổi mã.

## 0.9.3 - 2026-10-01

### EZVIZ (HCNetSDK): camera rớt mạng giữa bài không còn "đang phát" vào kết nối chết (issue #2)
- `hik_noi` kiểm kết quả `NET_DVR_VoiceComSendData` và nghe ngoại lệ `EXCEPTION_AUDIOEXCHANGE`
  (`NET_DVR_SetExceptionCallBack_V30`); hỏng thì báo `LOI` giữa lượt, đóng kênh nói, vẫn giữ đăng nhập.
- Phía HA đọc kênh báo không chặn khi gửi tiếng — thấy `LOI` thì dừng lượt (tự nối lại của 0.9.1 chạy được cho
  EZVIZ); luồng chuyển khung hỏng thì báo lỗi và tắt ffmpeg thay vì kẹt; chương trình trợ giúp tự thoát được thu
  dọn ngay (hết tiến trình `<defunct>`). `hik_noi-x86_64` dựng lại (glibc ≥ 2.34).

### Vệ tinh không tự đánh thức bằng đuôi câu trả lời của chính nó (issue #3)
- Mic vệ tinh bị bỏ khi loa CỦA CHÍNH camera đang phát và thêm một khoảng sau gói tiếng cuối — theo trạng thái
  loa, nên che cả khi phát qua `media_player` (`tts.speak`, nhạc).
- Ô số mới **Che mic sau khi nói** (giây, từng camera). Mặc định: HCNetSDK/EZVIZ 1,8 s, đường khác 0,5 s.

### Vệ tinh không còn điếc lặng / nạp lại không còn treo (issue #4)
- Chờ ffmpeg mic thoát sau khi tắt có hạn (5 s) — quá hạn thì ghi log và mở lại mic.
- Gỡ vệ tinh chờ vòng nghe tối đa 10 s; `Speaker.async_close` chờ khoá tối đa 10 s.
- Log lỗi dùng `repr` (không còn dòng `cannot play reply: ` trống); log debug mỗi lần mở mic.

## 0.9.2 - 2026-09-30

### Sửa: thanh tua hiện mà đứng yên
- Trên HA 2026.9 (Python 3.14) loa không đưa được `media_position` vào trạng thái dù đã đặt (bản 0.9.1 đo được:
  đang phát có `media_content_id` mà không có vị trí). Nay loa tự khai `media_position` /
  `media_position_updated_at` — thẻ phát nhạc tính được thời gian đang chạy.

## 0.9.1 - 2026-09-30

### Nhạc dài không còn bị cắt giữa bài
- Đo trên Imou thật: camera tự đóng kênh nói cổng 8086 sau 71–115 giây (nhạc im giữa bài, log "Broken pipe").
  Nay tích hợp gửi lại yêu cầu giữ phiên mỗi 30 giây — đo lại 200 giây liền không bị cắt.
- Dự phòng: camera vẫn cắt giữa bài thì tự nối lại và phát TIẾP đúng giây đang dở (tối đa 20 lần một bài;
  camera từ chối ngay thì thôi, không thử mãi).

### Thanh tua cho loa camera
- Loa báo bài đang phát và vị trí (`media_content_id`, `media_position`) và nhận **Tua** (`media_seek`) —
  thẻ phát nhạc (kể cả thẻ YouTube ở chế độ chỉ nghe) hiện thanh thời gian và tua được.

## 0.9.0 - 2026-09-30

### Sửa: loa camera "phát một lúc thì đơ, không Stop được" (và YouTube không phát được sau đó)
- Gặp thật 30/09/2026: loa Imou kẹt ở "playing" hơn 3 giờ. Soi trên máy: camera đã cắt kết nối cổng
  8086, luồng gửi thoát LẶNG, không còn ai đọc đầu ra của bộ mã hoá AAC → ống đầy → mọi thứ đứng chờ
  (`pipe_write`); Stop chờ theo mãi, và mọi lệnh phát sau đó (YouTube, TTS) cũng xếp hàng sau bài kẹt.
- Nay: camera cắt giữa bài thì báo lỗi ngay, loa về "idle"; cổng 37777 cũng không còn chờ gửi vô hạn
  (trước đặt `settimeout(None)`); Stop / Pause chờ tối đa 8 giây rồi huỷ — không bao giờ treo HA.
- Test tái hiện: camera giả cắt kết nối giữa bài — mã cũ kẹt, mã mới báo lỗi trong vài giây.

### Pause / Play, và thông báo chen ngang nhạc
- Loa camera có **Pause** và **Play**: tạm dừng nhớ đã phát tới đâu, Play phát tiếp từ đó.
- Thông báo / TTS (`tts.speak`, `announce`) tới lúc đang phát nhạc: nhạc tạm dừng, đọc xong phát tiếp
  đúng chỗ. Stop là dừng hẳn.

### Lưu ý: mic camera khi đang phát
- Camera Dahua/Imou TỰ TẮT MIC trong lúc có phiên nói (chống hú) — đầu ghi / Frigate không thu tiếng
  trong mấy giây đang đọc. Bản cũ kẹt phiên nói thì mic tắt suốt thời gian kẹt; nay phiên nói luôn đóng
  khi hết tiếng hoặc khi camera cắt.

## 0.8.0 - 2026-09-30

### Âm lượng loa từng camera
- Loa camera có `volume_set` (thanh âm lượng trên thẻ media, thẻ YouTube, `media_player.volume_set`):
  **50% = tiếng gốc** của camera, 100% = gấp đôi (+6 dB, chặn đỉnh để không vỡ tiếng), 0% = tắt tiếng.
  Mỗi camera nhớ mức riêng qua lần khởi động lại HA; camera mới mặc định 50% — kêu y như trước.
- Làm bằng phần mềm ngay trước khi gửi, nên chạy với MỌI loại camera (Imou 8086, Dahua 37777,
  EZVIZ/Hikvision qua RTSP hay HCNetSDK). Đổi lúc đang phát thì khúc kế tiếp theo ngay.
- Áp cho nhạc, thông báo, câu trả lời Assist; bộ đàm (tiếng người nói trực tiếp) giữ nguyên.

## 0.7.0 - 2026-09-30

### Loa camera: nhạc phát nền, có nút Dừng — không còn phải khởi động lại HA
- Trước: `play_media` (YouTube, nhạc) chờ tới khi phát hết bài mới trả về, và loa không có
  Stop — muốn im chỉ còn cách khởi động lại HA; HA còn mất cả phút mới tắt xong vì luồng phát
  đang gửi dở. Gặp thật 30/09/2026 khi phát YouTube ra loa camera phòng khách.
- Nay: nhạc phát nền, lệnh trả về ngay; bài mới thay bài đang phát (nút "bài sau" dùng được);
  thêm **Stop** (`media_player.media_stop`) — dừng sau khúc đang gửi (≤ 0,3 s), tắt ffmpeg.
- Thông báo (`announce`, `tts.speak`) vẫn chờ phát xong như cũ để nối tiếp nhau.
- HA tắt / gỡ camera: luồng phát thoát ngay, HA không phải chờ.

## 0.6.1 - 2026-09-29

### Sửa: tự tải HCNetSDK báo "sha256 mismatch"
- Bản 0.6.0 đọc gói bằng một lần `content.read(n)` — aiohttp chỉ trả phần đang có trong bộ đệm
  (đo thật: 16 384 / 10 015 050 byte), nên mã kiểm lệch và gói bị bỏ. Nay đọc từng khúc tới hết.
  Gặp thật trên HA OS 29/09/2026. Test mới giả đúng hành vi đọc từng phần của aiohttp.
- Đã cài 0.6.0: cập nhật lên 0.6.1 rồi ⋮ → Cấu hình lại camera EZVIZ để tải lại.

## 0.6.0 - 2026-09-29

### EZVIZ: tự tải HCNetSDK
- Thêm camera EZVIZ hoặc ⋮ → Cấu hình lại: máy HA x86_64 chưa có SDK thì tích hợp tự tải gói
  `lib` (~10 MB) từ repo riêng `TriTue2011/hcnetsdk-linux`, kiểm sha256 ghim sẵn, chỉ nhận mục
  trong `lib/`, giải qua thư mục tạm rồi mới đổi tên. Tải hỏng → kênh ngược RTSP như trước.
- Vì sao: đời EZVIZ không có kênh ngược RTSP báo `DESCRIBE failed (551)` mỗi lần phát (gặp thật
  29/09/2026 trên HA OS); trang tải của Hikvision chặn tải tự động (HTTP 403).
- Raspberry Pi (aarch64): chưa — cần bản trợ giúp `hik_noi-aarch64` và SDK ARM64.

## 0.5.0 - 2026-09-29

### Bộ đàm 16 kHz — tiếng điện thoại tới loa rõ như TTS
- Dòng go2rtc mới: `rtsp://<HA>:8557/<camera>/<khoá>#backchannel=1`. Tích hợp tự mở một máy
  chủ RTSP nhỏ (cổng 8557) khai rãnh kênh ngược `opus/48000/2`; go2rtc chọn Opus với trình duyệt
  và chuyển nguyên từng gói sang, HA giải mã bằng PyAV (có sẵn cho `stream`) ra đúng tần số loa —
  16 kHz với Imou 8086 và EZVIZ HCNetSDK. Không cần add-on.
- Vì sao: WebRTC của go2rtc 1.9.14 chỉ nhận từ trình duyệt Opus 48 kHz / PCMU / PCMA 8 kHz, còn
  lệnh `exec:` nhận dòng byte không ranh giới gói — chỉ G.711 8 kHz dùng được, cắt mất dải trên
  4 kHz. Đo thật: go2rtc đẩy 379 gói Opus trong 8 giây qua kênh xen TCP; test gửi tiếng 6 kHz
  qua trọn đường và tiếng ấy còn nguyên ở loa 16 kHz.
- `get_intercom_source` trả dòng `rtsp://` (kèm `exec_source` — dòng `exec:` 8 kHz cũ); HA thiếu
  bộ giải mã Opus hay cổng 8557 bị chiếm thì trả dòng `exec:` như trước. Dòng `exec:` đã dán vẫn
  chạy (khoá không đổi).

### Bộ đàm không tích trễ
- Chủ máy: "bị trễ so với thực tế". Đo trong HA: phát hết hàng đợi đúng nhịp thì cả lượt nói trễ
  đúng bằng lúc chờ mở kênh (tới 1,25 s khi camera vừa đóng kênh chưa nhả) cộng 0,3 s đệm đầu câu.
- Nay mỗi khúc tiếng bộ đàm mang lúc nó tới HA; khúc **im lặng** đã trễ quá 0,15 s thì bỏ — hàng
  đợi đuổi kịp qua các khoảng lặng (trước câu, giữa các từ), tiếng nói không bị bỏ. Đo trên H6C:
  mỗi lượt bỏ 0,18–1,76 s lặng.
- EZVIZ / Hikvision (HCNetSDK): nghỉ giữa câu 1,5–3,5 s thì câu sau vẫn trễ ~1,2 s — camera cần
  ~1,24 s mới cho mở lại kênh vừa đóng (mở bằng phiên đăng nhập khác cũng vậy), và mic camera câm
  suốt lúc kênh mở kể cả khi không gửi tiếng, nên không giữ kênh mở được. README ghi rõ.

### README
- Mục Bộ đàm viết lại cho dòng `rtsp://`; cách kiểm cổng 8557 bằng `nc`.
- "Không muốn mở cổng": STUN (không làm gì), ngrok có sẵn trong go2rtc, máy chủ TURN, VPN; vì sao
  Cloudflare Tunnel / Nabu Casa không chở mic cho go2rtc.

## 0.4.2 - 2026-09-29

### Bộ đàm EZVIZ / Hikvision: nói "alo, alo" không còn mất câu sau
- Sau khi đóng kênh đàm thoại, H6C cần ~1,2 s mới nhả kênh (đo: mở lại sau 1 s mất 259 ms, sau
  0,2 s mất 1036 ms, mở ngay thì camera từ chối "mã 29"). Bộ đàm đóng kênh sau 1,5 s im lặng để
  nghe bên kia, nên câu nói tiếp đúng lúc ấy bị từ chối và mất hẳn.
- Nay camera báo mã 29 lúc mở kênh thì chờ 0,3 s rồi mở lại, tối đa 3 s; tiếng nói trong lúc chờ
  vẫn nằm hàng đợi. Đo thật: 5 lượt nói nối liền đều phát (lượt sát nhau mở sau ~1,2 s).

## 0.4.1 - 2026-09-29

### Bộ đàm EZVIZ / Hikvision hết chậm: giữ đăng nhập HCNetSDK giữa các lượt nói
- Chủ máy thử bộ đàm H6C: "chậm hơn Imou". Đo trên H6C: đăng nhập SDK 0,6–1,3 s, đăng xuất
  0,5 s, còn mở kênh đàm thoại chỉ 0,02–0,27 s. Mỗi lượt nói trước đây đăng nhập lại từ đầu, tiếng
  bộ đàm dồn hàng đợi suốt lúc ấy nên cả câu phát trễ theo.
- Chương trình trợ giúp nay sống giữa các lượt: đăng nhập một lần, mỗi lượt chỉ mở / đóng kênh;
  kênh đóng mà ngồi yên 60 giây thì tự đăng xuất; chết giữa chừng (camera khởi động lại) thì lượt
  sau đăng nhập lại. Đo thật: lượt đầu mở kênh 393 ms, các lượt sau 26–37 ms.
- ffmpeg khởi động song song lúc camera mở kênh. Gỡ entry thì đăng xuất ngay.
- Imou không đổi: bắt tay cổng 8086 vốn chỉ ~0,03 s.

## 0.4.0 - 2026-09-28

### EZVIZ / Hikvision nói ra loa qua HCNetSDK (cổng 8000) — chạy cả trên HA OS
- EZVIZ H6C không có kênh tiếng ngược RTSP, không ONVIF, cổng HTTP bị khoá; có đời EZVIZ có kênh
  ngược mà loa câm (issue #1). HCNetSDK của Hikvision qua cổng 8000 thì mở được kênh đàm thoại:
  đo thật trên H6C — camera báo AAC 16 kHz, `tts.speak` phát rõ (chủ máy nghe xác nhận).
- Container HA (cả HA OS) là Alpine/musl, không nạp được HCNetSDK (glibc): tích hợp mang theo
  chương trình trợ giúp `hik/hik_noi-x86_64` (mã nguồn kèm) + bộ glibc nhỏ, chạy qua trình nạp
  glibc đi kèm như tiến trình con. HCNetSDK KHÔNG đi kèm — chép thư mục `lib` của "Device
  Network SDK (Linux 64-bit)" vào `/config/hcnetsdk/lib`.
- Thêm / cấu hình lại camera EZVIZ: có SDK thì tự chọn đường cổng 8000 (đăng nhập thử, không
  phát gì); không có thì giữ đường kênh ngược RTSP như trước. Lỗi "không có kênh ngược" nay chỉ
  cách cài SDK.

## 0.3.0 - 2026-09-28

### Loa camera Imou nói tiếng 16 kHz qua cổng 8086 — rõ hơn hẳn 8 kHz
- Kênh nói HTTP riêng của Imou (cổng 8086, `visualtalk.xav`, xác thực WSSE), tiếng AAC
  16 kHz do ffmpeg của HA mã hoá. Camera tự khai kênh nói là `MPEG4-GENERIC/16000`; cổng
  37777 chỉ nhận PCM 8 kHz, cắt mất dải trên 4 kHz (phụ âm s/x/ch). Nghe so sánh cùng câu
  trên camera Imou thật: 16 kHz rõ hơn. Bắt tay 8086 mất ~0,03 giây.
- Camera không mở 8086 hay từ chối thì tự lùi về 37777 (8 kHz) như trước, một giờ sau thử lại.
- Câu trả lời Assist xin TTS đúng tần số loa; tiếng ting sinh theo tần số loa; bộ đàm
  (A-law 8 kHz) được đổi lên 16 kHz trước khi gửi.
- Trình tự byte theo [ha-imou-talkback](https://github.com/vnp1978/ha-imou-talkback) (MIT),
  viết lại chạy ngay trong HA — không cần add-on.

## 0.2.9 - 2026-09-28

### Hết kẹt "Đang phản hồi" ở MỌI đường — vệ tinh luôn về chờ sau mỗi lượt
- Sự cố thật: câu trả lời có TTS nhưng không lấy được luồng tiếng → vệ tinh kẹt "Đang phản
  hồi" 18 giờ (không ting, gọi không nhận) tới khi nạp lại tích hợp. Home Assistant chỉ rời
  trạng thái này khi được báo `tts_response_finished`, mà trước đây chỉ đường phát câu trả lời
  báo. Nay vòng nghe tự báo khi lượt kết thúc và loa không còn phát — một chỗ cho mọi đường thoát.
- Phát thông báo bằng URL có hạn (300 s): loa treo thì bỏ, mic nghe lại — trước đây mic bỏ mọi
  tiếng tới khi loa trả lời, vệ tinh điếc mà không báo gì.

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
