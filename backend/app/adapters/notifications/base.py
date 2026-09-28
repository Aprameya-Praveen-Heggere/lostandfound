from typing import Protocol
from sqlalchemy.orm import Session


class NotificationProvider(Protocol):
    def send(self, db: Session, institution_id: str, user_id: str, title: str, message: str) -> None: ...
