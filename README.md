# Bộ 6 Custom Skills OpenClaw

Ngày chuẩn hóa gần nhất: 2026-08-04 UTC.

Nguồn: bộ skill chuẩn hóa để triển khai trên nhiều VPS/OpenClaw khác nhau.

## Danh sách skill

1. `gmail-invoice-extractor` - Đọc Gmail và trích xuất dữ liệu hóa đơn.
2. `google-calendar-openclaw` - Đọc, tạo, cập nhật và xóa lịch Google Calendar theo quyền đã cấu hình.
3. `google-drive-rclone-setup` - Thiết lập và vận hành kết nối Google Drive bằng rclone.
4. `google-gmail-send` - Gửi Gmail và file kết quả theo yêu cầu.
5. `post-fanpage-fb` - Chuẩn bị hoặc đăng nội dung lên Facebook Fanpage theo quy trình được duyệt.
6. `youtube-competitor-analysis` - Phân tích kênh hoặc nội dung YouTube của đối thủ.

## Ghi chú

- Mỗi skill nằm trong một folder riêng; toàn bộ `SKILL.md` đã được viết lại bằng tiếng Việt, bổ sung preflight, dependency, credential, quy trình an toàn và tiêu chí hoàn tất.
- Credential Google, Facebook, Telegram và API key nằm ngoài bộ skill, không được copy vào đây.
- Khi chỉnh sửa thử nghiệm, ưu tiên làm trên bộ xuất này để không ảnh hưởng trợ lý đang chạy.
- Trước khi chạy block lệnh trong một skill, chuyển thư mục hiện hành vào đúng folder skill đó để `SKILL_DIR="$(pwd -P)"` hoạt động chính xác.
- Cấu trúc chuẩn suy ra `RUNTIME_ROOT` bằng đường dẫn tương đối `SKILL_DIR/../../../..`; nếu VPS dùng cấu trúc khác, chỉ định `OPENCLAW_RUNTIME_ROOT` thay vì sửa hardcode trong skill.
- Không đóng gói `.git`, `__pycache__`, file `.pyc`, log, output thử nghiệm hoặc artifact runtime vào từng folder skill.
- Không ghi đường dẫn filesystem tuyệt đối của VPS vào source hoặc tài liệu. Shebang hệ thống chuẩn và URL API không được xem là đường dẫn dữ liệu VPS.

## Kết quả kiểm tra ngày 2026-08-04

- `gmail-invoice-extractor`: đạt; chạy trọn pipeline bằng ngày tương lai, tạo workbook 5 sheet và không tải attachment.
- `google-calendar-openclaw`: đạt; đọc sự kiện từ Calendar ID đã cấu hình, không tạo/sửa/xóa lịch.
- `google-drive-rclone-setup`: đạt; nhận remote `gdrive:` và đọc danh sách cấp một, không ghi/xóa file.
- `google-gmail-send`: đạt; OAuth refresh được, đọc Gmail thành công, tạo–xóa draft kiểm tra thành công và không gửi email.
- `post-fanpage-fb`: đạt; đã sửa wrapper trỏ đúng project, Facebook identity và Google Sheet đọc được, không đăng bài hoặc gửi tin.
- `youtube-competitor-analysis`: đạt; thu dữ liệu bằng `yt-dlp`, tạo workbook 7 sheet và mở lại thành công.
- Cả sáu skill có frontmatter hợp lệ, code Python/JSON/shell parse thành công, không có broken symlink và không phát hiện credential trong bộ xuất.
- Kiểm tra portability trên cây VPS giả lập đạt 6/6 khi `HOME` và `PATH` không trỏ về VPS nguồn.
- Quét cả file text và binary không còn đường dẫn home tuyệt đối, username VPS, `.git`, `__pycache__` hoặc `.pyc` trong bộ xuất.

## Lưu ý runtime member hiện tại

Mọi skill suy ra `RUNTIME_ROOT` bằng đường dẫn tương đối từ folder skill. Nếu VPS dùng cấu trúc khác chuẩn OpenClaw, đặt biến `OPENCLAW_RUNTIME_ROOT`. Với binary local, dùng:

```bash
export PATH="$RUNTIME_ROOT/.local/bin:$PATH"
```
