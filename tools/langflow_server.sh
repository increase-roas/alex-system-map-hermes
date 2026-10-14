#!/bin/sh
# Starts the real Langflow app on this Mac only (127.0.0.1:7860), for the dashboard's "Open in Langflow".
# Its database and settings live in app/.data/langflow-server (git-ignored). Single local user: auto-login on,
# so the dashboard can hand flows over without storing any credential. Not reachable from the tailnet.
# Run by hand, or at login by ~/Library/LaunchAgents/com.alex.langflow-server.plist.
#
# Keys are read from 1Password (Connectors vault) at every start, with the connectors-sync service account token
# from the Keychain, and passed only to Langflow's environment. They are never written to a file or printed.
# - Langfuse tracing: item "Langfuse - Langflow" (the Langfuse project "Langflow"). Set LANGFUSE_OP_ITEM="" to turn
#   tracing off.
# - AI models: item "OpenRouter - Langflow" (capped at $100 a month in OpenRouter; Spend approval: Alex, 2026-10-14).
#   Langflow lists OPENROUTER_API_KEY as a global variable (it keeps it encrypted in its own database in
#   app/.data/langflow-server). Set OPENROUTER_OP_ITEM="" to start without it.
# If 1Password cannot be read, Langflow starts without that key and the log says so (no values).
set -e
cd "$(dirname "$0")/../app"
DATA="$PWD/.data/langflow-server"
mkdir -p "$DATA"

VAULT="r6z62bjyy3c5ipilbgs4lyakwi"
ITEM="${LANGFUSE_OP_ITEM-rxoo6lpuxbca67oj4yofie45sm}"
OR_ITEM="${OPENROUTER_OP_ITEM-daz37abakr3thickvjpfxle5ni}"
OP_TOKEN="$(/usr/bin/security find-generic-password -a connectors-sync -s op-service-account-connectors-sync -w 2>/dev/null || true)"
op_read() { [ -n "$OP_TOKEN" ] && OP_SERVICE_ACCOUNT_TOKEN="$OP_TOKEN" OP_BIOMETRIC_UNLOCK_ENABLED=false op read "op://$VAULT/$1/$2" 2>/dev/null || true; }

if [ -n "$ITEM" ]; then
  LANGFUSE_SECRET_KEY="$(op_read "$ITEM" credential)"
  LANGFUSE_PUBLIC_KEY="$(op_read "$ITEM" 'public key')"
  LANGFUSE_HOST="$(op_read "$ITEM" host)"
  if [ -n "$LANGFUSE_SECRET_KEY" ] && [ -n "$LANGFUSE_PUBLIC_KEY" ] && [ -n "$LANGFUSE_HOST" ]; then
    export LANGFUSE_SECRET_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_HOST
    echo "langflow_server: Langfuse tracing on (keys from 1Password item $ITEM)"
  else
    unset LANGFUSE_SECRET_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_HOST
    echo "langflow_server: Langfuse tracing off (could not read all three fields from 1Password item $ITEM)"
  fi
fi

if [ -n "$OR_ITEM" ]; then
  OPENROUTER_API_KEY="$(op_read "$OR_ITEM" credential)"
  if [ -n "$OPENROUTER_API_KEY" ]; then
    export OPENROUTER_API_KEY OPENROUTER_APP_NAME="Alex system map Langflow"
    echo "langflow_server: OpenRouter key on (1Password item $OR_ITEM, capped in OpenRouter)"
  else
    unset OPENROUTER_API_KEY
    echo "langflow_server: OpenRouter key off (could not read 1Password item $OR_ITEM)"
  fi
fi
unset OP_TOKEN

exec env \
  LANGFLOW_CONFIG_DIR="$DATA" \
  LANGFLOW_DATABASE_URL="sqlite:///$DATA/langflow.db" \
  LANGFLOW_AUTO_LOGIN=True \
  LANGFLOW_SKIP_AUTH_AUTO_LOGIN=True \
  DO_NOT_TRACK=true \
  LANGFLOW_LOG_LEVEL=warning \
  "${LANGFLOW_BIN:-$HOME/.venvs/langflow-dashboard/bin/langflow}" run \
  --host 127.0.0.1 --port "${LANGFLOW_PORT:-7860}" --no-open-browser
