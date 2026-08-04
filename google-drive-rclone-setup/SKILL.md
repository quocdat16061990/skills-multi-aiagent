---
name: "google-drive-rclone-setup"
description: "Cài đặt, kiểm tra, sửa và vận hành Google Drive bằng rclone với remote mặc định `gdrive:`. Dùng khi cần kết nối Drive, giới hạn thư mục gốc, liệt kê/tải lên/tải xuống/đồng bộ dữ liệu hoặc kiểm tra OAuth rclone; mặc định chỉ đọc và không dùng skill này cho Google Calendar."
---

# Google Drive bằng rclone

## Phạm vi

- Chỉ xử lý Google Drive qua `rclone`.
- Dùng skill `google-calendar-openclaw` cho Google Calendar.
- Dùng remote mặc định `gdrive:`; không tự tạo remote tên khác nếu chưa có yêu cầu.

## Nguyên tắc bắt buộc

- Không yêu cầu mật khẩu Google, OTP hoặc mã khôi phục.
- Không in OAuth token, refresh token, client secret hoặc toàn bộ `rclone.conf`.
- Không dùng `rclone config show` trên output có thể bị ghi log.
- Mặc định chỉ đọc metadata/danh sách. Chỉ ghi, xóa, di chuyển hoặc đồng bộ hai chiều khi người dùng yêu cầu rõ.
- Backup `rclone.conf` trước mọi thay đổi cấu hình.
- `root_folder_id` chỉ đổi gốc thao tác của rclone, không thu hẹp tuyệt đối OAuth scope phía Google.

## Môi trường

- Binary ưu tiên: `command -v rclone`; fallback được tính từ `RUNTIME_ROOT/.local/bin/rclone`.
- Cấu hình mặc định được tính từ `RUNTIME_ROOT/.config/rclone/rclone.conf`.
- File cấu hình phải có quyền `0600`; thư mục nên có quyền `0700`.
- Khi dùng Client ID riêng hoặc OAuth headless, đọc đầy đủ `references/oauth-client-id-rieng.md`.
- Không cần thư viện Python cho thao tác Drive cơ bản.

## Xác định binary và kiểm tra cài đặt

```bash
SKILL_DIR="$(pwd -P)"
RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT:-$(CDPATH= cd -- "$SKILL_DIR/../../../.." && pwd -P)}"
export PATH="$RUNTIME_ROOT/.local/bin:$PATH"
export RCLONE_CONFIG="${RCLONE_CONFIG:-$RUNTIME_ROOT/.config/rclone/rclone.conf}"
RCLONE="$(command -v rclone || true)"

test -n "$RCLONE"
"$RCLONE" version
"$RCLONE" listremotes
```

Nếu chưa có `rclone`, chỉ cài khi thực sự thiếu:

```bash
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y rclone
```

Nếu không có quyền root, cài binary chính thức vào `RUNTIME_ROOT/.local/bin/rclone`, đặt quyền thực thi rồi kiểm tra lại phiên bản. Không ghi đè binary đang hoạt động.

## Kiểm tra cấu hình an toàn

```bash
CONFIG_FILE="$RCLONE_CONFIG"
test -r "$CONFIG_FILE"
chmod 600 "$CONFIG_FILE"
"$RCLONE" listremotes | grep -qx 'gdrive:'
```

Chỉ đọc các trường an toàn trong section `[gdrive]`: `type`, `scope`, trạng thái có/không của `root_folder_id` và token. Khi báo token, chỉ ghi `present_redacted`; không in giá trị.

## Backup trước khi sửa remote

```bash
CONFIG_FILE="$RCLONE_CONFIG"
BACKUP_DIR="${OPENCLAW_BACKUP_DIR:-$RUNTIME_ROOT/_Backups/rclone}"
mkdir -p "$BACKUP_DIR"
install -m 600 "$CONFIG_FILE" \
  "$BACKUP_DIR/rclone.conf.$(date -u +%Y%m%dT%H%M%SZ).bak"
```

## Tạo hoặc kết nối remote

- Chạy `"$RCLONE" listremotes` trước để tránh tạo trùng `gdrive`.
- Dùng `scope=drive.readonly` nếu chỉ cần đọc.
- Dùng `scope=drive` khi người dùng xác nhận cần đọc/ghi.
- Có thể đặt `root_folder_id` để rclone bắt đầu tại một thư mục cụ thể.
- Khi nhập token qua terminal, tránh echo và log; không chép token vào tài liệu hoặc câu trả lời.

Ví dụ tạo khung remote chưa có token:

```bash
"$RCLONE" config create gdrive drive \
  scope=drive \
  root_folder_id=FOLDER_ID \
  config_is_local=false
```

Sau đó thực hiện OAuth/reconnect theo tài liệu tham chiếu. Không đưa Client Secret hoặc token thật vào lịch sử shell công khai.

## Kiểm tra đọc không phá hủy

```bash
"$RCLONE" listremotes
"$RCLONE" lsf gdrive: --max-depth 1
"$RCLONE" size gdrive: --json
```

Không in tên file/folder riêng tư nếu người dùng chỉ cần trạng thái kết nối; có thể chỉ báo số lượng.

## Thao tác ghi

- Chỉ chạy khi người dùng yêu cầu rõ.
- Với bài test quyền ghi, tạo file vô hại tên duy nhất, upload, xác minh rồi xóa ngay.
- Nếu xóa thất bại, báo chính xác đường dẫn file thử còn sót.
- Không chạy `sync`, `bisync`, `purge`, `delete` hoặc `move` nếu chưa xác nhận nguồn, đích và hướng dữ liệu.

## Tiêu chí hoàn tất

- Binary `rclone` được tìm thấy trong PATH hoặc `RUNTIME_ROOT/.local/bin`.
- Remote `gdrive:` tồn tại và đọc được.
- Cấu hình giữ quyền `0600`, token chỉ được báo ở dạng che.
- Backup tồn tại nếu có thay đổi cấu hình.
- Không có thao tác ghi/xóa ngoài phạm vi người dùng cho phép.
