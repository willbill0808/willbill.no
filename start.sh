#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

VENV_DIR=".venv"
REQ_FILE="requirements.txt"
PYTHON=${PYTHON:-python3}

SERVER_FILE="willbill-main-server.py"


if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: Python executable '$PYTHON' not found. Install Python 3 or set PYTHON to a valid interpreter." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
  echo "Creating virtual environment in $VENV_DIR..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
  echo "ERROR: virtualenv activation script missing in $VENV_DIR/bin/activate." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [ ! -f "$REQ_FILE" ]; then
  echo "ERROR: $REQ_FILE not found in $(pwd)." >&2
  exit 1
fi

echo "Upgrading pip and installing requirements from $REQ_FILE..."
pip install --upgrade pip
pip install -r "$REQ_FILE"

echo "Virtual environment is ready. To re-enter it, run: source $VENV_DIR/bin/activate"

if [ ! -f "$SERVER_FILE" ]; then
  echo "ERROR: $SERVER_FILE not found in $(pwd)." >&2
  exit 1
fi

echo "Starting $SERVER_FILE..."
exec python "$SERVER_FILE"
