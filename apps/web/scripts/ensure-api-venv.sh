#!/usr/bin/env bash
#
# Ensure apps/api/.venv can import the API dependencies.
# Prints the interpreter path on stdout; progress and errors go to stderr.
#
# Called by `npm run dev:all` and the e2e harness. An explicit DEV_PYTHON is
# preferred when it can import the deps; otherwise the repo venv is used.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$WEB_DIR/../.." && pwd)"
API_DIR="$ROOT/apps/api"
VENV="$API_DIR/.venv"
PYTHON="$VENV/bin/python"
REQUIREMENTS="$API_DIR/requirements.txt"

log() { echo "[dev] $*" >&2; }
can_import() { "$1" -c 'import uvicorn, pydantic_core' >/dev/null 2>&1; }

if [[ -n "${DEV_PYTHON:-}" ]]; then
  if can_import "$DEV_PYTHON"; then
    printf '%s\n' "$DEV_PYTHON"
    exit 0
  fi
  log "DEV_PYTHON=$DEV_PYTHON cannot import uvicorn/pydantic_core; falling back to $VENV."
fi

# Fast path: the venv already has everything.
if [[ -x "$PYTHON" ]] && can_import "$PYTHON"; then
  printf '%s\n' "$PYTHON"
  exit 0
fi

BASE_PYTHON="${BASE_PYTHON:-python3}"
if ! command -v "$BASE_PYTHON" >/dev/null 2>&1; then
  log "No '$BASE_PYTHON' on PATH. Install Python 3.11+ and retry."
  exit 1
fi

if [[ -x "$PYTHON" ]] && "$PYTHON" --version >/dev/null 2>&1; then
  log "Repairing $VENV (installing the API requirements)..."
else
  log "Creating $VENV with $("$BASE_PYTHON" --version 2>&1)..."
  if ! "$BASE_PYTHON" -m venv --clear "$VENV" >&2; then
    log "Could not create the virtualenv. On Debian/Ubuntu: sudo apt install python3-venv"
    exit 1
  fi
fi

log "Installing $REQUIREMENTS (the first run can take a minute)..."
if ! { "$PYTHON" -m pip install --upgrade pip && "$PYTHON" -m pip install -r "$REQUIREMENTS"; } >&2; then
  log "Dependency install failed. Fix the error above, then rerun: npm run dev:all"
  exit 1
fi

if ! can_import "$PYTHON"; then
  log "$PYTHON still cannot import uvicorn/pydantic_core after installing the requirements."
  log "Remove $VENV and rerun: npm run dev:all"
  exit 1
fi

printf '%s\n' "$PYTHON"
