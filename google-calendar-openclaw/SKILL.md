---
name: "google-calendar-openclaw"
description: "Đọc, tạo, cập nhật và xóa sự kiện Google Calendar bằng Service Account đã được chia sẻ quyền. Dùng khi người dùng giao việc liên quan lịch, lịch hẹn, nhắc lịch hoặc kiểm tra quyền Calendar; mọi thao tác ghi phải được yêu cầu rõ và đọc lại để xác minh."
---

# Google Calendar bằng Service Account

## Nguyên tắc bắt buộc

- Dùng Service Account; không dùng Gmail OAuth của skill gửi/đọc Gmail.
- Không in private key, access token, Calendar ID thật hoặc nội dung credential.
- Mặc định chỉ đọc. Chỉ tạo, sửa hoặc xóa khi người dùng yêu cầu rõ.
- Sau mọi thao tác ghi, đọc lại đúng event ID để xác minh.
- Nếu thiếu thời lượng, mặc định 60 phút và báo rõ.
- Múi giờ mặc định: `Asia/Ho_Chi_Minh`.

## Môi trường và credential

- Python chuẩn được tính từ `RUNTIME_ROOT/.openclaw/tools/google-venv/bin/python`.
- Thư viện bắt buộc: `google-auth` và `requests`.
- Credential mặc định được tính từ `RUNTIME_ROOT/.config/openclaw-google-service-account/service-account.json`.
- Calendar ID mặc định: biến `GOOGLE_CALENDAR_ID` hoặc file `calendar.env` cùng thư mục credential.
- Có thể đổi thư mục bằng `OPENCLAW_GOOGLE_SA_DIR`.
- Service Account phải được chia sẻ Calendar với quyền `writer` hoặc `owner`.
- File JSON và `calendar.env` phải có quyền `0600`; thư mục nên có quyền `0700`.

## Kiểm tra và cài thư viện

```bash
SKILL_DIR="$(pwd -P)"
RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT:-$(CDPATH= cd -- "$SKILL_DIR/../../../.." && pwd -P)}"
PY="$RUNTIME_ROOT/.openclaw/tools/google-venv/bin/python"
SCRIPT="$SKILL_DIR/scripts/calendar_api.py"

test -x "$PY"
test -r "$RUNTIME_ROOT/.config/openclaw-google-service-account/service-account.json"
test -r "$RUNTIME_ROOT/.config/openclaw-google-service-account/calendar.env"
"$PY" -c 'import google.auth, requests'
"$PY" "$SCRIPT" --help
```

Nếu import thất bại, chỉ cài phần thiếu:

```bash
"$PY" -m pip install 'google-auth>=2,<3' 'requests>=2.32,<3'
"$PY" -m pip check
```

## Kiểm tra đọc không phá hủy

```bash
"$PY" "$SCRIPT" events --days 7
```

Không dùng `discover` nếu đã có Calendar ID hợp lệ. Lệnh `calendars` có thể trả danh sách rỗng với Service Account dù Calendar ID được chia sẻ vẫn hoạt động; ưu tiên kiểm tra trực tiếp bằng `events`.

## Thao tác sự kiện

```bash
"$PY" "$SCRIPT" create \
  "Tên sự kiện" \
  "2026-08-05T09:00:00+07:00" \
  --duration 60 \
  --description "Nội dung"

"$PY" "$SCRIPT" update EVENT_ID \
  --summary "Tên mới" \
  --start "2026-08-05T10:00:00+07:00" \
  --duration 60

"$PY" "$SCRIPT" delete EVENT_ID
```

- Xác định đúng event ID trước khi sửa/xóa.
- Không tự suy đoán ngày giờ khi yêu cầu còn mơ hồ.
- `test-permissions` sẽ tạo, sửa và xóa sự kiện kiểm tra; chỉ chạy khi người dùng yêu cầu kiểm tra quyền quản trị.

## Tiêu chí hoàn tất

- Runtime và import thư viện đạt.
- Credential đúng quyền file và Calendar ID tồn tại.
- Đọc sự kiện thành công.
- Thao tác ghi, nếu có, đã đọc lại để xác minh và không để sự kiện test rác.
