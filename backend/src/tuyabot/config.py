"""Bootstrap configuration — ONLY the environment keys documented here.

Everything else lives in the database and is edited from the dashboard.
"""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_FORWARDED_ALLOW_IPS = "127.0.0.1"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    api_host: str
    api_port: int
    tz: str
    # Peers whose X-Forwarded-For is trusted (comma separated). Empty string
    # means "trust nobody", which is the right default when the API is reached
    # directly; set it to the reverse proxy's address when one sits in front.
    forwarded_allow_ips: str = DEFAULT_FORWARDED_ALLOW_IPS


def load() -> Settings:
    raw_dir = os.getenv("DATA_DIR", "").strip() or "./data"
    data_dir = Path(raw_dir).expanduser().resolve()
    return Settings(
        data_dir=data_dir,
        api_host=os.getenv("API_HOST", "127.0.0.1").strip() or "127.0.0.1",
        api_port=int(os.getenv("API_PORT", "8080") or 8080),
        tz=os.getenv("TZ", "Asia/Makassar").strip() or "Asia/Makassar",
        forwarded_allow_ips=(
            os.getenv("FORWARDED_ALLOW_IPS", DEFAULT_FORWARDED_ALLOW_IPS).strip()
            or DEFAULT_FORWARDED_ALLOW_IPS
        ),
    )
