# ─────────────────────────────────────────────────────────────
# Tuya bot backend — multi-stage, non-root, read-only friendly.
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/opt/venv/bin:$PATH"

# curl is not installed: the healthcheck uses Python's stdlib.
RUN groupadd -g 10001 app && useradd -u 10001 -g app -m -s /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app src/ ./src/
COPY --chown=app:app entrypoint.sh ./entrypoint.sh
# Only /app/data is a mount point; the app creates logs/ and backups/ inside it.
RUN chmod +x ./entrypoint.sh && mkdir -p /app/data && chown -R app:app /app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).status==200 else 1)"

# Runs as root for a few milliseconds to fix volume ownership, then execs
# setpriv to drop to uid 10001 so SIGTERM still reaches Python.
ENTRYPOINT ["/app/entrypoint.sh"]
