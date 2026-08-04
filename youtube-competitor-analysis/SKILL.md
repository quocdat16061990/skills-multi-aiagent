---
name: "youtube-competitor-analysis"
description: "Thu thập dữ liệu công khai từ kênh YouTube, phân tích Videos/Shorts và xuất báo cáo Excel 7 sheet. Dùng khi cần nghiên cứu đối thủ, chủ đề, tiêu đề, hook hoặc hiệu suất nội dung YouTube; không đăng nhập, không dùng cookie và không vượt cơ chế chặn."
---

# Phân tích kênh YouTube đối thủ

## Nguyên tắc bắt buộc

- Chỉ dùng dữ liệu công khai; không đăng nhập, không dùng cookie, proxy hoặc kỹ thuật né CAPTCHA/chặn truy cập.
- Không gửi email; nếu cần gửi báo cáo phải dùng skill `google-gmail-send` theo yêu cầu riêng.
- Không biến nhãn phân loại hoặc suy luận thành dữ kiện của tác giả.
- Không báo thành công nếu thu được `0` video mà không giải thích rõ giới hạn.
- Giới hạn mỗi lần chạy từ 1 đến 100 video.

## Môi trường

- Python chuẩn được tính từ `RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python`.
- Thư viện Python bắt buộc: `requests`, `openpyxl`.
- Binary bắt buộc để chạy ổn định: `yt-dlp`.
- Ưu tiên tìm `yt-dlp` trong PATH; fallback được tính từ `RUNTIME_ROOT/.local/bin` hoặc thư mục `bin` của document venv.
- Không cần API key YouTube.

## Kiểm tra và cài điều kiện

```bash
SKILL_DIR="$(pwd -P)"
RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT:-$(CDPATH= cd -- "$SKILL_DIR/../../../.." && pwd -P)}"
PY="$RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python"
export PATH="$(dirname "$PY"):$RUNTIME_ROOT/.local/bin:$PATH"

test -x "$PY"
"$PY" -c 'import requests, openpyxl'
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
  --config "$SKILL_DIR/templates/report_config.json"
```

Kiểm tra JSON stdout:

- `status=ok`.
- `dry_run=true`.
- `source=yt-dlp` là trạng thái ưu tiên.
- `counts.videos` phải lớn hơn 0 để coi là bài test chức năng đạt.
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

## Tiêu chí hoàn tất

- Runtime, import và `yt-dlp` đạt.
- Dry-run thu được ít nhất một video công khai.
- Báo cáo Excel mở lại được và đủ 7 sheet.
- Nguồn, cảnh báo và giới hạn dữ liệu được ghi rõ.
