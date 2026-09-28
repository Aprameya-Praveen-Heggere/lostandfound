from sqlalchemy.orm import Session
from app.models import Notification


class InAppNotificationProvider:
    def send(self, db: Session, institution_id: str, user_id: str, title: str, message: str) -> None:
        db.add(Notification(institution_id=institution_id, user_id=user_id, title=title, message=message))
