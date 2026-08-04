---
name: "gmail-invoice-extractor"
description: "Đọc Gmail cá nhân theo khoảng ngày, tải tệp hóa đơn PDF/XML/ảnh/ZIP an toàn, trích xuất trường dữ liệu và tạo workbook Excel để rà soát. Dùng khi cần tổng hợp hóa đơn từ Gmail, kiểm tra attachment hóa đơn hoặc tạo báo cáo hóa đơn; không dùng để gửi email."
---

# Trích xuất hóa đơn từ Gmail

## Nguyên tắc bắt buộc

- Chỉ đọc Gmail và tải attachment; không sửa, xóa, đánh dấu hoặc gửi email.
- Không in `client_secret`, access token, refresh token, message ID hoặc nội dung credential.
- Luôn chạy `--dry-run` trước khi tải attachment thật.
- Giữ file gốc, ghi kết quả vào thư mục đầu ra mới và rà soát workbook trước khi sử dụng.
- Không khẳng định trường hóa đơn có độ tin cậy thấp là dữ kiện chắc chắn.

## Môi trường và credential

- Python chuẩn được tính từ `RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python`.
- Thư viện bắt buộc nằm trong `requirements.txt`: `requests`, `openpyxl`, `pypdf`, `pdfplumber`, `Pillow`.
- OAuth mặc định được tính từ `RUNTIME_ROOT/.config/openclaw-google-calendar/client.json` và `token.json`.
- Có thể đổi thư mục OAuth bằng biến `OPENCLAW_GOOGLE_OAUTH_DIR`.
- Token phải có khả năng đọc Gmail, ví dụ scope `gmail.readonly` hoặc `gmail.modify`.
- File OAuth phải có quyền `0600`; thư mục credential nên có quyền `0700`.
- OCR ảnh là tùy chọn. Chỉ bật `--ocr` khi có binary `tesseract` và ngôn ngữ `vie+eng`.

## Kiểm tra và cài thư viện

```bash
SKILL_DIR="$(pwd -P)"
RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT:-$(CDPATH= cd -- "$SKILL_DIR/../../../.." && pwd -P)}"
PY="$RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python"

test -x "$PY"
test -r "$RUNTIME_ROOT/.config/openclaw-google-calendar/client.json"
test -r "$RUNTIME_ROOT/.config/openclaw-google-calendar/token.json"
"$PY" -c 'import requests, openpyxl, pypdf, pdfplumber; from PIL import Image'
"$SKILL_DIR/scripts/run_invoice_extractor.sh" --help
```

Nếu lệnh import thất bại, chỉ cài phần còn thiếu bằng:

```bash
"$PY" -m pip install -r "$SKILL_DIR/requirements.txt"
"$PY" -m pip check
```

Không cài lại hoặc nâng cấp hàng loạt khi các import đã đạt.

## Chạy thử không tải file

```bash
OPENCLAW_RUNTIME_ROOT="$RUNTIME_ROOT" \
"$SKILL_DIR/scripts/run_invoice_extractor.sh" \
  --start-date 2026-08-01 \
  --end-date 2026-08-04 \
  --output-dir "$RUNTIME_ROOT/Data/ket_qua/invoice-test" \
  --dry-run
```

Chỉ tiếp tục khi JSON trả `dry_run=true` và số lượng thư/attachment hợp lý.

## Chạy trích xuất thật

```bash
OPENCLAW_RUNTIME_ROOT="$RUNTIME_ROOT" \
"$SKILL_DIR/scripts/run_invoice_extractor.sh" \
  --start-date 2026-08-01 \
  --end-date 2026-08-04 \
  --output-dir "$RUNTIME_ROOT/Data/ket_qua/invoice-2026-08"
```

Thêm `--ocr` chỉ khi đã xác minh `tesseract --list-langs` có `vie` và `eng`.

## Đầu ra và xác minh

- Đọc JSON stdout để kiểm tra số thư, attachment, hóa đơn, bản trùng và lỗi.
- Mở lại `invoice_report.xlsx` bằng `openpyxl` và xác nhận đủ 5 sheet.
- Đọc `references/invoice_fields.md` khi cần hiểu trường dữ liệu và mức tin cậy.
- Báo rõ file nào cần rà soát thủ công; không che lỗi hoặc trường bị thiếu.
- Muốn gửi workbook qua Gmail phải chuyển sang skill `google-gmail-send` và chỉ gửi khi người dùng yêu cầu rõ.

## Tiêu chí hoàn tất

- Runtime và import thư viện đạt.
- OAuth đọc Gmail thành công nhưng không lộ credential.
- Dry-run đạt trước khi tải thật.
- Workbook tồn tại, mở lại được và kết quả đã được rà soát.
