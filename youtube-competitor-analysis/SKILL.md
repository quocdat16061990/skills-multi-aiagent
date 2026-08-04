---
name: "youtube-competitor-analysis"
description: "Thu thập dữ liệu công khai từ kênh YouTube, phân tích Videos/Shorts, xuất báo cáo Excel 7 sheet và tùy chọn gửi email HTML kèm workbook qua Gmail OAuth trong cùng một lần chạy. Dùng khi cần nghiên cứu đối thủ, chủ đề, tiêu đề, hook, hiệu suất nội dung hoặc gửi báo cáo YouTube; không đăng nhập YouTube, không dùng cookie và không vượt cơ chế chặn."
---

# Phân tích kênh YouTube đối thủ

## Nguyên tắc bắt buộc

- Chỉ dùng dữ liệu công khai; không đăng nhập, không dùng cookie, proxy hoặc kỹ thuật né CAPTCHA/chặn truy cập.
- Chỉ gửi email khi người dùng yêu cầu rõ và CLI có `--email-to`; không có tham số này thì chỉ tạo báo cáo.
- Dry-run tuyệt đối không gửi email, kể cả khi có `--email-to`.
- Khi gửi, chỉ gọi Gmail API một lần rồi xác minh message có nhãn `SENT`, đúng người nhận, tiêu đề và workbook đính kèm; không tự gửi lại nếu trạng thái chưa chắc chắn.
- Không in client secret, access token, refresh token hoặc nội dung credential.
- Không biến nhãn phân loại hoặc suy luận thành dữ kiện của tác giả.
- Không báo thành công nếu thu được `0` video mà không giải thích rõ giới hạn.
- Giới hạn mỗi lần chạy từ 1 đến 100 video.

## Môi trường

- Python chuẩn được tính từ `RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python`; nếu không tồn tại, có thể dùng `python3` trong `PATH`.
- Thư viện Python bắt buộc: `requests`, `openpyxl`.
- Binary bắt buộc để chạy ổn định: `yt-dlp`.
- Ưu tiên tìm `yt-dlp` trong PATH; fallback được tính từ `RUNTIME_ROOT/.local/bin` hoặc thư mục `bin` của document venv.
- Không cần API key YouTube.
- Cả ba skill Google dùng chung một OAuth client tại `RUNTIME_ROOT/AI_Runtime/client.json`; trên VPS này là `/root/AI_Runtime/client.json`.
- Có thể đổi file client chung bằng `OPENCLAW_GOOGLE_CLIENT_JSON` hoặc truyền trực tiếp `--client-json`.
- Khi có `--email-to` và không phải dry-run, CLI kiểm tra `client.json` trước khi quét YouTube: thiếu/không đọc được thì báo đúng đường dẫn và dừng; nếu tồn tại thì không in thông báo thừa.
- Quyền người dùng mặc định nằm riêng tại `RUNTIME_ROOT/.config/openclaw-google-calendar/oauth-user.json`; có thể đổi thư mục bằng `OPENCLAW_GOOGLE_OAUTH_DIR` hoặc truyền `--oauth-user-json`.
- `client.json` chung nhận diện ứng dụng Google; `oauth-user.json` chứa quyền người dùng và phải có refresh token cùng scope gửi Gmail.
- Hai file OAuth phải có quyền `0600`; không copy credential vào folder skill hoặc thư mục kết quả.

## Kiểm tra và cài điều kiện

```bash
SKILL_DIR="$(pwd -P)"
RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT:-$HOME}"
PY="$RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python"
if [ ! -x "$PY" ]; then PY="$(command -v python3)"; fi
CLIENT_JSON="${OPENCLAW_GOOGLE_CLIENT_JSON:-$RUNTIME_ROOT/AI_Runtime/client.json}"
export PATH="$(dirname "$PY"):$RUNTIME_ROOT/.local/bin:$PATH"

test -x "$PY"
"$PY" -c 'import requests, openpyxl'
test -r "$CLIENT_JSON"
command -v yt-dlp
"$PY" "$SKILL_DIR/scripts/youtube_competitor_analysis.py" --help
```

Nếu thiếu thư viện Python:

```bash
"$PY" -m pip install 'requests>=2.32,<3' 'openpyxl>=3.1,<4'
"$PY" -m pip check
```

Nếu thiếu `yt-dlp`:

```bash
"$PY" -m pip install yt-dlp
export PATH="$(dirname "$PY"):$RUNTIME_ROOT/.local/bin:$PATH"
command -v yt-dlp
```

Không cài lại khi import và binary đã hoạt động.

## Chạy dry-run

```bash
"$PY" "$SKILL_DIR/scripts/youtube_competitor_analysis.py" \
  "https://www.youtube.com/@TEN_KENH/videos" \
  --limit 10 \
  --dry-run \
  --email-to "nguoinhan@example.com" \
  --config "$SKILL_DIR/templates/report_config.json"
```

Kiểm tra JSON stdout:

- `status=ok`.
- `dry_run=true`.
- `source=yt-dlp` là trạng thái ưu tiên.
- `counts.videos` phải lớn hơn 0 để coi là bài test chức năng đạt.
- Nếu có `--email-to`, JSON phải trả `email.status=not_sent` và `reason=dry_run`.
- Đọc `warnings`; nếu YouTube chặn hoặc dữ liệu rỗng thì dừng, không né chặn.

## Xuất báo cáo Excel

```bash
OUTPUT_DIR="$RUNTIME_ROOT/Data/ket_qua/youtube"
"$PY" "$SKILL_DIR/scripts/youtube_competitor_analysis.py" \
  "https://www.youtube.com/@TEN_KENH/videos" \
  --limit 50 \
  --output-dir "$OUTPUT_DIR" \
  --config "$SKILL_DIR/templates/report_config.json"
```

## Phân tích và gửi Gmail trong một lần chạy

Không gọi skill gửi mail khác. CLI hiện tự thực hiện toàn bộ chuỗi:

1. Thu thập dữ liệu YouTube công khai.
2. Phân loại, tính chỉ số và tạo workbook 7 sheet.
3. Render email HTML từ `assets/analysis_report_email_template.html` bằng dữ liệu của lần chạy hiện tại.
4. Tạo text fallback.
5. Gửi Gmail kèm workbook và xác minh trực tiếp trong `SENT`.

```bash
OUTPUT_DIR="$RUNTIME_ROOT/Data/ket_qua/youtube"

OPENCLAW_RUNTIME_ROOT="$RUNTIME_ROOT" \
"$PY" "$SKILL_DIR/scripts/youtube_competitor_analysis.py" \
  "https://www.youtube.com/@TEN_KENH/shorts" \
  --limit 100 \
  --output-dir "$OUTPUT_DIR" \
  --config "$SKILL_DIR/templates/report_config.json" \
  --email-to "nguoinhan@example.com" \
  --email-subject "Báo cáo phân tích đối thủ YouTube"
```

Nếu bỏ `--email-subject`, script tự tạo tiêu đề từ tên kênh và ngày chạy. Nếu gửi thành công, JSON phải có:

- `status=ok`.
- `output` là workbook đã xác minh.
- `email_html` là HTML đã render và không còn placeholder.
- `email.status=ok`.
- `email.sent_verified=true`.
- `email.attachments` chứa đúng tên workbook.

Nếu workbook tạo thành công nhưng gửi thất bại, JSON trả `status=partial`, giữ đường dẫn `output` và `email_html`, đồng thời không tự gửi lại.

## Template email tích hợp

- Template nằm ngay trong skill tại `assets/analysis_report_email_template.html`; không phụ thuộc skill gửi mail khác.
- Template gồm hero, bốn thẻ chỉ số, kết luận nhanh, bảng top video, chủ đề/hook, đề xuất và giới hạn dữ liệu.
- `scripts/email_report.py` tự escape dữ liệu text, tạo các fragment HTML có kiểm soát và bắt buộc thay đủ placeholder.
- Không giữ cứng tên kênh, ngày, số liệu, top video hoặc nhận định của lần chạy trước.
- `scripts/gmail_sender.py` từ chối HTML rỗng, còn placeholder, JavaScript hoặc external stylesheet.

## Nguyên tắc phân tích

- **Dữ kiện**: trường quan sát trực tiếp từ nguồn công khai.
- **Mã hóa**: nhãn deterministic theo cấu hình/từ khóa; không phải tuyên bố của tác giả.
- **Suy luận**: phải nêu bằng chứng, mức tin cậy và không khẳng định quan hệ nhân quả.
- Chỉ tính `views/day` khi parse được ngày đăng tuyệt đối chắc chắn.
- Luôn tách Shorts, long-form và `unknown`.
- Chỉ gắn hook khi có cụm tiêu đề khớp; lưu bằng chứng cụm từ.
- Đọc `references/analysis_framework.md` khi diễn giải và `references/excel_schema.md` khi kiểm tra workbook.

## Xác minh đầu ra

Workbook phải mở lại được bằng `openpyxl` và có đúng 7 sheet:

- `Tong_quan`
- `Du_lieu_video`
- `Top_video`
- `Chu_de`
- `Hook_va_tieu_de`
- `De_xuat_hanh_dong`
- `Nguon_va_gioi_han`

Khi có `--email-to`, kiểm tra thêm:

- File HTML tồn tại, đọc được và không còn `{{...}}`.
- Text fallback không rỗng.
- Workbook là attachment duy nhất mặc định.
- Kết quả `sent_verified=true`; nếu không đạt, không gửi lại.

## Tiêu chí hoàn tất

- Runtime, import và `yt-dlp` đạt.
- Dry-run thu được ít nhất một video công khai.
- Báo cáo Excel mở lại được và đủ 7 sheet.
- Nguồn, cảnh báo và giới hạn dữ liệu được ghi rõ.
- Nếu người dùng yêu cầu gửi, cùng một CLI phải tạo HTML, gửi workbook và xác minh `SENT`; không gọi skill thứ hai.
