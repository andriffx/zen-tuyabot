"""Bootstrap configuration — ONLY the four documented env keys.

Everything else lives in the database and is edited from the dashboard.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    api_host: str
    api_port: int
    tz: str


def load() -> Settings:
    raw_dir = os.getenv("DATA_DIR", "").strip() or "./data"
    data_dir = Path(raw_dir).expanduser().resolve()
    return Settings(
        data_dir=data_dir,
        api_host=os.getenv("API_HOST", "127.0.0.1").strip() or "127.0.0.1",
        api_port=int(os.getenv("API_PORT", "8080") or 8080),
        tz=os.getenv("TZ", "Asia/Makassar").strip() or "Asia/Makassar",
    )
