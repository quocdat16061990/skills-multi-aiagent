---
name: "google-gmail-send"
description: "Gửi Gmail cá nhân bằng OAuth với nội dung text/HTML và nhiều file đính kèm. Dùng khi người dùng yêu cầu gửi email hoặc gửi kết quả công việc qua Gmail; không tự gửi nếu yêu cầu chỉ là soạn thảo, nghiên cứu hoặc xem trước."
---

# Gửi Gmail cá nhân bằng OAuth

## Nguyên tắc bắt buộc

- Không dùng Service Account để gửi Gmail cá nhân.
- Chỉ gửi thật khi có ý định gửi rõ ràng và xác định được người nhận.
- Không in access token, refresh token, client secret hoặc nội dung credential.
- Kiểm tra người nhận, tiêu đề, nội dung và toàn bộ attachment trước khi gửi.
- Không gửi lại tự động khi chưa biết lần trước thành công hay thất bại.
- Chỉ báo thành công khi stdout có `gmail_send=ok`.

## Môi trường và OAuth

- Python chuẩn được tính từ `RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python`.
- Thư viện bắt buộc: `requests`.
- OAuth mặc định được tính từ `RUNTIME_ROOT/.config/openclaw-google-calendar/client.json` và `token.json`.
- Token cần khả năng gửi/soạn Gmail, ví dụ `gmail.send`, `gmail.compose` hoặc `gmail.modify`.
- Token phải có refresh token để tự làm mới access token.
- Hai file OAuth phải có quyền `0600`; thư mục nên có quyền `0700`.

## Kiểm tra và cài thư viện

```bash
SKILL_DIR="$(pwd -P)"
RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT:-$(CDPATH= cd -- "$SKILL_DIR/../../../.." && pwd -P)}"
PY="$RUNTIME_ROOT/.openclaw/tools/document-venv/bin/python"
SCRIPT="$SKILL_DIR/scripts/gmail_send.py"

test -x "$PY"
test -r "$RUNTIME_ROOT/.config/openclaw-google-calendar/client.json"
test -r "$RUNTIME_ROOT/.config/openclaw-google-calendar/token.json"
"$PY" -c 'import requests'
"$PY" "$SCRIPT" --help
```

Nếu import thất bại:

```bash
"$PY" -m pip install 'requests>=2.32,<3'
"$PY" -m pip check
```

Không cần cài lại khi import và `pip check` đã đạt.

## Kiểm tra OAuth không gửi thư

```bash
"$PY" "$SCRIPT" profile
```

`profile` chỉ đọc hồ sơ Gmail và làm mới token khi cần. Nếu gặp `401/403`, dừng và kiểm tra lại OAuth/scopes; không yêu cầu mật khẩu Google, OTP hoặc mã khôi phục.

## Chuẩn bị nội dung

- Email ngắn: dùng `--body` dạng text.
- Báo cáo hoặc nội dung trình bày: dùng thêm `--html-file`, đồng thời vẫn truyền `--body` làm bản text dự phòng.
- HTML phải tự chứa, không JavaScript, không external stylesheet và không tài nguyên yêu cầu đăng nhập.
- Escape dữ liệu động trước khi chèn vào HTML.
- Kiểm tra file HTML không rỗng, không còn placeholder và không chứa dữ liệu của tác vụ cũ.

## Gửi email

```bash
"$PY" "$SCRIPT" send \
  --to "nguoinhan@example.com" \
  --subject "Kết quả công việc" \
  --body "Bản tóm tắt dạng text." \
  --html-file "./email.html" \
  --attachment "./bao_cao.xlsx"
```

Có thể lặp `--attachment` để gửi nhiều file. Bỏ `--html-file` nếu chỉ gửi text.

## Xác minh và báo cáo

- Xác nhận mọi attachment tồn tại và đọc được trước khi gọi API.
- Chỉ báo đã gửi khi script trả `gmail_send=ok`.
- Báo người nhận, tiêu đề và tên file đính kèm; không báo hoặc lưu message/token ID nếu không cần.
- Nếu script lỗi, không tự gửi lại cho đến khi xác định rõ trạng thái lần gửi trước.

## Tiêu chí hoàn tất

- Runtime và import thư viện đạt.
- OAuth refresh được và `profile` thành công.
- Email chỉ được gửi theo yêu cầu rõ.
- Kết quả gửi được xác minh bằng `gmail_send=ok`.
