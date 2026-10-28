# Quy tắc tài nguyên (RAM, CPU, kết nối, luồng)

Tích hợp chạy trong tiến trình Home Assistant dùng chung: một chỗ ngốn tài nguyên là cả Home Assistant đầy RAM rồi bị khởi động
lại. Mã mới phải theo các quy tắc sau; ba quy tắc đầu có test canh (`tests/test_quy_tac_tai_nguyen.py`).

1. **Hàng đợi luôn có trần.** Mọi `asyncio.Queue` có `maxsize`; đầy thì bỏ khúc **cũ nhất** (`hang_doi.day_bo_cu_nhat`), không
   để RAM tăng khi kênh nói tới camera tắc. Bộ đệm theo thời gian (đệm đầu câu) có trần theo số giây.
2. **Không chặn vòng lặp sự kiện.** Trong mã bất đồng bộ không `time.sleep`, `requests`, `urllib.request`, `subprocess.run`;
   việc chặn (ffmpeg đồng bộ, SDK) chạy trong luồng/executor riêng, không trên vòng lặp chính.
3. **Tiến trình con luôn dọn.** Mỗi `Popen`/`create_subprocess_exec` có `kill()` rồi `wait()` trong `finally`, không để tiến trình
   ffmpeg mồ côi chiếm CPU/RAM.
4. **Mở nhanh, đóng nhanh.** Kết nối tới camera/loa mở khi cần, đóng ngay khi xong; luồng nói mở lúc có tiếng, đóng khi im
   (`IM_GIAY`).
5. **Lỗi lặp thì nghỉ tăng dần**; mọi vòng `while True` có `await` thật; tác vụ nền gắn vòng đời và huỷ khi gỡ.
6. **Nhật ký chỉ ghi kiểu lỗi một lần**, không ghi mỗi vòng, không ghi bí mật.
