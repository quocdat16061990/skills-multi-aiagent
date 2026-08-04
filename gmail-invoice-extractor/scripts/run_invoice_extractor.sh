#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skill_dir=$(dirname "$script_dir")
runtime_root=${OPENCLAW_RUNTIME_ROOT:-$(CDPATH= cd -- "$skill_dir/../../../.." && pwd)}
python_bin=${OPENCLAW_DOCUMENT_PYTHON:-$runtime_root/.openclaw/tools/document-venv/bin/python}
google_oauth_dir=${OPENCLAW_GOOGLE_OAUTH_DIR:-$runtime_root/.config/openclaw-google-calendar}
client_json=$google_oauth_dir/client.json
token_json=$google_oauth_dir/token.json

if [ ! -x "$python_bin" ]; then
    echo "Document Python runtime is missing: $python_bin" >&2
    exit 1
fi

if [ ! -r "$client_json" ] || [ ! -r "$token_json" ]; then
    echo "Gmail OAuth credential files are missing or unreadable." >&2
    exit 1
fi

exec "$python_bin" "$script_dir/gmail_invoice_extractor.py" \
    --client-json "$client_json" \
    --token-json "$token_json" \
    "$@"
