from datetime import datetime,timezone
from sqlalchemy import select
from app.adapters.email.smtp import SMTPEmailProvider
from app.adapters.storage.local import LocalStorage
from app.core.database import SessionLocal
from app.models import BackgroundJobRecord, InstitutionSettings, LostReport, Notification, NotificationDelivery, User
from app.services.hybrid_matching import generate_matches
from app.services.notification_hub import send as send_notification

def run_job(job_id:str)->None:
    with SessionLocal() as db:
        job=db.get(BackgroundJobRecord,job_id)
        if not job or job.status not in ("PENDING","RETRY"):return
        job.status="RUNNING";job.attempts+=1;db.commit()
        try:
            if job.job_type=="email.delivery":
                delivery=db.get(NotificationDelivery,job.payload["delivery_id"]);notification=db.get(Notification,delivery.notification_id);user=db.get(User,notification.user_id)
                SMTPEmailProvider().send(user.email,notification.title,notification.message)
                delivery.status="DELIVERED";delivery.delivered_at=datetime.now(timezone.utc)
            elif job.job_type=="matching.generate":
                lost=db.get(LostReport,job.payload["lost_report_id"]);results=generate_matches(db,lost,LocalStorage())
                config=db.query(InstitutionSettings).filter_by(institution_id=lost.institution_id).first();threshold=config.matching_threshold if config else 35
                if any(x.total_score>=threshold for x in results):send_notification(db,lost.institution_id,lost.user_id,"New possible match",f"Findora found {sum(x.total_score>=threshold for x in results)} possible match(es) for {lost.name}.","possible_match")
            job.status="COMPLETED";job.completed_at=datetime.now(timezone.utc);db.commit()
        except Exception as exc:
            from datetime import timedelta
            job.last_error=str(exc)[:1000];job.status="RETRY" if job.attempts<job.max_attempts else "FAILED";job.run_after=datetime.now(timezone.utc)+timedelta(seconds=2**job.attempts*10)
            if job.job_type=="email.delivery":
                delivery=db.get(NotificationDelivery,job.payload["delivery_id"]);delivery.status=job.status;delivery.attempts=job.attempts;delivery.last_error=job.last_error
            db.commit()
