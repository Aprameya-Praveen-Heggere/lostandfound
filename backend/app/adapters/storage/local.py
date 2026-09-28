import secrets
from pathlib import Path
from app.core.config import settings


class LocalStorage:
    def __init__(self):
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
    def save(self, data: bytes, suffix: str) -> str:
        name = f"{secrets.token_urlsafe(24)}{suffix.lower()}"
        (settings.upload_dir / name).write_bytes(data)
        return name
    def path(self, stored_name: str) -> Path:
        safe = Path(stored_name).name
        return settings.upload_dir / safe
