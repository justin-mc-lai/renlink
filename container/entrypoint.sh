#!/bin/sh
# Start the optional Obscura CDP server before the app when ENABLE_OBSCURA=1.
# Default path starts no browser process at all.
set -eu

OBSCURA_PORT="${OBSCURA_PORT:-9222}"
OBSCURA_LOG="${OBSCURA_LOG:-/tmp/obscura.log}"

if [ "${ENABLE_OBSCURA:-0}" = "1" ]; then
    if command -v obscura >/dev/null 2>&1; then
        EXTRA_ARGS=""
        if [ "${OBSCURA_ALLOW_PRIVATE_NETWORK:-0}" = "1" ]; then
            # Local evidence only: Clash fake-ip DNS resolves to 198.18.0.0/15,
            # which obscura's SSRF guard rejects. Production keeps the default.
            EXTRA_ARGS="--allow-private-network"
        fi
        # shellcheck disable=SC2086
        obscura serve --port "$OBSCURA_PORT" --host 127.0.0.1 --stealth $EXTRA_ARGS >"$OBSCURA_LOG" 2>&1 &
        OBSCURA_PID=$!
        i=0
        while [ "$i" -lt 50 ]; do
            if python -c "import socket,sys; s=socket.socket(); s.settimeout(0.2); sys.exit(0 if s.connect_ex(('127.0.0.1', int('$OBSCURA_PORT')))==0 else 1)" 2>/dev/null; then
                break
            fi
            if ! kill -0 "$OBSCURA_PID" 2>/dev/null; then
                echo "obscura exited during startup; see $OBSCURA_LOG" >&2
                break
            fi
            i=$((i + 1))
            sleep 0.1
        done
        export PLAYWRIGHT_CDP="${PLAYWRIGHT_CDP:-ws://127.0.0.1:$OBSCURA_PORT}"
        echo "obscura pid=$OBSCURA_PID cdp=$PLAYWRIGHT_CDP log=$OBSCURA_LOG"
    else
        echo "ENABLE_OBSCURA=1 but the obscura binary is missing" >&2
    fi
fi

exec "$@"
