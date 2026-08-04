---
name: "google-gmail-send"
description: "Gửi Gmail cá nhân bằng OAuth với nội dung text/HTML và nhiều file đính kèm. Dùng khi người dùng yêu cầu rõ việc gửi email hoặc gửi kết quả từ skill khác qua Gmail; không tự gửi khi yêu cầu chỉ là soạn thảo, phân tích hoặc xem trước."
---

# Gửi Gmail cá nhân bằng OAuth

## Nguyên tắc bắt buộc

- Chỉ gửi thật khi người dùng yêu cầu rõ và đã xác định người nhận.
- Không dùng Service Account để gửi Gmail cá nhân.
- Không in client secret, access token, refresh token hoặc nội dung credential.
- Kiểm tra người nhận, tiêu đề, text fallback, HTML và toàn bộ attachment trước khi gửi.
- Chỉ gọi API gửi một lần. Nếu trạng thái không rõ, không tự gửi lại.
- Chỉ báo hoàn tất khi stdout có `gmail_send=ok` và `sent_verified=true`.

## Môi trường và OAuth

- Python mặc định: `RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python`; nếu không tồn tại, wrapper dùng `python3` trong `PATH`.
- Có thể ép một Python cụ thể bằng biến `OPENCLAW_DOCUMENT_PYTHON`.
- OAuth client dùng chung nằm tại `RUNTIME_ROOT/AI_Runtime/client.json`; trên VPS này là `/root/AI_Runtime/client.json`.
- Có thể đổi file client chung bằng biến `OPENCLAW_GOOGLE_CLIENT_JSON`.
- Wrapper kiểm tra `client.json` trước lệnh `profile` hoặc `send`: thiếu/không đọc được thì báo đúng đường dẫn và dừng; nếu tồn tại thì không in thông báo thừa.
- Quyền người dùng mặc định nằm tại `RUNTIME_ROOT/.config/openclaw-google-calendar/oauth-user.json`; có thể đổi thư mục bằng `OPENCLAW_GOOGLE_OAUTH_DIR`.
- `client.json` chung chứa Client ID/Client Secret để nhận diện ứng dụng Google.
- `oauth-user.json` chứa quyền người dùng sau khi hoàn thành kết nối OAuth và phải có refresh token.
- Scope phải cho phép gửi Gmail, ví dụ `gmail.send`, `gmail.compose` hoặc `gmail.modify`.
- Thư mục credential nên có quyền `0700`; hai file OAuth phải có quyền `0600`.
- Không copy credential vào folder skill hoặc file báo cáo.

## Kiểm tra runtime

```bash
SKILL_DIR="$(pwd -P)"
RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT:-$HOME}"
PY="${OPENCLAW_DOCUMENT_PYTHON:-$RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python}"
if [ ! -x "$PY" ]; then PY="$(command -v python3)"; fi
CLIENT_JSON="${OPENCLAW_GOOGLE_CLIENT_JSON:-$RUNTIME_ROOT/AI_Runtime/client.json}"

test -x "$PY"
"$PY" -c 'import requests'
test -r "$CLIENT_JSON"
OPENCLAW_RUNTIME_ROOT="$RUNTIME_ROOT" \
  "$SKILL_DIR/scripts/run_gmail_send.sh" --help
```

Nếu import thất bại, chỉ cài phần còn thiếu:

```bash
"$PY" -m pip install -r "$SKILL_DIR/requirements.txt"
"$PY" -m pip check
```

## Kiểm tra OAuth không gửi thư

```bash
OPENCLAW_RUNTIME_ROOT="$RUNTIME_ROOT" \
  "$SKILL_DIR/scripts/run_gmail_send.sh" profile
```

`profile` chỉ đọc hồ sơ Gmail và làm mới quyền truy cập khi cần. Nếu gặp `401/403`, dừng và kiểm tra lại OAuth/scopes; không yêu cầu mật khẩu Google, OTP hoặc mã khôi phục.

## Chuẩn bị nội dung

- Email ngắn có thể dùng text thuần qua `--body`.
- Báo cáo hoặc nghiên cứu nên dùng thêm `--html-file`, đồng thời vẫn truyền `--body` làm text fallback.
- HTML phải tự chứa, tương thích Gmail, không JavaScript, không external stylesheet và không tài nguyên yêu cầu đăng nhập.
- Escape dữ liệu động trước khi đưa vào HTML.
- Kiểm tra HTML không rỗng, không còn placeholder và không chứa dữ liệu từ tác vụ cũ.
- Có thể lặp `--attachment` để gửi nhiều file.

## Template HTML mẫu

- Template dashboard dùng lại nằm tại `assets/analysis_report_email_template.html`.
- Template giữ giao diện của email báo cáo YouTube đã kiểm thử: hero tối, bốn thẻ chỉ số, kết luận, bảng top, hai thẻ insight, đề xuất và phần giới hạn/attachment.
- Không chỉnh trực tiếp file trong `assets`; luôn copy sang thư mục đầu ra của tác vụ rồi mới điền dữ liệu.
- Chỉ điền dữ liệu từ báo cáo hiện tại; không giữ cứng tên kênh, ngày, chỉ số hoặc kết luận của lần gửi trước.
- Escape text động. Các placeholder kết thúc bằng `_HTML` chỉ nhận fragment HTML đã được tạo có kiểm soát như `<li>`, `<tr>` hoặc chuỗi có `<br>`.
- Bắt buộc thay toàn bộ `{{...}}` trước khi gửi; `gmail_send.py` sẽ từ chối HTML còn placeholder.

```bash
OUTPUT_DIR="/duong/dan/ket-qua"
cp "$SKILL_DIR/assets/analysis_report_email_template.html" \
  "$OUTPUT_DIR/email_report.html"

test -s "$OUTPUT_DIR/email_report.html"
if rg -n '\{\{[^}]+\}\}' "$OUTPUT_DIR/email_report.html"; then
  echo "HTML còn placeholder" >&2
  exit 1
fi
```

Các nhóm placeholder chính:

- Tiêu đề: `REPORT_KICKER`, `REPORT_TITLE`, `REPORT_SUBTITLE`, `EMAIL_PREHEADER`.
- Chỉ số: `METRIC_1_VALUE` đến `METRIC_4_VALUE` và nhãn tương ứng.
- Nội dung động: `SUMMARY_ITEMS_HTML`, `TOP_TABLE_ROWS_HTML`, hai card insight và `RECOMMENDATION_ITEMS_HTML`.
- Cuối email: `LIMITATIONS_HTML` và `ATTACHMENT_SUMMARY_HTML`.

## Gửi email

```bash
OPENCLAW_RUNTIME_ROOT="$RUNTIME_ROOT" \
  "$SKILL_DIR/scripts/run_gmail_send.sh" send \
  --to "nguoinhan@example.com" \
  --subject "Kết quả công việc" \
  --body "Bản tóm tắt dạng text." \
  --html-file "/duong/dan/email.html" \
  --attachment "/duong/dan/bao_cao.xlsx"
```

Luồng từ skill khác phải tách rõ: skill nguồn tạo và xác minh báo cáo; `google-gmail-send` chỉ nhận nội dung cuối cùng cùng attachment để gửi.

## Xác minh và báo cáo

- Script kiểm tra message vừa gửi có nhãn `SENT`, đúng người nhận, tiêu đề và danh sách attachment.
- Báo người nhận, tiêu đề và tên attachment; không báo hoặc lưu Gmail message ID khi không cần.
- Nếu Gmail chấp nhận gửi nhưng bước xác minh thất bại, báo trạng thái chưa chắc chắn và không tự gửi lại.

## Tiêu chí hoàn tất

- Runtime và import thư viện đạt.
- `profile` thành công trước khi gửi.
- Email chỉ được gửi theo yêu cầu rõ ràng.
- Kết quả trả `gmail_send=ok` và `sent_verified=true`.
