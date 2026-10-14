#!/bin/sh
# Starts the real Langflow app on this Mac only (127.0.0.1:7860), for the dashboard's "Open in Langflow".
# Its database and settings live in app/.data/langflow-server (git-ignored). Single local user: auto-login on,
# so the dashboard can hand flows over without storing any credential. Not reachable from the tailnet.
# Run by hand, or at login by ~/Library/LaunchAgents/com.alex.langflow-server.plist.
set -e
cd "$(dirname "$0")/../app"
DATA="$PWD/.data/langflow-server"
mkdir -p "$DATA"
exec env \
  LANGFLOW_CONFIG_DIR="$DATA" \
  LANGFLOW_DATABASE_URL="sqlite:///$DATA/langflow.db" \
  LANGFLOW_AUTO_LOGIN=True \
  LANGFLOW_SKIP_AUTH_AUTO_LOGIN=True \
  DO_NOT_TRACK=true \
  LANGFLOW_LOG_LEVEL=warning \
  "${LANGFLOW_BIN:-$HOME/.venvs/langflow-dashboard/bin/langflow}" run \
  --host 127.0.0.1 --port "${LANGFLOW_PORT:-7860}" --no-open-browser
