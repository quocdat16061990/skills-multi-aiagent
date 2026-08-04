---
name: "gmail-invoice-extractor"
description: "Chỉ đọc Gmail Inbox theo khoảng ngày, tải tệp hóa đơn PDF/XML/ảnh/ZIP an toàn, trích xuất trường dữ liệu và tạo workbook Excel để rà soát. Dùng khi cần tổng hợp hóa đơn trong hộp thư đến, kiểm tra attachment hóa đơn hoặc tạo báo cáo hóa đơn; không dùng để gửi email."
---

# Trích xuất hóa đơn từ Gmail

## Nguyên tắc bắt buộc

- Chỉ đọc nhãn `INBOX` và tải attachment; không quét All Mail, Sent, Spam hoặc Trash, không sửa, xóa, đánh dấu hoặc gửi email.
- Không in `client_secret`, access token, refresh token, message ID hoặc nội dung credential.
- Luôn chạy `--dry-run` trước khi tải attachment thật.
- Giữ file gốc, ghi kết quả vào thư mục đầu ra mới và rà soát workbook trước khi sử dụng.
- Không khẳng định trường hóa đơn có độ tin cậy thấp là dữ kiện chắc chắn.

## Môi trường và credential

- Python chuẩn được tính từ `RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python`.
- Thư viện bắt buộc nằm trong `requirements.txt`: `requests`, `openpyxl`, `pypdf`, `pdfplumber`, `Pillow`.
- OAuth client dùng chung được tính từ `RUNTIME_ROOT/AI_Runtime/client.json`; trên VPS này là `/root/AI_Runtime/client.json`.
- Có thể đổi file client chung bằng biến `OPENCLAW_GOOGLE_CLIENT_JSON`.
- Wrapper kiểm tra `client.json` trước dry-run/chạy thật: thiếu/không đọc được thì báo đúng đường dẫn và dừng; nếu tồn tại thì không in thông báo thừa.
- `client.json` chỉ nhận diện ứng dụng OAuth; quyền người dùng sau bước kết nối phải được lưu trong `oauth-user.json` tại `RUNTIME_ROOT/.config/openclaw-google-calendar` hoặc thư mục được đặt bởi `OPENCLAW_GOOGLE_OAUTH_DIR`. n8n có thể trông như chỉ cần Client ID/Secret vì quyền người dùng được lưu bên trong credential của n8n sau bước kết nối tài khoản.
- Token phải có khả năng đọc Gmail, ví dụ scope `gmail.readonly` hoặc `gmail.modify`.
- File OAuth phải có quyền `0600`; thư mục credential nên có quyền `0700`.
- Không copy `client.json` hoặc `oauth-user.json` vào folder skill.
- OCR ảnh là tùy chọn. Chỉ bật `--ocr` khi có binary `tesseract` và ngôn ngữ `vie+eng`.
- Khoảng ngày được lọc bằng Unix timestamp theo timezone; mặc định là `Asia/Ho_Chi_Minh` và có thể đổi bằng `--timezone`.

## Kiểm tra và cài thư viện

```bash
SKILL_DIR="$(pwd -P)"
RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT:-$HOME}"
PY="$RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python"
CLIENT_JSON="${OPENCLAW_GOOGLE_CLIENT_JSON:-$RUNTIME_ROOT/AI_Runtime/client.json}"

test -x "$PY"
test -r "$CLIENT_JSON"
test -r "$RUNTIME_ROOT/.config/openclaw-google-calendar/oauth-user.json"
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
  --timezone Asia/Ho_Chi_Minh \
  --output-dir "$RUNTIME_ROOT/Data/ket_qua/invoice-test" \
  --dry-run
```

Chỉ tiếp tục khi JSON trả `dry_run=true` và số lượng thư/attachment hợp lý. Kết quả bắt buộc chỉ đến từ `INBOX`. Dry-run chỉ trả số thứ tự, tên file, MIME type và kích thước; không trả Gmail message ID hoặc attachment ID.

## Chạy trích xuất thật

```bash
OPENCLAW_RUNTIME_ROOT="$RUNTIME_ROOT" \
"$SKILL_DIR/scripts/run_invoice_extractor.sh" \
  --start-date 2026-08-01 \
  --end-date 2026-08-04 \
  --timezone Asia/Ho_Chi_Minh \
  --output-dir "$RUNTIME_ROOT/Data/ket_qua/invoice-2026-08"
```

Thêm `--ocr` chỉ khi đã xác minh `tesseract --list-langs` có `vie` và `eng`.

## Đầu ra và xác minh

- Đọc JSON stdout để kiểm tra số thư, attachment, hóa đơn, bản trùng và lỗi.
- Xác nhận truy vấn và code đều khóa nhãn `INBOX`; không tự mở rộng sang All Mail.
- Mở lại `invoice_report.xlsx` bằng `openpyxl` và xác nhận đủ 5 sheet.
- Đọc `references/invoice_fields.md` khi cần hiểu trường dữ liệu và mức tin cậy.
- Báo rõ file nào cần rà soát thủ công; không che lỗi hoặc trường bị thiếu.
- File không có đủ trường nhận diện sẽ không được tính là hóa đơn; ảnh không OCR sẽ vào rà soát hoặc được đánh dấu bản trùng khi subject và người gửi khớp số hóa đơn đã bóc tách.
- Workbook và đường dẫn output chỉ dùng số thứ tự nội bộ, không chứa Gmail message ID, thread ID hoặc attachment ID.
- Sau khi xác minh, bàn giao workbook Excel trực tiếp trong cuộc trò chuyện hiện tại.

## Bàn giao kết quả trong cuộc trò chuyện

- Mặc định chỉ trả file workbook Excel đã kiểm tra cho người dùng ngay tại kênh chat hiện tại; không tự gửi email.
- Nếu nền tảng hỗ trợ upload file, tải workbook lên trực tiếp. Nếu không, trả đường dẫn tuyệt đối, chính xác và có thể mở được tới workbook.
- Tóm tắt ngắn khoảng ngày, số thư, attachment, hóa đơn duy nhất, bản trùng và số mục cần rà soát kèm theo file.
- Giữ PDF, XML, JPG, PNG và ZIP gốc trong thư mục đầu ra; chỉ gửi thêm các chứng từ này khi người dùng yêu cầu rõ.
- Chỉ chuyển sang skill `google-gmail-send` khi người dùng nói rõ muốn gửi qua email và cung cấp hoặc xác nhận người nhận.

## Tiêu chí hoàn tất

- Runtime và import thư viện đạt.
- OAuth đọc Gmail thành công nhưng không lộ credential.
- Dry-run đạt trước khi tải thật.
- Workbook tồn tại, mở lại được và kết quả đã được rà soát.
- Không có Gmail message ID, thread ID hoặc attachment ID trong stdout, đường dẫn output hoặc workbook.
- Workbook đã được bàn giao trực tiếp trong cuộc trò chuyện hoặc có đường dẫn mở được nếu nền tảng không hỗ trợ upload.
