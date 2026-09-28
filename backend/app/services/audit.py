from sqlalchemy.orm import Session
from app.models import AuditLog, User


def record(db: Session, actor: User, action: str, entity_type: str, entity_id: str, changes: dict | None = None) -> None:
    db.add(AuditLog(institution_id=actor.institution_id, actor_id=actor.id, action=action,
                    entity_type=entity_type, entity_id=entity_id, changes=changes or {}))
