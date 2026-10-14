#!/bin/sh
# Starts the real Langflow app on this Mac only (127.0.0.1:7860), for the dashboard's "Open in Langflow".
# Its database and settings live in app/.data/langflow-server (git-ignored). Single local user: auto-login on,
# so the dashboard can hand flows over without storing any credential. Not reachable from the tailnet.
# Run by hand, or at login by ~/Library/LaunchAgents/com.alex.langflow-server.plist.
#
# Langfuse tracing: the keys are read from the 1Password item "Langfuse - Langflow" (Connectors vault) at every
# start, with the connectors-sync service account token from the Keychain, and passed only to Langflow's
# environment. They are never written to a file or printed. If 1Password cannot be read, Langflow starts without
# tracing and the log says so (no values). Set LANGFUSE_OP_ITEM="" to turn tracing off.
set -e
cd "$(dirname "$0")/../app"
DATA="$PWD/.data/langflow-server"
mkdir -p "$DATA"

VAULT="r6z62bjyy3c5ipilbgs4lyakwi"
ITEM="${LANGFUSE_OP_ITEM-rxoo6lpuxbca67oj4yofie45sm}"
if [ -n "$ITEM" ]; then
  OP_TOKEN="$(/usr/bin/security find-generic-password -a connectors-sync -s op-service-account-connectors-sync -w 2>/dev/null || true)"
  if [ -n "$OP_TOKEN" ]; then
    op_read() { OP_SERVICE_ACCOUNT_TOKEN="$OP_TOKEN" OP_BIOMETRIC_UNLOCK_ENABLED=false op read "op://$VAULT/$ITEM/$1" 2>/dev/null || true; }
    LANGFUSE_SECRET_KEY="$(op_read credential)"
    LANGFUSE_PUBLIC_KEY="$(op_read 'public key')"
    LANGFUSE_HOST="$(op_read host)"
  fi
  unset OP_TOKEN
  if [ -n "$LANGFUSE_SECRET_KEY" ] && [ -n "$LANGFUSE_PUBLIC_KEY" ] && [ -n "$LANGFUSE_HOST" ]; then
    export LANGFUSE_SECRET_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_HOST
    echo "langflow_server: Langfuse tracing on (keys from 1Password item $ITEM)"
  else
    unset LANGFUSE_SECRET_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_HOST
    echo "langflow_server: Langfuse tracing off (could not read all three fields from 1Password item $ITEM)"
  fi
fi

exec env \
  LANGFLOW_CONFIG_DIR="$DATA" \
  LANGFLOW_DATABASE_URL="sqlite:///$DATA/langflow.db" \
  LANGFLOW_AUTO_LOGIN=True \
  LANGFLOW_SKIP_AUTH_AUTO_LOGIN=True \
  DO_NOT_TRACK=true \
  LANGFLOW_LOG_LEVEL=warning \
  "${LANGFLOW_BIN:-$HOME/.venvs/langflow-dashboard/bin/langflow}" run \
  --host 127.0.0.1 --port "${LANGFLOW_PORT:-7860}" --no-open-browser
