#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skill_dir=$(dirname "$script_dir")
runtime_root=${OPENCLAW_RUNTIME_ROOT:-$HOME}
python_bin=${OPENCLAW_DOCUMENT_PYTHON:-$runtime_root/.openclaw/tools/document-venv/bin/python}
google_oauth_dir=${OPENCLAW_GOOGLE_OAUTH_DIR:-$runtime_root/.config/openclaw-google-calendar}
client_json=${OPENCLAW_GOOGLE_CLIENT_JSON:-$runtime_root/AI_Runtime/client.json}
oauth_user_json=$google_oauth_dir/oauth-user.json

if [ ! -x "$python_bin" ]; then
    python_bin=$(command -v python3 || true)
fi
if [ -z "$python_bin" ] || [ ! -x "$python_bin" ]; then
    echo "Python runtime is missing" >&2
    exit 1
fi

help_requested=false
for argument in "$@"; do
    if [ "$argument" = "--help" ] || [ "$argument" = "-h" ]; then
        help_requested=true
        break
    fi
done

if [ "$help_requested" = false ] && [ ! -r "$client_json" ]; then
    echo "Không tìm thấy hoặc không đọc được client.json dùng chung: $client_json" >&2
    exit 1
fi

if [ "$help_requested" = false ] && [ ! -r "$oauth_user_json" ]; then
    echo "Không tìm thấy hoặc không đọc được quyền OAuth người dùng: $oauth_user_json" >&2
    exit 1
fi

exec "$python_bin" "$script_dir/gmail_send.py" \
    --client-json "$client_json" \
    --oauth-user-json "$oauth_user_json" \
    "$@"
