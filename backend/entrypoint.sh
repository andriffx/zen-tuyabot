#!/bin/sh
# Fix volume ownership, then drop privileges. SIGTERM reaches Python via exec.

set -e

UID_GID="10001:10001"

# Only DATA_DIR is writable. The app creates its own logs/ and backups/ inside
# it (see bootstrap.init), so /app/logs and /app/backup are not touched here:
# with read_only:true those chowns failed with "Read-only file system" and the
# container restarted in a loop.
DATA="${DATA_DIR:-/app/data}"
mkdir -p "$DATA" || true

# Fixing ownership needs CAP_CHOWN (docker-compose grants it). If the operator
# runs the container with a stricter securityContext, or as a non-root user,
# these calls fail with EPERM. Ownership is a convenience, not a requirement:
# a bind mount keeps the permissions the operator already chose, and an empty
# named volume is created with the right owner by Docker. Warn and continue
# rather than restart-looping, which is what `set -e` produced here.
chown -R "$UID_GID" "$DATA" 2>/dev/null || \
    echo "entrypoint: cannot chown $DATA (missing CAP_CHOWN?); continuing" >&2
chmod 700 "$DATA" 2>/dev/null || \
    echo "entrypoint: cannot chmod $DATA; continuing" >&2

exec setpriv --reuid=10001 --regid=10001 --init-groups \
    python -m tuyabot.main
