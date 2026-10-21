#!/usr/bin/env bash
#
# Start the API, the Vite dev server and a local SMTP catcher together.
#
#   npm run dev:all            # from apps/web
#   DEV_SETUP_ONLY=true npm run dev:all   # only create/repair the API venv
#
# The first run creates apps/api/.venv and installs the API requirements.
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

# The helper prefers an explicit DEV_PYTHON when it can import the API deps;
# otherwise it creates/repairs apps/api/.venv. It prints the interpreter path
# on stdout and progress on stderr.
DEV_PYTHON="$(bash "$SCRIPT_DIR/ensure-api-venv.sh")"

if [[ "${DEV_SETUP_ONLY:-}" == "true" ]]; then
  echo "[dev] API dependencies ready: $DEV_PYTHON"
  exit 0
fi

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
echo "[dev] py   -> $DEV_PYTHON"
if [[ "$MAIL_CATCHER" == "true" ]]; then
  echo "[dev] mail -> SMTP on 127.0.0.1:$MAIL_PORT, saved under $MAIL_DIR"
fi

if [[ "$MAIL_CATCHER" == "true" ]]; then
  (
    cd "$API_DIR"
    exec "$DEV_PYTHON" -m app.cli mail-catcher --port "$MAIL_PORT" --out "$MAIL_DIR"
  ) &
  mail_pid=$!
fi

(
  cd "$API_DIR"
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
