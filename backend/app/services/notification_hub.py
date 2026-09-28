from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import BackgroundJobRecord, InstitutionSettings, Notification, NotificationDelivery, NotificationPreference, User

EVENT_GROUP={"possible_match":"match_notifications","claim":"claim_notifications","handover":"handover_notifications"}

def send(db:Session,institution_id:str,user_id:str,title:str,message:str,event_group:str="claim")->Notification|None:
    preference=db.scalar(select(NotificationPreference).where(NotificationPreference.user_id==user_id))
    enabled=preference is None or getattr(preference,EVENT_GROUP.get(event_group,"claim_notifications"),True)
    if not enabled:return None
    institution_settings=db.scalar(select(InstitutionSettings).where(InstitutionSettings.institution_id==institution_id))
    in_app_enabled=preference is None or preference.in_app_enabled
    email_enabled=bool(settings.smtp_host) and (institution_settings is None or institution_settings.email_enabled) and (preference is None or preference.email_enabled)
    if not in_app_enabled and not email_enabled:return None
    notification=Notification(institution_id=institution_id,user_id=user_id,title=title,message=message,in_app_visible=in_app_enabled);db.add(notification);db.flush()
    if email_enabled:
        delivery=NotificationDelivery(institution_id=institution_id,notification_id=notification.id,channel="EMAIL",provider="smtp");db.add(delivery);db.flush()
        db.add(BackgroundJobRecord(institution_id=institution_id,job_type="email.delivery",payload={"delivery_id":delivery.id}))
    return notification
