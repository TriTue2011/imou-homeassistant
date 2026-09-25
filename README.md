# Imou / Dahua cho Home Assistant — loa, bộ đàm, vệ tinh Assist

Biến mic và loa của camera **Imou / Dahua** thành **loa**, **bộ đàm** (nói qua camera
bằng mic điện thoại, như app Imou) và **vệ tinh Assist** ngay trong Home Assistant —
không cần dịch vụ nào bên ngoài HA.

Mỗi camera thêm vào sinh ra:

| Thực thể | Làm gì |
|---|---|
| `media_player.<camera>_loa` | `tts.speak`, `media_player.play_media` (tệp, URL, media source) ra loa camera. |
| `assist_satellite.<camera>` | Nghe mic camera, chạy pipeline Assist (từ gọi → nhận giọng → hiểu lệnh → đọc trả lời), trả lời ra loa camera. Câu trả lời là câu hỏi lại thì nghe tiếp luôn, không cần gọi lại từ gọi. `assist_satellite.announce` / `start_conversation` phát ra loa. |
| `number.<camera>_tang_mic` | Khuếch đại mic 0–30 dB trước khi đưa vào Assist (mic camera nhỏ). |
| `switch.<camera>_tat_mic` | Tắt nghe (loa, thông báo, bộ đàm vẫn chạy). |
| `select.<camera>_tro_ly` | Chọn pipeline Assist (từ gọi, STT, TTS, tác tử). |
| `select.<camera>_phat_hien_noi_xong` | Độ nhạy nhận biết đã nói xong. |

Và dịch vụ `dahua_talk.get_intercom_source` — trả dòng cấu hình go2rtc cho **bộ đàm**.

**Mục lục**

1. [Vì sao cần tích hợp này](#vì-sao-cần-tích-hợp-này)
2. [Cài đặt camera bằng SmartPSS](#cài-đặt-camera-bằng-smartpss)
3. [Cài đặt tích hợp](#cài-đặt-tích-hợp)
4. [Loa và automation](#loa-và-automation)
5. [Vệ tinh Assist, từ gọi, tăng mic](#vệ-tinh-assist-từ-gọi-tăng-mic)
6. [Bộ đàm](#bộ-đàm)
7. [Xem và nói từ xa (4G)](#xem-và-nói-từ-xa-4g)
8. [Dùng cùng Frigate](#dùng-cùng-frigate)
9. [Bảo mật](#bảo-mật)
10. [Sự cố thường gặp](#sự-cố-thường-gặp)
11. [Giới hạn](#giới-hạn)
12. [Phát triển và test](#phát-triển-và-test)

---

## Vì sao cần tích hợp này

Nhiều camera Imou (lõi Dahua) **không có kênh ngược RTSP/ONVIF**: go2rtc và thẻ
camera của HA xem được, nghe được, nhưng **không nói ra loa được**. Tích hợp này nói
qua **cổng TCP 37777** — đúng đường app Imou dùng (giao thức NetSDK
`CLIENT_StartTalkEx`), viết bằng Python thuần theo mô tả khung byte của
[go2rtc PR #2431](https://github.com/AlexxIT/go2rtc/pull/2431).

Đã chạy thật trên 4 camera Imou (trong nhà và ngoài trời): mở kênh nói 0,04–0,9
giây; camera tự tắt mic của nó trong lúc phát nên không tự nghe lại tiếng mình.

---

## Cài đặt camera bằng SmartPSS

Dùng **SmartPSS** (hoặc trang web của camera) để chỉnh những mục app Imou không có.
Tên mục có thể khác đôi chút giữa các đời firmware; đường dẫn dưới đây theo SmartPSS:
**Device CFG → chọn camera**.

### Mã hoá hình — Encode → Video

| Mục | Nên đặt | Vì sao |
|---|---|---|
| Luồng chính — Compression | **H.264** | Trình duyệt xem WebRTC H.265 rất kém (nhiều máy không có hình). |
| Smart Codec / H.264+ | **Tắt** | Mã hoá "thông minh" giãn khung khoá rất xa: mở luồng chậm, hình vỡ khi người đi nhanh, ảnh nhận mặt nhoè. |
| Luồng chính — Resolution | Cao nhất camera cho phép | Mặt càng nhiều điểm ảnh càng nhận được. Lưu ý **mỗi đời camera một mức tối đa** — nhiều camera 2 MP chỉ tới 1080P, danh sách 2K/4MP chỉ có ở đời cao hơn. |
| Luồng chính — Bit Rate | 4096 Kbps trở lên cho 1080P (6144 nếu có) | Bitrate thấp → mặt nhỏ vỡ ô vuông khi phóng to. |
| Luồng chính — Frame Rate | 15–20 | Đủ mượt, đỡ tốn băng thông. |
| Luồng phụ (Sub Stream) | **H.264**, 640×480 hoặc tương đương, **bật** | Để dò chuyển động / nghe mic cho nhẹ. |
| Audio (cả luồng chính **và** luồng phụ) | **Bật**, mã hoá **AAC** | AAC nghe tốt hơn G.711 (alaw/mulaw). Mic cho Assist nên đọc từ luồng phụ — phải bật audio ở luồng phụ. |

**Snapshot** (Encode → Snapshot) chỉ dùng cho ảnh camera tự chụp lưu thẻ nhớ/đám mây
khi có sự kiện — không ảnh hưởng HA, go2rtc hay nhận mặt. Để *Trigger*, đổi hay
không đều được.

### Âm thanh — Audio

| Mục | Nên đặt | Vì sao |
|---|---|---|
| **Noise Filter / Lọc ồn** | **TẮT** | Xem ngay dưới. |
| Mic volume (Audio Input Volume) | Cao (mặc định thường đã 100) | Mic camera vốn nhỏ. |
| Speaker volume (Audio Output Volume) | Theo ý (70–100) | Âm lượng loa **chỉ** chỉnh được ở camera, không chỉnh qua HA. |

> ### ⚠️ Lọc ồn làm hỏng từ gọi và nhận giọng
> Đo thật trên camera Imou: bật **Noise Filter** thì camera **cắt tiếng về 0** trong
> **35–94% thời gian** (mọi khoảng nó coi là "ồn" — kể cả câu nói ở xa). Từ gọi
> (openWakeWord) không bao giờ nghe đủ cả cụm, nhận giọng (STT) mất chữ. Tắt lọc ồn
> xong là hết cắt. Muốn giảm ồn thì để HA làm (Assist có lọc ồn riêng) và dùng
> `number.<camera>_tang_mic` để bù độ nhỏ — đừng bật lọc của camera.

### Mạng — Network

| Mục | Nên đặt |
|---|---|
| TCP Port | **37777** (mặc định). Đổi thì điền cổng mới vào ô *Cổng nói* của tích hợp. |
| RTSP Port | 554 (mặc định) — go2rtc/Frigate đọc hình qua cổng này. |
| IP | **Tĩnh** hoặc giữ chỗ DHCP trên router — đổi IP là HA, go2rtc, Frigate cùng mất camera. |
| Thời gian (NTP) | Bật đồng bộ — giờ trên hình và sự kiện khớp với HA. |

> **Sai mật khẩu vài lần là camera khoá đăng nhập** một lúc (cả SmartPSS, go2rtc,
> tích hợp này). Tích hợp chỉ đăng nhập thử **một lần** mỗi lần bấm.

---

## Cài đặt tích hợp

**HACS (khuyên dùng):** HACS → ⋮ → Custom repositories → thêm
`https://github.com/TriTue2011/imou-homeassistant`, loại **Integration** → tìm
**Dahua/Imou Talk** → Tải xuống → khởi động lại HA.

**Chép tay:** chép thư mục `custom_components/dahua_talk` vào
`/config/custom_components/dahua_talk` rồi khởi động lại HA.

Sau đó: Cài đặt → Thiết bị & dịch vụ → Thêm tích hợp → **Dahua/Imou Talk**, mỗi
camera một lần:

| Ô | Điền |
|---|---|
| Tên | Tên camera (vd *Cam cửa*) |
| IP camera, Cổng nói | IP camera trong mạng nhà, `37777` |
| Tài khoản, Mật khẩu | Tài khoản camera (thường `admin` + mật khẩu thiết bị / mã an toàn in trên tem) |
| URL tiếng mic | **Không bắt buộc.** Có go2rtc: `http://IP_GO2RTC:1984/api/stream.mp4?src=TEN_LUONG_PHU&video=none&audio=all`. Hoặc URL RTSP luồng phụ của camera. **Bỏ trống thì chỉ dùng loa và bộ đàm** — vệ tinh Assist không nghe gì. |

HA phải tới được camera ở cổng 37777 (cùng mạng LAN là đủ).

---

## Loa và automation

```yaml
# Đọc ra loa camera
action: tts.speak
target: {entity_id: tts.piper}
data:
  media_player_entity_id: media_player.cam_cua_loa
  message: "Có người ở cửa"

# Thông báo (chờ phát xong mới chạy tiếp)
action: assist_satellite.announce
target: {entity_id: assist_satellite.cam_cua}
data: {message: "Cửa trước vừa mở", preannounce: false}

# Hỏi rồi nghe câu trả lời
action: assist_satellite.start_conversation
target: {entity_id: assist_satellite.cam_cua}
data: {start_message: "Anh có muốn bật đèn hiên không?"}
```

Loa, thông báo, trả lời Assist và bộ đàm dùng chung một phiên nói: cái nào tới trước
phát trước, cái sau chờ.

---

## Vệ tinh Assist, từ gọi, tăng mic

**Từ gọi** do **pipeline** quyết: Cài đặt → Trợ lý giọng nói → chọn pipeline → mục
*Từ gọi* chọn engine (vd openWakeWord) và từ (vd `okay_nabu`). Rồi chọn pipeline đó
ở `select.<camera>_tro_ly`. Từ gọi riêng: thêm mô hình openWakeWord tuỳ chỉnh vào
add-on openWakeWord (thư mục `share/openwakeword`) rồi chọn trong pipeline.

Kinh nghiệm đo thật với camera trong nhà:

- **Tắt Noise Filter trên camera** — [xem trên](#-lọc-ồn-làm-hỏng-từ-gọi-và-nhận-giọng).
- **Tăng mic:** mic camera nhỏ (phòng yên chỉ -46…-51 dBFS). Ngồi cách 3 m phải nói to
  mới bắt được từ gọi; `number.<camera>_tang_mic` **+12 đến +18 dB** là mức hợp lý.
  Tích hợp luôn lọc bỏ độ lệch một chiều (DC) của mic camera **trước** khi tăng, và
  chặn đỉnh để nói gần không vỡ tiếng. Đổi mức là áp ngay.
- **Từ gọi tiếng Anh với giọng Việt ở xa:** các mô hình có sẵn (`okay_nabu`,
  `hey_jarvis`) được huấn luyện bằng giọng Anh; với giọng Việt qua mic camera cách
  3 m chúng bắt rất kém. Gần mic thì được. Từ gọi tiếng Việt cần mô hình tự huấn
  luyện.
- Camera tắt mic của nó lúc loa đang phát, nên vệ tinh không tự nghe lại câu trả lời.

> ⚠️ **Đừng cho nghe ở camera hướng ra ngoài** (cổng, cửa, ban công): ai đứng ngoài
> nói từ gọi là ra lệnh được cho nhà bạn — kể cả mở khoá, tắt báo động nếu trợ lý
> được phép. Camera ngoài chỉ nên dùng loa và bộ đàm (để trống *URL tiếng mic*, hoặc
> bật `switch.<camera>_tat_mic`).

---

## Bộ đàm

Mở thẻ camera trên điện thoại: **nghe** được tiếng camera, **nói** thì giọng bạn ra
loa camera nguyên gốc (không qua TTS) — như app Imou, nhưng ngay trong HA.

### Cách hoạt động

```
Điện thoại (thẻ WebRTC Camera, mic)
        │  WebRTC (cổng 8555)
        ▼
     go2rtc ──── nghe: tiếng camera (opus) ───────────────► điện thoại
        │  nói: kênh ngược → lệnh exec (ffmpeg)
        ▼  POST A-law 8 kHz, khoá riêng của camera
Home Assistant — /api/dahua_talk/intercom/<camera>
        │  cổng 37777 (giao thức nói Dahua)
        ▼
   Loa camera
```

- **Chỉ mở loa khi có tiếng người** (to hơn -45 dBFS), **đóng sau 1,5 giây im**, giữ
  0,3 giây ngay trước tiếng để không mất âm đầu câu. Lý do: camera **tự tắt mic của
  nó suốt lúc loa đang mở**, mà trình duyệt gửi tiếng liên tục — mở loa suốt thì
  không bao giờ nghe được người bên camera trả lời. Dùng như bộ đàm: nói xong ngừng,
  rồi nghe.
- **Trực tiếp**, không thu hết rồi mới phát: mỗi khúc tiếng ra loa sau ~0,1–0,3 giây;
  câu đầu mỗi lượt chờ thêm lúc mở kênh nói với camera (0,05–0,9 giây).

**Cần:** go2rtc **≥ 1.9.10** (kênh ngược qua `exec`), thẻ
[WebRTC Camera](https://github.com/AlexxIT/WebRTC), HA mở bằng **https** (trình
duyệt chỉ cho dùng mic trên https).

### Bước 1 — lấy dòng go2rtc

Công cụ nhà phát triển → **Hành động** → `dahua_talk.get_intercom_source`:

```yaml
action: dahua_talk.get_intercom_source
data:
  entity_id: media_player.cam_cua_loa
  # ha_url: http://192.168.1.10:8123   # xem bảng dưới — bỏ trống nếu go2rtc chung mạng với HA
```

Bấm **Thực hiện hành động**, chép dòng `source` trả về. Nó có dạng:

```
exec:ffmpeg -hide_banner -loglevel error -probesize 32 -analyzeduration 0 -fflags nobuffer -f alaw -ar 8000 -ac 1 -i - -c:a copy -f alaw -flush_packets 1 -method POST http://127.0.0.1:8123/api/dahua_talk/intercom/<mã camera>?k=<khoá>#backchannel=1#audio=alaw/8000
```

Mỗi camera một dòng riêng (khoá khác nhau). Dòng không đổi sau khi khởi động lại HA.

> Đừng tự viết lại dòng này. Ba cờ `-probesize 32 -analyzeduration 0 -fflags
> nobuffer` là bắt buộc: thiếu chúng, ffmpeg **gom tiếng để dò định dạng** rồi mới
> nhả — đo thật: nói 2,5 giây mà 0 byte tới loa, tức "thu hết rồi mới phát".

### Chọn `ha_url` theo cách bạn cài

`ha_url` là **địa chỉ HA mà máy chạy go2rtc gọi tới được**. Tiếng đi từ go2rtc sang
HA, nên chỉ cần hai bên thấy nhau trong mạng nhà.

| Cách cài | `ha_url` | Vì sao |
|---|---|---|
| **HA OS + add-on go2rtc** | **bỏ trống** (dùng `127.0.0.1`) | Add-on go2rtc chạy mạng *host*, cùng máy với HA — `127.0.0.1` chính là HA. Tiếng không ra khỏi máy. |
| **HA Container + go2rtc container, cùng máy, cả hai `network_mode: host`** | **bỏ trống** | Như trên: cùng mạng của máy chủ. |
| **Cùng máy, nhưng go2rtc ở mạng *bridge*** (mặc định của Docker) | `http://IP_LAN_CỦA_MÁY:8123` | `127.0.0.1` trong container bridge là **chính container go2rtc**, không phải HA. Dùng IP LAN của máy, hoặc `http://host.docker.internal:8123` (trên Linux phải thêm `extra_hosts: ["host.docker.internal:host-gateway"]` cho container go2rtc). |
| **Hai máy / hai VM — kiểu Proxmox** (HA một VM, go2rtc ở VM/LXC khác) | `http://IP_LAN_CỦA_HA:8123` | Hai máy khác nhau nên `127.0.0.1` sai. Đặt IP tĩnh (hoặc giữ chỗ DHCP) cho HA, kẻo đổi IP là dòng go2rtc hỏng. |
| **go2rtc nằm trong Frigate** | `http://IP_LAN_CỦA_HA:8123` | Xem [Dùng cùng Frigate](#dùng-cùng-frigate). |
| HA bật SSL ngay trên cổng 8123 | `https://…:8123` | Bỏ trống thì tích hợp tự dùng `https` khi HA có chứng chỉ. ffmpeg không kiểm chứng chỉ nên chứng chỉ cho tên miền vẫn dùng được với IP. |

**Không** dùng địa chỉ đi qua internet (tên miền Cloudflare, Nabu Casa…) cho
`ha_url`: tiếng đi vòng ra ngoài rồi mới về, chậm và phụ thuộc mạng.

Kiểm từ máy chạy go2rtc:
`curl -s -o /dev/null -w '%{http_code}\n' -X POST "<URL trong dòng exec>"` phải ra
`200` (không có tiếng thì loa không mở). `401` là sai khoá / sai camera; không kết
nối được là sai `ha_url`.

### Bước 2 — cấu hình go2rtc

Dán dòng vừa chép vào **cuối danh sách nguồn** của luồng camera trong
`go2rtc.yaml`, trong **dấu nháy kép**:

```yaml
streams:
  cam_cua:
    - rtsp://admin:MATKHAU@192.168.1.64:554/cam/realmonitor?channel=1&subtype=0
    - ffmpeg:cam_cua#audio=opus          # tiếng camera cho WebRTC (AAC không đi qua WebRTC được)
    - "exec:ffmpeg … #backchannel=1#audio=alaw/8000"   # dòng từ bước 1
  cam_cua_sub:
    - rtsp://admin:MATKHAU@192.168.1.64:554/cam/realmonitor?channel=1&subtype=1

webrtc:
  listen: ":8555/tcp"
  candidates:
    - stun:8555          # go2rtc tự dò IP ngoài — xem phần xem từ xa
```

Khởi động lại go2rtc (add-on: Cài đặt → Add-on → go2rtc → Khởi động lại).

- Dòng `exec` phải thêm vào **tệp cấu hình**. go2rtc **chặn** nguồn `exec` (có dấu
  cách) thêm qua API / giao diện web của nó, vì lý do an toàn.
- Thêm vào **đúng luồng** mà thẻ WebRTC xem (thường là luồng chính). Luồng phụ cho
  AI / Frigate không cần.

### Bước 3 — thẻ WebRTC Camera

```yaml
type: custom:webrtc-camera
url: cam_cua
media: video,audio,microphone
```

- Thẻ **không có nút mic**: có `microphone` thì thẻ xin quyền mic lúc mở và **để mic
  mở suốt** lúc thẻ còn hiện. Nói là loa camera phát, im là loa đóng.
- Trình duyệt / app HA Companion phải được **cho phép Micro** (Android: Cài đặt → Ứng
  dụng → Home Assistant → Quyền → Micro). Xin mic thất bại thì thẻ **im lặng bỏ qua**
  (chỉ ghi ở console) — không báo gì trên màn hình.
- Mic chỉ chạy khi HA mở bằng **https**. `http://IP:8123` trong mạng nhà cũng bị
  trình duyệt cấm mic.
- Mở lại thẻ ngay khi phiên cũ chưa kịp đóng, go2rtc có thể báo `exec: Stdin already
  set` và lần đó không có mic — đóng thẻ ~10 giây rồi mở lại. Hai thẻ cùng mở mic
  vào **cùng một luồng** cũng gặp lỗi này.

---

## Xem và nói từ xa (4G)

Trong mạng nhà, điện thoại nối thẳng IP LAN của go2rtc — không cần làm gì thêm. Ở
ngoài (4G), WebRTC cần **một cổng vào nhà** và go2rtc phải **báo đúng IP ngoài** cho
điện thoại.

`candidates: - stun:8555` nghĩa là: go2rtc tự hỏi máy chủ STUN "IP ngoài của tôi là
gì", rồi bảo điện thoại "gọi IP đó, cổng 8555". Chạy được khi **đủ ba điều**:

1. Router có **IP công khai thật** (không phải CGNAT).
2. Router **chuyển cổng 8555/TCP** về máy chạy go2rtc.
3. Máy chạy go2rtc **ra internet bằng chính IP đó** (không bị router đẩy qua VPN).

**Dấu hiệu chưa được:** mở thẻ bằng 4G có hình, có tiếng, **không có mic**. Thẻ chạy
song song WebRTC và MSE; WebRTC không nối được thì sau **~30 giây** thẻ bỏ WebRTC,
giữ MSE — MSE xem được nhưng **không gửi được mic**. Nối được thì ngược lại: chỉ
1–2 giây sau khi mở, thẻ bỏ MSE và giữ WebRTC.

Xem được điều này trên go2rtc: `http://IP_GO2RTC:1984/api/streams` → luồng camera →
`consumers`: kết nối `webrtc` của điện thoại có ở lại quá 30 giây không.

### Kiểm CGNAT

So IP ở cổng internet (WAN / PPPoE) của router với IP hiện ra khi mở
`https://ifconfig.me` bằng mạng nhà. IP WAN dạng `100.64–127.x.x` hay `10.x.x.x` là
**CGNAT** — mở cổng không có tác dụng; gọi nhà mạng xin IP riêng, hoặc dùng
[VPN về nhà](#không-muốn-mở-cổng).

(Nếu IP WAN là IP thật mà `ifconfig.me` ra IP **khác** — thường là IP nước ngoài —
thì mạng nhà đang đi qua VPN: xem [Router đẩy máy HA qua VPN](#router-đẩy-máy-ha-qua-vpn).)

### Mở cổng trên router

Chỉ mở **8555/TCP**. Cổng này chỉ chở luồng hình/tiếng: muốn nhận luồng phải có mã
phiên, mà mã phiên chỉ được cấp qua HA **sau khi đăng nhập** — người ngoài gọi vào
8555 không xem, không nói được gì.

> ⚠️ **Tuyệt đối không mở 1984 (API go2rtc) và 8554 (RTSP)** ra internet. API go2rtc
> mặc định không có mật khẩu và trả nguyên URL camera **kèm mật khẩu**.

**MikroTik (RouterOS 7)** — Winbox → New Terminal. Đổi `pppoe-out1` thành tên cổng
internet của bạn (xem `/ip address print`: cổng mang IP công khai), `192.168.1.10`
thành IP máy chạy go2rtc:

```
/ip firewall nat add chain=dstnat in-interface=pppoe-out1 protocol=tcp dst-port=8555 action=dst-nat to-addresses=192.168.1.10 to-ports=8555 comment="go2rtc WebRTC"
/ip firewall filter add chain=forward in-interface=pppoe-out1 protocol=tcp dst-port=8555 dst-address=192.168.1.10 connection-state=new connection-limit=20,32 action=drop place-before=0 comment="go2rtc 8555 chan don ket noi"
```

- Luật thứ hai chặn một IP mở quá 20 kết nối cùng lúc (quét cổng, dồn kết nối);
  điện thoại xem camera chỉ dùng vài kết nối. Router chưa có luật filter nào thì bỏ
  `place-before=0`.
- Cấu hình mặc định của MikroTik có sẵn luật "drop mọi thứ từ WAN không được
  dst-nat", không cần thêm luật cho phép.
- **Kiểm:** `/ip firewall nat print stats where comment~"WebRTC"` — mở thẻ bằng 4G
  thì cột `PACKETS` phải tăng. Đứng ở 0 là gói chưa tới router (CGNAT, nhà mạng chặn).
  (`print stats where dst-port=8555` không in gì — hãy lọc theo `comment`.)
- **Lỗi hay gặp khi gõ tay** (nên copy nguyên dòng rồi dán, trong Winbox bấm chuột
  phải → Paste):
  - `interface-list=WAN` → báo *expected end of command*; đúng là `in-interface-list=WAN`.
  - `in-interface-list=pppoe-out1` → báo *input does not match any value of
    interface-list*; tên **cổng** thì dùng `in-interface=pppoe-out1`, tên **danh
    sách** mới dùng `in-interface-list=`.
  - Luật filter gõ `chain=dstnat` → MikroTik **không báo lỗi** (coi là chuỗi tự đặt
    tên) nhưng luật không bao giờ chạy; phải là `chain=forward`. Xoá luật sai:
    `/ip firewall filter remove [find chain=dstnat]`.
  - Chạy lệnh thêm hai lần → hai luật trùng; xem `/ip firewall nat print detail
    where comment~"WebRTC"` rồi xoá một luật bằng số thứ tự.

**Router nhà mạng (Viettel, VNPT, FPT…)** — vào trang quản trị (thường
`192.168.1.1`), tìm **NAT / Port Forwarding / Virtual Server / Chuyển tiếp cổng**:

| Ô | Điền |
|---|---|
| Tên | `go2rtc WebRTC` |
| Giao thức | **TCP** |
| Cổng ngoài (External / WAN port) | `8555` |
| IP trong (Internal / LAN IP) | IP máy chạy go2rtc |
| Cổng trong (Internal / LAN port) | `8555` |

Modem nhà mạng để chế độ **bridge** và router riêng quay PPPoE thì mở cổng trên
**router quay PPPoE**, không phải trên modem.

Đặt **IP tĩnh / giữ chỗ DHCP** cho máy chạy go2rtc: đổi IP là luật chuyển cổng trỏ
sai chỗ. Muốn mượt hơn khi 4G yếu có thể mở thêm dải UDP của go2rtc (`filters:
udp_ports: [50000, 50500]` trong `webrtc:`) — không bắt buộc, TCP 8555 là đủ.

### Router đẩy máy HA qua VPN

Nhiều nhà cho cả mạng ra internet qua VPN (máy chủ nước ngoài) bằng **policy
routing** trên router. Khi đó máy chạy go2rtc ra internet bằng **IP của VPN**, và
dù đã mở cổng:

1. `stun:` dò ra **IP của VPN** — điện thoại gọi sang đó, không bao giờ tới nhà.
2. Kể cả điện thoại gọi đúng IP nhà, **gói trả lời** từ go2rtc bị đẩy ra VPN thay vì
   quay lại cổng internet nó đã vào.

**Kiểm:**

1. Trên máy chạy go2rtc (HA OS: add-on *Terminal & SSH*): `curl -s ifconfig.me`.
   Ra **khác** IP WAN của router là đang đi VPN.
2. go2rtc đang báo IP nào cho điện thoại — từ bất kỳ máy nào trong nhà có Python:

   ```bash
   pip install aiortc
   python3 - <<'EOF'
   import asyncio, json, urllib.request
   from aiortc import RTCPeerConnection
   async def main():
       pc = RTCPeerConnection(); pc.addTransceiver("video", direction="recvonly")
       await pc.setLocalDescription(await pc.createOffer())
       req = urllib.request.Request("http://IP_GO2RTC:1984/api/webrtc?src=cam_cua",
           data=json.dumps({"type": "offer", "sdp": pc.localDescription.sdp}).encode(),
           headers={"Content-Type": "application/json"}, method="POST")
       for l in json.load(urllib.request.urlopen(req))["sdp"].splitlines():
           if l.startswith("a=candidate") and " 8555 " in l: print(l)
       await pc.close()
   asyncio.run(main())
   EOF
   ```
   Dòng in ra phải chứa **IP WAN của router**. go2rtc nhận IP mới ngay khi đường đi
   đổi — không cần khởi động lại.

**Cách sửa gọn nhất — cho riêng máy chạy go2rtc đi thẳng internet**, các máy khác
vẫn đi VPN. go2rtc tự dò đúng IP, gói trả lời tự đi đúng đường — **không cần DDNS
hay tên miền**, giữ nguyên `stun:8555`.

MikroTik — xem router đẩy qua VPN bằng gì: `/ip firewall mangle print` (luật
`action=mark-routing`), `/routing rule print`, `/ip route print where
dst-address=0.0.0.0/0`.

- Đẩy bằng **mangle `mark-routing`** theo dải `src-address` (hay gặp nhất): thêm luật
  **đứng trước** để máy go2rtc thoát ra trước khi bị gắn nhãn:
  ```
  /ip firewall mangle add chain=prerouting src-address=192.168.1.10 dst-address=!192.168.1.0/24 action=accept place-before=0 comment="go2rtc di mang nha"
  ```
  Trong mangle, `accept` nghĩa là "thôi xét các luật mangle phía sau" — gói không bị
  gắn nhãn VPN, đi theo đường mặc định của bảng `main` (cổng internet). Có hiệu lực
  ngay. Gỡ: `/ip firewall mangle remove [find comment~"go2rtc di mang nha"]`.
- Đẩy bằng **`/routing rule`**: thêm rule `src-address=192.168.1.10/32
  action=lookup-only-in-table table=main` **đứng trước** rule đẩy sang VPN.

Router khác (OpenWrt pbr, pfSense/OPNsense, router có VPN client): thêm máy chạy
go2rtc vào danh sách **ngoại lệ / bypass VPN**.

Luật này chỉ đổi đường **ra internet** của đúng một máy; liên lạc trong LAN (camera,
Frigate, các máy khác) không đổi, không mở thêm cổng nào. Hệ quả: mọi thứ máy đó gọi
ra internet (với HA OS là cả HA: cập nhật, dịch vụ đám mây, Cloudflare Tunnel…) đi
mạng nhà thay vì VPN. Nếu bạn cố ý cho HA đi VPN vì một dịch vụ bị chặn, dùng cách
dưới.

**Nếu phải giữ máy go2rtc đi VPN:**

1. Thay `stun:8555` bằng địa chỉ nhà: `- ten.ddns.cua.ban:8555` (go2rtc tự phân giải
   tên miền; MikroTik có DDNS miễn phí trong `/ip cloud`). Tên miền qua Cloudflare
   thì bản ghi phải **DNS only (đám mây xám)**.
2. Cho gói trả lời của kết nối **đi vào từ cổng internet** quay lại đúng cổng đó —
   MikroTik:
   ```
   /ip firewall mangle add chain=prerouting in-interface=pppoe-out1 connection-state=new action=mark-connection new-connection-mark=vao_tu_wan passthrough=yes place-before=0
   /ip firewall mangle add chain=prerouting connection-mark=vao_tu_wan in-interface=!pppoe-out1 action=accept place-before=1
   ```
   (luật thứ hai đứng trước luật gắn nhãn VPN, để gói trả lời không bị gắn nhãn).

### Không muốn mở cổng

Dùng VPN **về nhà** (WireGuard trên router, add-on Tailscale…): bật VPN trên điện
thoại là như đang ở trong mạng nhà, WebRTC nối thẳng IP LAN, không mở cổng nào. Đổi
lại phải bật VPN mỗi lần dùng.

**Cloudflare Tunnel / proxy Cloudflare (đám mây cam) / Nabu Casa chỉ chở trang web
của HA**, không chở WebRTC — xem từ xa qua chúng vẫn có hình (MSE) nhưng **không có
mic**.

---

## Dùng cùng Frigate

Frigate có go2rtc riêng bên trong. Chọn **một** go2rtc làm nguồn camera duy nhất —
khai camera ở hai go2rtc là camera phải mở hai kết nối, mà camera Imou/Dahua chịu
được rất ít kết nối cùng lúc.

**Cách A (khuyên dùng) — go2rtc của HA là nguồn, Frigate đọc lại từ nó**

```yaml
# frigate config.yml
cameras:
  cam_cua:
    ffmpeg:
      inputs:
        - path: rtsp://USER:PASS@IP_GO2RTC:8554/cam_cua_sub   # dò
          roles: [detect]
        - path: rtsp://USER:PASS@IP_GO2RTC:8554/cam_cua       # ghi
          roles: [record]
```

(`USER:PASS` là `rtsp: username/password` đặt trong `go2rtc.yaml`.) Dòng `exec` bộ
đàm nằm trong `go2rtc.yaml` của HA như bước 2; `ha_url` theo bảng ở trên. Thẻ WebRTC
xem go2rtc của HA. Không khai camera trong mục `go2rtc:` của Frigate nữa.

**Cách B — go2rtc của Frigate là nguồn**

- Thêm dòng `exec` vào mục `go2rtc: streams:` trong cấu hình Frigate, với `ha_url` =
  **IP LAN của HA** (Frigate chạy trong container / máy khác, nên `127.0.0.1` không
  phải HA).
- Phiên bản go2rtc đi kèm Frigate phải **≥ 1.9.10**: mở `http://IP_FRIGATE:1984/api`
  (hoặc cổng go2rtc mà Frigate mở ra), xem trường `version`.
- Tích hợp WebRTC Camera phải trỏ tới go2rtc của Frigate (`http://IP_FRIGATE:1984`),
  và cổng **8555 mở về máy Frigate**; điều kiện "không đi VPN" áp cho **máy Frigate**.

**Với cả hai cách:** đừng đặt `api: listen: "127.0.0.1:1984"` hay `rtsp: listen:
"127.0.0.1:8554"` theo các hướng dẫn "bảo mật" chung chung — Frigate (và mọi máy khác
đọc luồng) mất hình ngay. Bảo mật bằng mật khẩu, xem dưới.

---

## Bảo mật

- **Khoá bộ đàm:** mỗi camera một khoá ngẫu nhiên (trong dòng `exec`). Ai có dòng đó
  **chỉ phát được tiếng ra loa của camera ấy** — không xem, không điều khiển gì khác.
  Đừng dán dòng này ra ngoài `go2rtc.yaml`. Lộ khoá thì xoá camera khỏi tích hợp rồi
  thêm lại (sinh khoá mới), lấy lại dòng và thay trong `go2rtc.yaml`.
- **API go2rtc (1984)** mặc định không có mật khẩu và trả URL camera **kèm mật khẩu**
  cho bất kỳ máy nào trong mạng. Nên đặt:
  ```yaml
  api:
    listen: ":1984"
    username: ten_rieng
    password: mat_khau_rieng
  ```
  rồi sửa URL go2rtc trong tích hợp WebRTC Camera (và mọi thứ khác đang gọi API,
  kể cả *URL tiếng mic* của tích hợp này: `http://ten_rieng:mat_khau_rieng@IP:1984/…`)
  cho khớp.
- Chỉ mở **8555** ra internet — [Mở cổng trên router](#mở-cổng-trên-router).
- Camera ngoài trời: không bật nghe cho Assist — [xem trên](#vệ-tinh-assist-từ-gọi-tăng-mic).

---

## Sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Thẻ không có nút mic | Thẻ WebRTC Camera không có nút mic — mic mở suốt khi có `microphone` | Bình thường. Nói là loa phát. |
| Có hình/tiếng, nói không ra loa (ở nhà) | Trình duyệt chưa cho mic, hoặc HA mở bằng `http` | Mở HA bằng https; cho phép Micro. |
| Có hình/tiếng, nói không ra loa (4G) | WebRTC không nối được, thẻ tụt về MSE sau ~30 giây | Mở cổng 8555; kiểm CGNAT; kiểm máy go2rtc có đi VPN không. |
| Đã mở cổng mà 4G vẫn không có mic | Máy go2rtc ra internet qua VPN → `stun:` báo IP của VPN | [Router đẩy máy HA qua VPN](#router-đẩy-máy-ha-qua-vpn). |
| go2rtc báo `exec: Stdin already set` | Mở lại thẻ khi phiên cũ chưa đóng, hoặc hai thẻ mở mic cùng một luồng | Đóng thẻ ~10 giây rồi mở lại; mỗi luồng chỉ một thẻ có mic. |
| Thêm dòng `exec` qua giao diện go2rtc bị từ chối | go2rtc chặn nguồn `exec` qua API | Sửa thẳng `go2rtc.yaml`. |
| Tiếng ra loa trễ cả câu | Dòng `exec` thiếu `-probesize 32 -analyzeduration 0 -fflags nobuffer` | Dùng đúng dòng dịch vụ trả về. |
| Nói nhỏ thì loa không phát | Dưới ngưỡng -45 dBFS | Nói gần điện thoại hơn. |
| Đang nói thì không nghe bên kia | Camera tắt mic lúc loa mở | Bình thường — nói xong ngừng ~1,5 giây là nghe được. |
| Dòng `exec` gọi HA ra `401` | Sai khoá / camera đã xoá rồi thêm lại | Lấy lại dòng bằng `dahua_talk.get_intercom_source`. |
| Dòng `exec` không kết nối được HA | Sai `ha_url` (thường: `127.0.0.1` trong khi go2rtc ở máy/container khác) | [Bảng chọn `ha_url`](#chọn-ha_url-theo-cách-bạn-cài). |
| Từ gọi không bắt / STT mất chữ | Noise Filter của camera đang bật | Tắt Noise Filter trong SmartPSS. |
| Phải nói rất to mới bắt từ gọi | Mic camera nhỏ | `number.<camera>_tang_mic` +12…+18 dB. |
| `okay_nabu` / `hey_jarvis` không bắt khi ngồi xa | Mô hình giọng Anh, giọng Việt ở xa | Nói gần hơn, hoặc mô hình từ gọi tiếng Việt tự huấn luyện. |
| Thêm camera báo sai mật khẩu dù đúng | Camera đang khoá đăng nhập sau nhiều lần sai | Chờ vài phút (hoặc khởi động lại camera) rồi thử **một** lần. |
| WebRTC không có hình | Luồng chính H.265 | Đổi luồng chính sang H.264 trong SmartPSS. |

## Giới hạn

- Chỉ kênh nói 0 (camera một mắt). Số kênh ngoài dải làm một số firmware khởi động lại.
- Âm lượng loa chỉ chỉnh ở camera (SmartPSS / app Imou).
- Bộ đàm là **luân phiên** (như bộ đàm), không song công như gọi điện — do camera
  tắt mic lúc loa mở.

## Phát triển và test

```bash
pip install pytest-homeassistant-custom-component
# đúng phiên bản HA ghim cho các thành phần Assist/TTS/ffmpeg (bản mới nhất có thể lệch)
pip install $(python -c 'import json,os,homeassistant as h; b=os.path.join(os.path.dirname(h.__file__),"components"); print(" ".join(sorted({r for c in ("assist_pipeline","conversation","ffmpeg","tts") for r in json.load(open(os.path.join(b,c,"manifest.json"))).get("requirements",[])})))')
pytest
```

Phiên bản mới: nâng `version` trong `custom_components/dahua_talk/manifest.json` và
thêm mục `## <version>` vào `CHANGELOG.md` — workflow tự tạo release, HACS báo cập
nhật.
