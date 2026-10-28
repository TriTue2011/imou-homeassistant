# Assist Camera — loa, bộ đàm, vệ tinh Assist cho camera Imou / Dahua / EZVIZ / ONVIF

[![Mở kho này trong HACS của bạn.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=TriTue2011&repository=imou-homeassistant&category=integration)

Biến mic và loa camera thành **loa**, **bộ đàm** (nói qua camera bằng mic điện thoại) và
**vệ tinh Assist** ngay trong Home Assistant — không cần add-on, không qua đám mây.

> Camera **EZVIZ / Hikvision / ONVIF có loa**: xem thêm **[README_EZVIZ.md](README_EZVIZ.md)**.

Mỗi camera sinh ra:

| Thực thể | Làm gì |
|---|---|
| `media_player.<camera>_speaker` | `tts.speak`, `media_player.play_media` ra loa camera; nhạc phát nền, có `media_stop`, âm lượng từng camera (50% = tiếng gốc) |
| `assist_satellite.<camera>` | Nghe mic camera, chạy pipeline Assist, trả lời ra loa; `announce` / `start_conversation` |
| `number.<camera>_microphone_gain` | Tăng mic 0–30 dB (bắt đầu **0 dB**) |
| `switch.<camera>_wake_sound` | Kêu "ting" khi bắt được từ gọi |
| `switch.<camera>_mute_microphone` | Tắt nghe (loa, bộ đàm vẫn chạy) |
| `select.<camera>_assistant` / `_finished_speaking_detection` | Chọn pipeline / độ nhạy "nói xong" |

Và dịch vụ `dahua_talk.get_intercom_source` — trả dòng go2rtc cho bộ đàm.

**Mục lục:** [Cài đặt](#cài-đặt) · [Chỉnh camera Imou](#chỉnh-camera-imou) ·
[Loa](#loa-và-automation) · [Vệ tinh Assist](#vệ-tinh-assist) · [Bộ đàm](#bộ-đàm) ·
[Nói từ xa (4G)](#nói-từ-xa-4g) · [Bảo mật](#bảo-mật) · [Sự cố](#sự-cố-thường-gặp)

---

## Cài đặt

**HACS:** ⋮ → Custom repositories → `https://github.com/TriTue2011/imou-homeassistant`, loại
**Integration** → tải **Assist Camera** → khởi động lại HA. (Chép tay: thư mục
`custom_components/dahua_talk` vào `/config/custom_components/`.)

Rồi: Cài đặt → Thiết bị & dịch vụ → Thêm tích hợp → **Assist Camera**, mỗi camera một lần,
chọn loại:

| Loại | Điền |
|---|---|
| **Imou / Dahua** | Tên, IP, tài khoản (`admin`), mật khẩu (mã an toàn trên tem), URL tiếng mic |
| **EZVIZ** | Tên, IP, **mã xác minh** — xem [README_EZVIZ.md](README_EZVIZ.md) |
| **Hikvision / ONVIF khác** | Tên, IP, cổng RTSP, đường dẫn luồng, tài khoản, mật khẩu, URL tiếng mic |

- **URL tiếng mic** — không bắt buộc. Có go2rtc:
  `http://IP_GO2RTC:1984/api/stream.mp4?src=TEN_LUONG_PHU&video=none&audio=all`, hoặc URL RTSP
  luồng phụ. **Bỏ trống** nếu chỉ cần loa + bộ đàm, hoặc HA chưa có pipeline Assist đủ
  **từ gọi + STT + TTS**.
- Imou nói qua cổng **8086** (AAC 16 kHz), tự lùi về **37777** (8 kHz) nếu camera không mở
  8086. HA phải tới được hai cổng này (cùng LAN là đủ).
- Sửa IP / mật khẩu sau này: ⋮ cạnh camera → **Cấu hình lại** (khoá bộ đàm giữ nguyên).

## Chỉnh camera Imou

Bằng **SmartPSS** (Device CFG → camera):

- **Luồng chính H.264** (trình duyệt xem H.265 rất kém), **tắt Smart Codec / H.264+**.
- **Bật audio AAC ở cả luồng chính và luồng phụ** — mic cho Assist đọc từ luồng phụ.
- **Tắt Noise Filter** — đo thật: bật thì camera cắt tiếng về 0 trong 35–94% thời gian, từ
  gọi và nhận giọng hỏng.
- **IP tĩnh** (hoặc giữ chỗ DHCP). Âm lượng loa chỉ chỉnh được ở camera.
- Sai mật khẩu vài lần là camera khoá đăng nhập một lúc — tích hợp chỉ thử một lần mỗi lần bấm.

## Loa và automation

```yaml
action: tts.speak
target: {entity_id: tts.piper}
data:
  media_player_entity_id: media_player.cam_cua_speaker
  message: "Có người ở cửa"
---
action: assist_satellite.announce          # chờ phát xong mới chạy tiếp
target: {entity_id: assist_satellite.cam_cua}
data: {message: "Cửa trước vừa mở", preannounce: false}
```

Loa, thông báo, trả lời Assist và bộ đàm dùng chung một phiên: cái nào tới trước phát trước.

## Vệ tinh Assist

- **Từ gọi** do pipeline quyết (Cài đặt → Trợ lý giọng nói), chọn pipeline ở
  `select.<camera>_assistant`. Từ gọi tiếng Việt **«Trợ lý»**: [wakeword/](wakeword/README.md) —
  `okay_nabu` (giọng Anh) hay trượt với giọng Việt qua mic camera.
- **Tăng mic bắt đầu ở 0 dB**, chỉ tăng khi ngồi xa không bắt được (+12…+18 dB). Tăng quá tay
  tiếng vỡ, từ gọi trượt nhiều hơn.
- ⚠️ **Đừng cho nghe ở camera hướng ra ngoài** — người ngoài nói từ gọi là ra lệnh được cho
  nhà bạn. Camera ngoài chỉ dùng loa + bộ đàm.

---

## Bộ đàm

Mở thẻ camera trên điện thoại: nghe tiếng camera, bấm 🎙️ để nói — giọng bạn ra loa camera.

```
Điện thoại (thẻ WebRTC Camera) ──WebRTC 8555, Opus──► go2rtc
go2rtc ──kênh ngược RTSP, nguyên gói Opus──► HA cổng 8557 (tích hợp tự mở)
HA ──AAC 16 kHz──► loa camera (Imou 8086 / EZVIZ HCNetSDK 8000)
```

**Cần:** go2rtc ≥ 1.9.10, thẻ [WebRTC Camera](https://github.com/AlexxIT/WebRTC), HA mở bằng
**https** (trình duyệt chỉ cho mic trên https).

### 1. Lấy dòng go2rtc

Công cụ nhà phát triển → Hành động:

```yaml
action: dahua_talk.get_intercom_source
data:
  entity_id: media_player.cam_cua_speaker
  # ha_url: http://192.168.1.10:8123    # chỉ khi go2rtc KHÔNG chạy chung máy/mạng với HA
```

Chép dòng `source`: `rtsp://127.0.0.1:8557/<mã camera>/<khoá>#backchannel=1`.

- `ha_url`: **bỏ trống** nếu go2rtc là add-on HA OS, do tích hợp WebRTC Camera tự chạy, hoặc
  container `network_mode: host` cùng máy. go2rtc ở máy/VM khác, container mạng bridge, hay
  trong Frigate: điền **IP LAN của HA** — máy đó phải gọi được cổng **8557** của HA.
- Giữ `#backchannel=1` (thiếu là go2rtc tắt kênh ngược).
- `exec_source` trong kết quả là dòng `exec:` kiểu cũ (8 kHz) — chỉ dùng khi go2rtc không gọi
  tới được cổng 8557. Đang dùng dòng `exec:` cũ thì thay bằng dòng `rtsp://` (rõ hơn hẳn).

### 2. Thêm vào go2rtc

Dán vào **cuối** danh sách nguồn của luồng camera:

```yaml
streams:
  cam_cua:
    - rtsp://admin:MATKHAU@192.168.1.64:554/cam/realmonitor?channel=1&subtype=0
    - ffmpeg:cam_cua#audio=opus        # tiếng camera cho WebRTC
    - "rtsp://127.0.0.1:8557/<mã camera>/<khoá>#backchannel=1"
```

Mỗi luồng chỉ **một** dòng bộ đàm. Khởi động lại go2rtc.

Kiểm (từ máy chạy go2rtc):
`printf 'DESCRIBE rtsp://IP_HA:8557/<mã>/<khoá> RTSP/1.0\r\nCSeq: 1\r\n\r\n' | nc IP_HA 8557`
→ phải ra `200 OK` kèm `opus/48000/2`. `404` là sai khoá; không nối được là sai IP / tường lửa.

### 3. Thẻ WebRTC Camera

```yaml
type: custom:webrtc-camera
ui: true
streams:
  - url: cam_cua
    name: 🔇
    media: video,audio
  - url: cam_cua
    name: 🎙️
    media: video,audio,microphone
```

Bấm tên ở góc dưới để đổi 🔇 ↔ 🎙️. Chỉ camera có dòng bộ đàm mới cần mục 🎙️. Điện thoại phải
cho app HA / trình duyệt quyền **Micro**.

### Dùng thế nào

- **Luân phiên như bộ đàm:** camera **tắt mic lúc loa phát**, nên loa chỉ mở khi có tiếng người
  và đóng sau **1,5 giây im** — nói xong ngừng, rồi nghe bên kia.
- Tiếng ra loa sau ~0,1–0,4 giây; khi phải chờ mở kênh, tích hợp bỏ bớt khoảng lặng để đuổi kịp.
- **EZVIZ / Hikvision (HCNetSDK):** nghỉ giữa câu 1,5–3,5 giây thì câu sau trễ ~1,2 giây — camera
  cần chừng đó mới mở lại kênh vừa đóng. Nói liền, hoặc nghỉ hẳn hơn 3,5 giây, thì không bị.

---

## Nói từ xa (4G)

**Trong nhà không cần làm gì.** Ở ngoài, không làm gì thì thẻ vẫn xem, nghe được (sau ~30 giây
tụt về MSE) nhưng **không có mic**. Để có mic, chọn một cách:

1. **Mở cổng 8555/TCP** trên router về máy chạy go2rtc, và trong `go2rtc.yaml`:
   ```yaml
   webrtc:
     listen: ":8555/tcp"
     candidates:
       - stun:8555
   ```
   Chỉ chạy khi router có **IP công khai thật** (không CGNAT) và máy go2rtc **không bị router
   đẩy ra internet qua VPN** (nếu có: cho riêng máy đó đi thẳng, vd MikroTik
   `/ip firewall mangle add chain=prerouting src-address=IP_GO2RTC dst-address=!MANG_NHA/24 action=accept place-before=0`).
   Mạng nhà `172.16–31.x.x` mà máy có card Tailscale/VPN: thêm `filters: ips: [IP_LAN_GO2RTC]`
   vào `webrtc:` (go2rtc tưởng dải đó là Docker và bỏ qua IP LAN của chính nó).
   Kiểm cổng **từ ngoài**: check-host.net → `IP_WAN:8555`.
2. **Không mở cổng — ngrok** (có sẵn trong go2rtc, gói miễn phí):
   `ngrok: {command: ngrok tcp 8555 --authtoken <token>}` — go2rtc tự dùng địa chỉ ngrok.
3. **Không mở cổng — TURN**: `webrtc: ice_servers:` trỏ tới máy chủ TURN (coturn trên VPS,
   Cloudflare Realtime TURN…).
4. **VPN về nhà** (WireGuard, Tailscale): bật VPN trên điện thoại là như ở trong nhà.

Cloudflare Tunnel / Nabu Casa chỉ chở trang web HA, **không chở WebRTC của go2rtc**.
⚠️ Không bao giờ mở **1984** (API go2rtc — lộ mật khẩu camera), **8554**, **8557** ra internet.

---

## Bảo mật

- **Khoá bộ đàm** (trong dòng go2rtc): ai có chỉ phát được tiếng ra loa **camera ấy**. Đừng dán ra
  ngoài; lộ thì xoá camera khỏi tích hợp rồi thêm lại (khoá mới).
- **API go2rtc (1984)** mặc định không mật khẩu và trả URL camera kèm mật khẩu — nên đặt
  `api: username / password`.
- Che `admin:…@` và khoá khi dán cấu hình go2rtc đi hỏi.

## Sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Nói không ra loa (ở nhà) | HA phải mở bằng **https**; cho phép Micro; đang ở mục 🎙️ chưa |
| Nói không ra loa (4G), có hình có tiếng | WebRTC chưa nối — [Nói từ xa](#nói-từ-xa-4g) |
| Console: `reading 'getUserMedia'` | HA mở bằng `http://` — trình duyệt cấm mic |
| Dòng `rtsp://…:8557` không chạy | Kiểm bằng `nc` ở [bước 2](#2-thêm-vào-go2rtc); go2rtc ở máy khác thì `ha_url` = IP LAN của HA |
| `get_intercom_source` trả dòng `exec:` | Cổng 8557 bị chương trình khác chiếm (log HA `intercom RTSP: …`) |
| go2rtc báo `exec: Stdin already set` | Mở lại thẻ khi phiên cũ chưa đóng — đợi ~10 giây |
| Nói nhỏ thì loa không phát | Dưới -45 dBFS — nói gần điện thoại hơn |
| Đang nói thì không nghe bên kia | Bình thường — camera tắt mic lúc loa phát |
| Từ gọi không bắt / STT mất chữ | Tắt **Noise Filter** của camera; tăng mic dần từ 0 dB |
| Thêm camera báo sai mật khẩu dù đúng | Camera đang khoá — chờ vài phút, thử **một** lần |
| Log `Assist pipeline error … retrying` | Pipeline thiếu từ gọi / STT / TTS, hoặc xoá URL tiếng mic |
| WebRTC không có hình | Luồng H.265 → đổi sang H.264 |
| TTS vẫn đọc câu cũ sai | `action: tts.clear_cache` |

## Phát triển

```bash
pip install pytest-homeassistant-custom-component
pytest
```

Bản mới: nâng `version` trong `custom_components/dahua_talk/manifest.json`, thêm mục vào
`CHANGELOG.md` — workflow tự tạo release.
