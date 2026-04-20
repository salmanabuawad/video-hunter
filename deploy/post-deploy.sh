#!/usr/bin/env bash
# Runs on the server after files are in $APP_ROOT (default /opt/video_hunter).
# Idempotent: safe to re-run on every deploy.
set -euo pipefail
APP_ROOT="${APP_ROOT:-/opt/video_hunter}"
cd "$APP_ROOT"

# Windows→Linux hygiene: strip CRLF and restore www-data ownership after
# tar-as-root extraction (same two bugs we hit on the previous project —
# bake them into post-deploy so they never bite again).
find . -type f \( -name '*.sh' -o -name '*.service' -o -name '*.conf' \) \
  -not -path './.venv/*' -not -path './frontend/node_modules/*' \
  -print0 | xargs -0 -r sed -i 's/\r$//'
sudo chown -R www-data:www-data "$APP_ROOT"

if [[ ! -f .venv/bin/activate ]]; then
  python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r backend/requirements.txt

if [[ -f frontend/package.json ]] && command -v npm >/dev/null 2>&1; then
  echo "Building frontend…"
  (cd frontend && npm install && npm run build)
elif [[ ! -f frontend/dist/index.html ]]; then
  echo "WARNING: frontend/dist missing and npm not found — install Node.js on the server."
fi

sudo mkdir -p data/downloads data/thumbs
sudo chown -R www-data:www-data data

if [[ -f /etc/systemd/system/video-hunter.service ]]; then
  sudo systemctl daemon-reload
  sudo systemctl restart video-hunter.service
  sudo systemctl status video-hunter.service --no-pager || true
else
  echo "Tip: install deploy/video-hunter.service first (see deploy/README.md)."
fi

echo "Post-deploy done. Check: curl -sS http://127.0.0.1:8030/api/health"
