# EZVIZ (và Hikvision, camera ONVIF có loa) — loa, bộ đàm, vệ tinh Assist

Tích hợp **Dahua/Imou Talk** từ bản **0.2.0** nói được với camera **EZVIZ** qua **kênh
tiếng ngược RTSP/ONVIF** — cùng các thực thể như camera Imou: loa (`tts.speak`), vệ tinh
Assist, bộ đàm qua thẻ WebRTC. Chạy hoàn toàn trong mạng nhà, **không qua đám mây EZVIZ**,
không cần tài khoản nhà phát triển EZVIZ.

Hướng dẫn chung (SmartPSS, Assist, mở cổng 4G, go2rtc, bảo mật) ở [README chính](README.md);
trang này chỉ ghi phần **khác** của EZVIZ.

**Mục lục**

1. [Vì sao EZVIZ đi đường khác Imou](#vì-sao-ezviz-đi-đường-khác-imou)
2. [Chuẩn bị camera](#chuẩn-bị-camera)
3. [Thêm camera vào tích hợp](#thêm-camera-vào-tích-hợp)
4. [go2rtc và bộ đàm](#go2rtc-và-bộ-đàm)
5. [Thẻ WebRTC Camera](#thẻ-webrtc-camera)
6. [Vệ tinh Assist](#vệ-tinh-assist)
7. [Sự cố thường gặp](#sự-cố-thường-gặp)
8. [Đã kiểm những gì](#đã-kiểm-những-gì)

---

## Vì sao EZVIZ đi đường khác Imou

| | Imou / Dahua | EZVIZ |
|---|---|---|
| Đường nói ra loa | Giao thức riêng cổng **37777** | **Kênh tiếng ngược RTSP** (chuẩn ONVIF), cổng **554** |
| ISAPI (API web của Hikvision) | — | **Thường không có** (đo trên camera thật: mọi `/ISAPI/…` trả 404) |
| SDK của EZVIZ | — | Bắt đi qua đám mây (`appKey`, `accessToken`), tự lấy mic máy tính — **không dùng được** cho HA |

Kênh tiếng ngược: khi được hỏi luồng RTSP kèm dấu hiệu ONVIF (`Require:
www.onvif.org/ver20/backchannel`), camera trả thêm một **đường tiếng chiều camera nhận**
(G.711 PCMU 8 kHz). Tích hợp mở đường đó rồi gửi tiếng — đúng cách go2rtc làm với camera
có kênh ngược.

## Chuẩn bị camera

1. **IP tĩnh** (hoặc giữ chỗ DHCP trên router) cho camera.
2. **Tài khoản:** `admin` + **mã xác minh** (6 chữ IN HOA trên tem dưới đáy camera / trong
   hộp). Đổi mã xác minh trong app EZVIZ thì đổi luôn mật khẩu RTSP.
3. **Mã hoá hình H.264** (app EZVIZ → cài đặt camera → Mã hoá / Video): trình duyệt xem
   WebRTC H.265 rất kém.
4. Một số đời EZVIZ phải **bật RTSP / xem qua mạng LAN** trong app mới mở cổng 554.
5. **Sai mật khẩu vài lần là camera khoá đăng nhập** một lúc — tích hợp chỉ thử một lần mỗi
   lần bấm.

**Đường dẫn luồng** (kiểu Hikvision): luồng chính `/Streaming/Channels/101`, luồng phụ
`/Streaming/Channels/102`.

## Thêm camera vào tích hợp

Cài đặt → Thiết bị & dịch vụ → **Thêm tích hợp** → **Dahua/Imou Talk** → chọn loại
**EZVIZ**. Chỉ phải điền:

| Ô | Điền |
|---|---|
| Tên | vd `Cam EZVIZ` |
| IP camera | IP trong mạng nhà |
| Mã xác minh | 6 chữ IN HOA trên tem dưới đáy camera |
| URL tiếng mic | để trống nếu chỉ cần loa + bộ đàm — xem [Vệ tinh Assist](#vệ-tinh-assist) |

Tài khoản `admin`, cổng `554`, luồng `/Streaming/Channels/101` tích hợp tự điền. Camera
Hikvision / ONVIF khác (đường dẫn luồng khác) thì chọn loại **Hikvision / camera ONVIF
khác** — có đủ ô cổng, đường dẫn, tài khoản.

Lúc bấm gửi, tích hợp **chỉ hỏi** camera có kênh ngược không (không phát tiếng):

- báo **"không có kênh tiếng ngược"** → camera không có loa, hoặc sai đường dẫn luồng;
- báo **sai đăng nhập** → kiểm lại mã xác minh (và chờ vài phút nếu vừa sai nhiều lần).

Thử loa:

```yaml
action: tts.speak
target: {entity_id: tts.piper}          # engine TTS của bạn
data:
  media_player_entity_id: media_player.cam_ezviz_speaker
  message: "Thử loa camera"
```

Sửa IP, mật khẩu, đường dẫn sau khi thêm: ⋮ cạnh camera → **Cấu hình lại** (khoá bộ đàm
giữ nguyên).

## go2rtc và bộ đàm

Mật khẩu có `@` thì trong URL phải viết `%40` (vd `Abc@123` → `Abc%40123`).

**Cách A — chỉ cần bộ đàm, đơn giản nhất:** go2rtc tự dùng kênh ngược của RTSP, không
cần dòng `exec`. Lưu ý: thêm **bất kỳ** tuỳ chọn `#…` nào vào URL RTSP (vd `#timeout=30`)
là go2rtc **tắt** kênh ngược, trừ khi kèm `#backchannel=1` (đọc từ mã go2rtc
`internal/rtsp/rtsp.go`):

```yaml
streams:
  cam_ezviz:
    - rtsp://admin:MA_XAC_MINH@192.168.1.64:554/Streaming/Channels/101
    - ffmpeg:cam_ezviz#audio=opus          # tiếng camera cho WebRTC (AAC không qua WebRTC được)
  cam_ezviz_sub:
    - rtsp://admin:MA_XAC_MINH@192.168.1.64:554/Streaming/Channels/102
```

**Cách B — có dùng loa / Assist của tích hợp (khuyên dùng khi đó):** bộ đàm đi qua tích hợp
như camera Imou, để **dùng chung một phiên nói** với `tts.speak`, thông báo và câu trả lời
Assist (cái nào tới trước phát trước), và chỉ mở loa khi có tiếng người. Tắt kênh ngược
riêng của go2rtc (`#backchannel=0`) — hai bên cùng mở kênh ngược thì camera chỉ nhận một:

```yaml
streams:
  cam_ezviz:
    - rtsp://admin:MA_XAC_MINH@192.168.1.64:554/Streaming/Channels/101#backchannel=0
    - ffmpeg:cam_ezviz#audio=opus
    - "exec:ffmpeg … #backchannel=1#audio=alaw/8000"   # dòng từ dahua_talk.get_intercom_source
```

Lấy dòng `exec` và chọn `ha_url`: [README chính → Bộ đàm](README.md#bộ-đàm) (y hệt Imou).

Xem / nói từ xa qua 4G: [README chính → Xem và nói từ xa](README.md#xem-và-nói-từ-xa-4g)
(mở cổng 8555/TCP, máy go2rtc không đi VPN, mạng `172.16–31.x.x` thì thêm `filters: ips`).

## Thẻ WebRTC Camera

```yaml
type: custom:webrtc-camera
ui: true
streams:
  - url: cam_ezviz
    name: 🔇
    media: video,audio
  - url: cam_ezviz            # CÙNG camera — đừng trỏ sang luồng camera khác
    name: 🎙️
    media: video,audio,microphone
style: |
  .screenshot, .pictureinpicture { display: none !important; }
  .controls ha-icon { --mdc-icon-size: 20px; }
  .stream { font-size: 18px !important; margin-left: 6px !important; }
```

Bấm 🔇 ↔ 🎙️ để tắt/mở mic. Mic chỉ chạy khi HA mở bằng **https**.

## Vệ tinh Assist

Như camera Imou ([README chính → Vệ tinh Assist](README.md#vệ-tinh-assist-từ-gọi-tăng-mic)),
chỉ khác URL tiếng mic — đọc luồng phụ:

- qua go2rtc: `http://IP_GO2RTC:1984/api/stream.mp4?src=cam_ezviz_sub&video=none&audio=all`
- hoặc thẳng RTSP: `rtsp://admin:MA_XAC_MINH@IP_CAMERA:554/Streaming/Channels/102`

Chỉ điền khi HA đã có pipeline đủ từ gọi + STT + TTS. Camera hướng ra ngoài: đừng cho nghe.

## Sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Thêm camera báo "không có kênh tiếng ngược" | Camera không có loa, sai đường dẫn luồng, hoặc firmware tắt kênh ngược | Thử `/Streaming/Channels/101`; camera không loa thì chỉ xem được |
| Báo sai đăng nhập dù đúng mã | Camera đang khoá sau nhiều lần sai | Chờ vài phút, thử **một** lần |
| Không nối được cổng 554 | RTSP chưa bật / IP sai | Bật RTSP / xem qua LAN trong app EZVIZ; kiểm IP |
| Cách B: nói không ra loa, go2rtc báo lỗi kênh ngược | Quên `#backchannel=0` — go2rtc và tích hợp cùng mở kênh ngược | Thêm `#backchannel=0` vào URL RTSP |
| WebRTC không có hình | Luồng H.265 | Đổi sang H.264 trong app EZVIZ |
| Mật khẩu có `@` làm go2rtc báo sai địa chỉ | `@` trong URL | Viết `%40` |

## Đã kiểm những gì

Trên một camera EZVIZ thật (26/09/2026), từ một máy trong cùng mạng:

- Cổng 80, 443, 554, 8000 mở; **ISAPI không có** (mọi `/ISAPI/…` → 404).
- RTSP `/Streaming/Channels/101` hỏi kiểu ONVIF → có đường tiếng `sendonly` **PCMU 8 kHz**
  (hỏi thường thì không có).
- Mở kênh ngược, phát 0,8 giây tiếng bíp PCMU: DESCRIBE / SETUP / PLAY / TEARDOWN đều 200.
- Hàm kiểm của tích hợp (`check_rtsp_talk`) nhận camera; sai mật khẩu báo đúng lỗi đăng nhập.

**Chưa kiểm:** nghe tận tai tiếng phát ra loa qua tích hợp trên HA thật, và camera có tự
tắt mic lúc loa phát không (camera Imou có). Có kết quả sẽ ghi thêm vào đây.
