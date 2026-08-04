# OAuth Client ID riêng + token cho Google Drive rclone

Thực hiện tài liệu này khi cần kết nối Google Drive lâu dài bằng OAuth Client riêng thay cho Client ID dùng chung của rclone.

## Mục tiêu

Tạo kết nối theo mô hình:

```text
Google Cloud Project riêng
→ Google Drive API
→ OAuth Desktop App
→ Client ID + Client Secret riêng
→ Token có refresh token
→ rclone remote giới hạn bằng root_folder_id
→ kiểm tra đọc/ghi/xóa
```

Ưu tiên tạo remote mới song song, ví dụ `gdrive_private:`, kiểm tra hoàn chỉnh rồi mới thay remote cũ. Không tự xóa hoặc ghi đè remote đang chạy.

## Thông tin đầu vào

Xác nhận trước khi làm:

- Tên remote mới, mặc định `gdrive_private`.
- Link folder Google Drive và `FOLDER_ID`.
- My Drive hay Shared Drive.
- Scope `drive` để đọc/ghi hoặc `drive.readonly` để chỉ đọc.
- Tài khoản Google sẽ OAuth; khuyến nghị tài khoản phụ chỉ được chia sẻ đúng folder cần dùng.
- Máy Windows/macOS/Linux Desktop có trình duyệt và `rclone` để chạy authorize.

Không nhận mật khẩu Google, OTP hoặc mã khôi phục.

## A. Tạo OAuth Client trên Google Cloud

### 1. Tạo project

1. Mở Google Cloud Console.
2. Chọn danh sách project → `New Project`.
3. Đặt tên dễ nhận biết, ví dụ `Rclone Google Drive`.
4. Tạo project và chọn đúng project đó trước khi làm tiếp.

### 2. Bật Google Drive API

1. Vào `APIs & Services` → `Library`.
2. Tìm `Google Drive API`.
3. Chọn đúng API và nhấn `Enable`.

Tài liệu chính thức:

```text
https://developers.google.com/workspace/drive/api/quickstart
```

### 3. Cấu hình Google Auth Platform

1. Vào `Google Auth Platform`.
2. Nếu có `Get Started`, khai báo:
   - App name.
   - User support email.
   - Developer contact email.
3. Chọn Audience:
   - Gmail cá nhân: `External`.
   - Google Workspace chỉ dùng nội bộ tổ chức: có thể chọn `Internal`.
4. Nếu app đang Testing, thêm tài khoản OAuth vào `Test users`.
5. Với automation lâu dài, chuyển app sang `In production` để tránh giới hạn token của chế độ Testing. Không tuyên bố app đã được Google xác minh nếu chưa thực hiện verification.

### 4. Chọn scope

Trong `Data Access`, chọn scope phù hợp:

```text
Đọc/ghi: https://www.googleapis.com/auth/drive
Chỉ đọc: https://www.googleapis.com/auth/drive.readonly
```

Scope trong Google Cloud phải phù hợp với `scope` cấu hình ở rclone.

### 5. Tạo OAuth Client

1. Vào `Google Auth Platform` → `Clients`.
2. Chọn `Create Client`.
3. Application type: `Desktop app`.
4. Đặt tên, ví dụ `Rclone VPS`.
5. Tạo và lấy `Client ID`, `Client Secret`.

Không chọn `Web application` cho luồng rclone Desktop/headless thông thường.

## B. Hiểu redirect URL localhost

Khi chạy authorize, rclone thường mở local callback:

```text
http://127.0.0.1:53682/
```

- `127.0.0.1` là chính máy đang chạy `rclone authorize`.
- `53682` là cổng local OAuth thường dùng bởi rclone Google Drive.
- Link đầy đủ có thể thêm `/auth?state=...`; phần `state` thay đổi mỗi phiên.
- Listener chỉ tồn tại trong lúc authorize và tự đóng sau khi hoàn tất.
- Không mở firewall, Nginx, Docker port hoặc domain cho cổng này.
- Nếu chạy authorize trên Windows thì localhost là Windows, không phải VPS.

Tài liệu chính thức:

```text
https://rclone.org/remote_setup/
https://developers.google.com/identity/protocols/oauth2/native-app
```

## C. Lưu credential an toàn trên VPS

Ưu tiên để người dùng tự nhập credential vào file local, không gửi qua chat:

```bash
SKILL_DIR="$(pwd -P)"
RUNTIME_ROOT="${OPENCLAW_RUNTIME_ROOT:-$(CDPATH= cd -- "$SKILL_DIR/../../../.." && pwd -P)}"
PRIVATE_DIR="${GOOGLE_DRIVE_PRIVATE_DIR:-$RUNTIME_ROOT/Data/private_accounts/google_drive}"
BACKUP_DIR="${OPENCLAW_BACKUP_DIR:-$RUNTIME_ROOT/_Backups/rclone}"
export PATH="$RUNTIME_ROOT/.local/bin:$PATH"
export RCLONE_CONFIG="${RCLONE_CONFIG:-$RUNTIME_ROOT/.config/rclone/rclone.conf}"

install -d -m 700 "$PRIVATE_DIR"
umask 077
nano "$PRIVATE_DIR/gdrive_oauth.env"
```

Nội dung mẫu:

```bash
GOOGLE_DRIVE_CLIENT_ID="Nhap_Gia_Tri_Cua_Ban"
GOOGLE_DRIVE_CLIENT_SECRET="Nhap_API_Cua_Ban"
GOOGLE_DRIVE_ROOT_FOLDER_ID="Nhap_Gia_Tri_Cua_Ban"
RCLONE_REMOTE_NAME="gdrive_private"
```

Khóa quyền:

```bash
chmod 600 "$PRIVATE_DIR/gdrive_oauth.env"
```

Không in file này bằng `cat`, không đưa vào Git, skill, Second Brain, changelog hoặc phản hồi.

## D. Kiểm tra và backup rclone

```bash
command -v rclone
rclone version
rclone listremotes
CONFIG_FILE="$RCLONE_CONFIG"
stat -c '%a %n' "$CONFIG_FILE"
```

Backup trước thay đổi:

```bash
mkdir -p "$BACKUP_DIR"
chmod 600 "$CONFIG_FILE"
install -m 600 "$CONFIG_FILE" \
  "$BACKUP_DIR/rclone.conf.$(date -u +%Y%m%dT%H%M%SZ).before-oauth-private.bak"
```

Nếu remote đích đã tồn tại, không tạo đè. Chọn tên mới hoặc xin xác nhận trước khi cập nhật.

## E. Tạo remote không tương tác

Đọc credential từ file quyền `600`, không ghi giá trị thật vào command mẫu:

```bash
set -a
. "$PRIVATE_DIR/gdrive_oauth.env"
set +a

rclone config create "$RCLONE_REMOTE_NAME" drive \
  client_id "$GOOGLE_DRIVE_CLIENT_ID" \
  client_secret "$GOOGLE_DRIVE_CLIENT_SECRET" \
  scope drive \
  root_folder_id "$GOOGLE_DRIVE_ROOT_FOLDER_ID" \
  config_is_local false \
  --quiet

unset GOOGLE_DRIVE_CLIENT_ID GOOGLE_DRIVE_CLIENT_SECRET
chmod 600 "$RCLONE_CONFIG"
```

Với remote chỉ đọc, dùng:

```text
scope=drive.readonly
```

Lệnh trên thường tạo remote chưa có token. Không kiểm tra Drive cho đến khi nhập token.

## F. Tạo token trên máy có browser

Tải rclone chính thức và mở PowerShell trong thư mục chứa `rclone.exe`.

Đặt credential cục bộ trên máy người dùng:

```powershell
$env:GOOGLE_DRIVE_CLIENT_ID="Nhap_Gia_Tri_Cua_Ban"
$env:GOOGLE_DRIVE_CLIENT_SECRET="Nhap_API_Cua_Ban"

.\rclone.exe authorize "drive" `
  $env:GOOGLE_DRIVE_CLIENT_ID `
  $env:GOOGLE_DRIVE_CLIENT_SECRET
```

Thực hiện:

1. Đăng nhập đúng tài khoản Google đã được chia sẻ folder.
2. Chấp nhận quyền phù hợp.
3. Chờ PowerShell in token nằm giữa hai dòng `Paste the following...` và `End paste`.
4. Không gửi mật khẩu, OTP hoặc recovery code.
5. Xóa biến môi trường sau khi hoàn tất:

```powershell
Remove-Item Env:GOOGLE_DRIVE_CLIENT_ID
Remove-Item Env:GOOGLE_DRIVE_CLIENT_SECRET
```

Tài liệu chính thức:

```text
https://rclone.org/commands/rclone_authorize/
```

## G. Chuyển token sang VPS

Phương án ưu tiên: người dùng lưu duy nhất JSON token vào file quyền `600` trên VPS:

```bash
umask 077
nano "$PRIVATE_DIR/gdrive_token.json"
chmod 600 "$PRIVATE_DIR/gdrive_token.json"
```

Không giữ hai dòng marker; file chỉ chứa JSON token.

Nếu token buộc phải gửi qua chat:

- Chỉ dùng cuộc trò chuyện riêng.
- Không lặp lại token trong phản hồi.
- Nhắc người dùng xóa tin nhắn sau cấu hình.
- Với dữ liệu nhạy cảm, thu hồi và tạo token mới sau khi credential từng lộ.

## H. Nhập token không tương tác

Không dùng `rclone config edit` trên bản cũ vì màn hình tổng kết có thể in Client Secret và token. Không dùng reconnect trong PTY có log nếu nó in authorization state chứa Client Secret.

Nhập token từ file quyền `600`:

```bash
set -a
. "$PRIVATE_DIR/gdrive_oauth.env"
set +a

TOKEN_VALUE="$(cat "$PRIVATE_DIR/gdrive_token.json")"

rclone config update "$RCLONE_REMOTE_NAME" \
  token "$TOKEN_VALUE" \
  team_drive "" \
  --non-interactive \
  --quiet

unset TOKEN_VALUE GOOGLE_DRIVE_CLIENT_ID GOOGLE_DRIVE_CLIENT_SECRET
chmod 600 "$RCLONE_CONFIG"
```

Luồng `config update ... --non-interactive` đã được kiểm tra trên rclone `1.60.1`.

Với Shared Drive, không để `team_drive=` rỗng; xác định đúng Shared Drive ID trước khi cập nhật.

## I. Kiểm tra cấu hình mà không lộ secret

Không chạy trực tiếp:

```text
rclone config show
rclone config dump
```

trong log công khai.

Kiểm tra các khóa an toàn:

```bash
CONFIG_FILE="$(rclone config file | tail -n 1)"
REMOTE_NAME="gdrive_private"

awk -F' *= *' -v section="[$REMOTE_NAME]" '
  $0==section {inside=1; print; next}
  /^\[/ {inside=0}
  inside && $1=="type" {print "type = " $2}
  inside && $1=="scope" {print "scope = " $2}
  inside && $1=="root_folder_id" {print "root_folder_id = <configured>"}
  inside && $1=="client_id" {print "client_id = <configured>"}
  inside && $1=="client_secret" {print "client_secret = <configured, redacted>"}
  inside && $1=="token" {print "token = <configured, redacted>"}
' "$CONFIG_FILE"
```

## J. Kiểm tra đọc

```bash
rclone listremotes
rclone lsf gdrive_private: --max-depth 1
rclone size gdrive_private: --json
```

Xác nhận danh sách bắt đầu tại đúng folder đã chọn.

## K. Kiểm tra ghi và xóa

Chỉ chạy khi người dùng đã yêu cầu quyền ghi:

```bash
TEST_LOCAL="$(mktemp)"
TEST_REMOTE="_rclone_private_write_test_$(date -u +%Y%m%dT%H%M%SZ).txt"
printf 'Kiem tra OAuth Client rieng - %s UTC\n' "$(date -u '+%Y-%m-%d %H:%M:%S')" > "$TEST_LOCAL"

rclone copyto "$TEST_LOCAL" "gdrive_private:$TEST_REMOTE"
rclone lsf gdrive_private: --include "$TEST_REMOTE" --files-only
rclone deletefile "gdrive_private:$TEST_REMOTE"
unlink "$TEST_LOCAL"

if rclone lsf gdrive_private: --include "$TEST_REMOTE" --files-only | rg -q .; then
  echo 'WRITE_TEST_DELETE_FAILED'
  exit 1
else
  echo 'WRITE_TEST_OK_AND_REMOVED'
fi
```

Nếu xóa thất bại, báo tên file thử còn sót; không che giấu lỗi.

## L. Chuyển từ remote cũ sang remote mới

Sau khi remote mới đạt kiểm tra:

1. Giữ remote cũ cho đến khi xác nhận các script/cron dùng remote nào.
2. Tìm tham chiếu remote cũ trong script, cron và tài liệu.
3. Backup từng file trước khi đổi.
4. Chỉ đổi sang remote mới khi người dùng xác nhận.
5. Không xóa remote cũ trong cùng lần triển khai nếu chưa có kế hoạch rollback.

## M. Lỗi thường gặp

### `redirect_uri_mismatch`

- Kiểm tra OAuth Client có loại `Desktop app`.
- Không dùng Web application ngoài yêu cầu đặc biệt.
- Không đổi localhost thành IP VPS hoặc domain.

### `127.0.0.1 refused to connect`

- Chạy lại `rclone authorize` và giữ terminal đang hoạt động.
- Link localhost chỉ sống trong phiên OAuth.
- Kiểm tra cổng `53682` có bị chương trình khác chiếm.

Windows:

```powershell
netstat -ano | findstr 53682
```

### `access_denied`

- Kiểm tra đúng tài khoản Google.
- Nếu app ở Testing, thêm tài khoản vào Test users.
- Kiểm tra người dùng đã chấp nhận scope.

### `invalid_grant`

- Token bị thu hồi, hết hiệu lực hoặc sai Client ID.
- Tạo token mới bằng đúng Client ID/Secret đang lưu ở remote.
- Không dùng token tạo từ Client ID khác.

### Token hết hạn sau khoảng 7 ngày

- Kiểm tra OAuth app còn ở Testing hay không.
- Với automation lâu dài, chuyển app sang In production theo chính sách Google hiện hành.
- Tạo lại token sau khi đổi trạng thái nếu cần.

## N. Thu hồi và xoay credential

Khi token hoặc Client Secret từng xuất hiện trong chat/log:

1. Xóa tin nhắn/log nếu có thể.
2. Thu hồi quyền ứng dụng trong Google Account → Security → Third-party connections.
3. Tạo OAuth Client mới hoặc xoay credential trong Google Cloud.
4. Backup cấu hình.
5. Cập nhật Client ID/Secret và tạo token mới.
6. Kiểm tra đọc/ghi lại.

Không tuyên bố an toàn tuyệt đối chỉ vì file config có quyền `600` nếu credential đã từng bị lộ ở nơi khác.

## O. Tiêu chí hoàn tất

- Remote mới tồn tại và remote cũ không bị ảnh hưởng.
- Client ID riêng, Client Secret và token đều hiện diện nhưng không bị in ra.
- Scope đúng yêu cầu.
- `root_folder_id` đúng folder.
- Đọc được dữ liệu cấp một.
- Nếu có quyền ghi: upload, nhìn thấy và xóa file thử thành công.
- File config và backup có quyền `600`.
- Credential/token không xuất hiện trong skill, Second Brain hoặc changelog.
- Cập nhật file do `SECOND_BRAIN_LOG` chỉ định, hoặc đường dẫn tương đối `RUNTIME_ROOT/_Second_AI_Brain/06_Nhat_Ky_Thay_Doi.md`, bằng thông tin đã che secret.
