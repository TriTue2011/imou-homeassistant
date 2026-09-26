# Từ gọi tiếng Việt «Trợ lý» cho openWakeWord

`tro_ly.tflite` — mô hình từ gọi **«Trợ lý»** (và «Trợ lý ơi») cho
[wyoming-openwakeword](https://github.com/rhasspy/wyoming-openwakeword) 2.x, dùng với vệ tinh
Assist của tích hợp này hoặc bất kỳ vệ tinh nào trong Home Assistant.

Các mẫu có sẵn như «Okay Nabu» học từ giọng tiếng Anh — người Việt đọc không giống nên hay
trượt, nhất là qua mic camera ở xa.

## Cài

1. Chép `tro_ly.tflite` vào thư mục mô hình riêng của container openWakeWord (thư mục gắn vào
   `--custom-model-dir`).
2. Khởi động lại container openWakeWord.
3. Home Assistant → **Cài đặt → Trợ lý giọng nói** → chọn pipeline → **Từ đánh thức** → `tro_ly`.

Ngưỡng mặc định **0,5** của container là đủ (xem số đo).

## Số đo

Chấm bằng `pyopen_wakeword` — đúng thư viện wyoming-openwakeword 2.x dùng:

| Thử | Kết quả |
|---|---|
| Giọng máy chưa có trong dữ liệu học | bắt đúng 96,5 % (ngưỡng 0,5) |
| Giọng người thật chưa có trong dữ liệu học (ghi bằng điện thoại) | 0,99 |
| Gọi qua mic camera trong phòng khách | 4/4 lần |
| Tiếng sinh hoạt trong phòng (nói chuyện, tivi) | điểm cao nhất 0,01 — không lần nào thức nhầm |
| Từ gần âm («Trợ lực», «Thư ký», «Quản lý»…) | thức nhầm 3,8 % ở 0,5; 2,6 % ở 0,9 |

Học từ ~100 giọng tiếng Việt tổng hợp (câu có từ gọi, câu gần âm, câu nói thường) cộng vài
câu người thật, mỗi câu làm méo nhiều bản (vang phòng, dải tần mic camera, to nhỏ, nhanh chậm).
Đặc trưng là bộ trích embedding có sẵn của openWakeWord; đầu phân loại nhỏ đầu vào `[1, 16, 96]`.

## Tự thử trên bản ghi của bạn

```bash
pip install pyopen-wakeword numpy
python cham_tu_goi.py tro_ly.tflite ban_ghi.wav      # WAV 16 kHz mono, hoặc PCM16 thô .pcm
```

In điểm cao nhất và các mốc (giây) vượt 0,95. Tệp ngắn (một câu gọi) được đệm nền trước/sau.
