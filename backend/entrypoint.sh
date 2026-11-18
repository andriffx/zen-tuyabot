#!/bin/sh
# Fix volume ownership, then drop privileges. SIGTERM reaches Python via exec.

set -e

UID_GID="10001:10001"

# Only DATA_DIR is writable. The app creates its own logs/ and backups/ inside
# it (see bootstrap.init), so /app/logs and /app/backup are not touched here:
# with read_only:true those chowns failed with "Read-only file system" and the
# container restarted in a loop.
DATA="${DATA_DIR:-/app/data}"
mkdir -p "$DATA"
chown -R "$UID_GID" "$DATA"
chmod 700 "$DATA"

exec setpriv --reuid=10001 --regid=10001 --init-groups \
    python -m tuyabot.main
