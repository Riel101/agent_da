#!/usr/bin/env bash
#
# Start the API, the Vite dev server and a local SMTP catcher together.
#
#   npm run dev:all            # from apps/web
#
# Ctrl-C stops all of them. Override anything with the environment, e.g.
#   API_PORT=9000 SCHEDULER_ENABLED=false npm run dev:all
#   MAIL_CATCHER=false npm run dev:all     # no catcher; reminders are logged only
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$WEB_DIR/../.." && pwd)"
API_DIR="$ROOT/apps/api"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///$ROOT/agent_da.db}"
AGENT_AUTOSTART="${AGENT_AUTOSTART:-true}"
SCHEDULER_ENABLED="${SCHEDULER_ENABLED:-true}"
# A local SMTP catcher, so reminders really do get delivered somewhere in dev
# instead of only being logged. Set MAIL_CATCHER=false to turn it off.
MAIL_CATCHER="${MAIL_CATCHER:-true}"
MAIL_PORT="${MAIL_PORT:-1025}"
MAIL_DIR="${MAIL_DIR:-${TMPDIR:-/tmp}/agentda-mail}"

# The API deps live in apps/api/.pylibs; prefer a venv that actually has them.
DEV_PYTHON="${DEV_PYTHON:-python3}"
for candidate in "$API_DIR/.venv/bin/python" "$ROOT/.venv/bin/python"; do
  if [[ -x "$candidate" ]] && "$candidate" -c 'import uvicorn' >/dev/null 2>&1; then
    DEV_PYTHON="$candidate"
    break
  fi
done

api_pid=""
mail_pid=""

kill_tree() {
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

cleanup() {
  if [[ -n "$mail_pid" ]] && kill -0 "$mail_pid" 2>/dev/null; then
    kill_tree "$mail_pid"
    wait "$mail_pid" 2>/dev/null || true
  fi
  if [[ -n "$api_pid" ]] && kill -0 "$api_pid" 2>/dev/null; then
    kill_tree "$api_pid"
    wait "$api_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "[dev] api  -> http://$API_HOST:$API_PORT  (autostart=$AGENT_AUTOSTART scheduler=$SCHEDULER_ENABLED)"
echo "[dev] web  -> http://localhost:$WEB_PORT"
echo "[dev] db   -> $DATABASE_URL"
if [[ "$MAIL_CATCHER" == "true" ]]; then
  echo "[dev] mail -> SMTP on 127.0.0.1:$MAIL_PORT, saved under $MAIL_DIR"
fi

if [[ "$MAIL_CATCHER" == "true" ]]; then
  (
    cd "$API_DIR"
    export PYTHONPATH="$API_DIR/.pylibs${PYTHONPATH:+:$PYTHONPATH}"
    exec "$DEV_PYTHON" -m app.cli mail-catcher --port "$MAIL_PORT" --out "$MAIL_DIR"
  ) &
  mail_pid=$!
fi

(
  cd "$API_DIR"
  export PYTHONPATH="$API_DIR/.pylibs${PYTHONPATH:+:$PYTHONPATH}"
  export DATABASE_URL AGENT_AUTOSTART SCHEDULER_ENABLED
  if [[ "$MAIL_CATCHER" == "true" ]]; then
    # Keep the API pointed at the catcher even when MAIL_PORT is overridden.
    export SMTP_HOST=127.0.0.1 SMTP_PORT="$MAIL_PORT" SMTP_STARTTLS=false
    export SMTP_USER= SMTP_PASSWORD=
  fi
  exec "$DEV_PYTHON" -m uvicorn app.main:app \
    --host "$API_HOST" --port "$API_PORT" --reload --log-level info
) &
api_pid=$!

cd "$WEB_DIR"
"$WEB_DIR/node_modules/.bin/vite" --port "$WEB_PORT" --strictPort &
web_pid=$!

wait "$web_pid"
