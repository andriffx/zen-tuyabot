#!/bin/sh
# Fix volume ownership, then drop privileges. SIGTERM reaches Python via exec.

set -e

UID_GID="10001:10001"

for dir in /app/data /app/logs /app/backup; do
    mkdir -p "$dir"
    chown -R "$UID_GID" "$dir"
done

chmod 700 /app/data

exec setpriv --reuid=10001 --regid=10001 --init-groups \
    python -m tuyabot.main
