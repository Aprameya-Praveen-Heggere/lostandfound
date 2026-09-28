import math
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.adapters.notifications.in_app import InAppNotificationProvider
from app.adapters.storage.local import LocalStorage
from app.api.deps import admin, current_user, officer, platform_admin
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_token, hash_password, verify_password
from app.extensions.registry import registry
from app.models import *
from app.schemas import *
from app.services.audit import record
from app.services.matching import score_item
from app.services.hybrid_matching import generate_matches
from app.services.notification_hub import send as send_notification
from app.workers.tasks import run_job
from app.services.oidc import authorization_url, exchange, verify_state

router = APIRouter()
notify = InAppNotificationProvider()
storage = LocalStorage()


def ref(prefix: str) -> str: return f"{prefix}-{secrets.token_hex(4).upper()}"
def owned(entity, user: User):
    if not entity or entity.institution_id != user.institution_id: raise HTTPException(404, "Record not found")
    return entity
def category_exists(db: Session, category_id: str, institution_id: str):
    item=db.get(Category, category_id)
    if not item or item.institution_id != institution_id or not item.is_active: raise HTTPException(422, "Unknown category")


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(func.lower(User.email) == body.email.lower())): raise HTTPException(409, "Email already registered")
    domain = body.email.rsplit("@", 1)[-1].lower()
    institution = db.scalar(select(Institution).where(func.lower(Institution.email_domain) == domain))
    if not institution or not institution.is_active: raise HTTPException(422, "Use an email address from an active registered institution")
    user = User(institution_id=institution.id, name=body.name.strip(), email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user); db.flush()
    from app.models import InstitutionMembership
    db.add(InstitutionMembership(institution_id=institution.id,user_id=user.id,role=Role.USER))
    record(db, user, "user.registered", "user", user.id); db.commit()
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash): raise HTTPException(401, "Incorrect email or password")
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@router.post("/auth/logout", status_code=204)
def logout(user: User = Depends(current_user)): return None
@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)): return user
@router.get("/categories", response_model=list[CategoryOut])
def categories(user:User=Depends(current_user),db: Session = Depends(get_db)): return db.scalars(select(Category).where(Category.institution_id==user.institution_id,Category.is_active.is_(True)).order_by(Category.name)).all()
@router.get("/locations", response_model=list[LocationOut])
def locations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.models import Location
    return db.scalars(select(Location).where(Location.institution_id == user.institution_id).order_by(Location.name)).all()


@router.post("/lost-reports", response_model=LostOut, status_code=201)
def create_lost(body: LostCreate, background:BackgroundTasks, user: User = Depends(current_user), db: Session = Depends(get_db)):
    category_exists(db, body.category_id,user.institution_id)
    item = LostReport(**body.model_dump(), reference=ref("LOST"), user_id=user.id, institution_id=user.institution_id)
    db.add(item); db.flush(); record(db, user, "item.reported", "lost_report", item.id)
    from app.models import BackgroundJobRecord
    job=BackgroundJobRecord(institution_id=user.institution_id,job_type="matching.generate",payload={"lost_report_id":item.id});db.add(job);db.commit();db.refresh(item)
    if settings.environment!="test":background.add_task(run_job,job.id)
    return item


@router.get("/lost-reports/me", response_model=list[LostOut])
def my_lost(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(LostReport).where(LostReport.user_id == user.id).order_by(LostReport.created_at.desc())).all()
@router.get("/lost-reports/{item_id}", response_model=LostOut)
def get_lost(item_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db.get(LostReport, item_id), user)
    if item.user_id != user.id and user.role == Role.USER: raise HTTPException(404, "Record not found")
    return item
@router.patch("/lost-reports/{item_id}", response_model=LostOut)
def update_lost(item_id: str, body: LostUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db.get(LostReport, item_id), user)
    if item.user_id != user.id: raise HTTPException(403, "Only the report owner may edit it")
    if item.status != ReportStatus.OPEN: raise HTTPException(409, "Only open reports can be edited")
    for key, value in body.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    record(db, user, "lost_report.updated", "lost_report", item.id, body.model_dump(exclude_unset=True)); db.commit(); return item

@router.patch("/lost-reports/{item_id}/status",response_model=LostOut)
def update_lost_status(item_id:str,body:LostStatusUpdate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=owned(db.get(LostReport,item_id),user)
    if item.user_id!=user.id:raise HTTPException(403,"Only the report owner may change its status")
    if body.status==ReportStatus.MATCHED:raise HTTPException(422,"MATCHED is managed by the matching workflow")
    if item.status==ReportStatus.RECOVERED:raise HTTPException(409,"A recovered report is final")
    allowed={ReportStatus.OPEN:{ReportStatus.CLOSED,ReportStatus.RECOVERED},ReportStatus.CLOSED:{ReportStatus.OPEN}}
    if body.status==item.status:return item
    if body.status not in allowed.get(item.status,set()):raise HTTPException(409,"Invalid report status transition")
    previous=item.status;item.status=body.status
    record(db,user,"lost_report.status.updated","lost_report",item.id,{"from":previous.value,"to":body.status.value})
    send_notification(db,user.institution_id,user.id,"Lost report status changed",f"{item.name} is now {body.status.value.lower()}.","claim")
    db.commit();return item


@router.post("/found-items", response_model=FoundOut, status_code=201)
def create_found(body: FoundCreate, background:BackgroundTasks, user: User = Depends(current_user), db: Session = Depends(get_db)):
    category_exists(db, body.category_id,user.institution_id)
    item = FoundItem(**body.model_dump(), reference=ref("FOUND"), reporter_id=user.id, institution_id=user.institution_id)
    db.add(item); db.flush(); record(db, user, "item.found", "found_item", item.id)
    jobs=[]
    for lost in db.scalars(select(LostReport).where(LostReport.institution_id==user.institution_id,LostReport.category_id==body.category_id,LostReport.status==ReportStatus.OPEN,LostReport.is_archived.is_(False))).all():
        job=BackgroundJobRecord(institution_id=user.institution_id,job_type="matching.generate",payload={"lost_report_id":lost.id});db.add(job);jobs.append(job)
    db.commit(); db.refresh(item)
    if settings.environment!="test":
        for job in jobs:background.add_task(run_job,job.id)
    return item
@router.get("/found-items", response_model=list[FoundOut])
def found_items(category_id: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(FoundItem).where(FoundItem.institution_id == user.institution_id)
    if category_id: query = query.where(FoundItem.category_id == category_id)
    return db.scalars(query.order_by(FoundItem.created_at.desc()).limit(100)).all()
@router.get("/found-items/me", response_model=list[FoundOut])
def my_found_items(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(FoundItem).where(FoundItem.reporter_id == user.id).order_by(FoundItem.created_at.desc())).all()
@router.get("/found-items/{item_id}", response_model=FoundOut)
def get_found(item_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)): return owned(db.get(FoundItem, item_id), user)
@router.patch("/found-items/{item_id}", response_model=FoundOut)
def update_found(item_id: str, body: FoundUpdate, user: User = Depends(officer), db: Session = Depends(get_db)):
    item = owned(db.get(FoundItem, item_id), user)
    for key, value in body.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    record(db, user, "found_item.updated", "found_item", item.id, body.model_dump(exclude_unset=True));send_notification(db,user.institution_id,item.reporter_id,"Item status changed",f"Custody information for {item.name} was updated.","claim"); db.commit(); return item


@router.post("/found-items/{item_id}/attachments", status_code=201)
async def upload(item_id: str, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db.get(FoundItem, item_id), user)
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if file.content_type not in allowed: raise HTTPException(415, "Only JPEG, PNG, and WebP images are accepted")
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes: raise HTTPException(413, "Image exceeds the 5 MB limit")
    signatures = {"image/jpeg": data[:3] == b"\xff\xd8\xff", "image/png": data[:8] == b"\x89PNG\r\n\x1a\n", "image/webp": data[:4] == b"RIFF" and data[8:12] == b"WEBP"}
    if not signatures[file.content_type]: raise HTTPException(415, "File contents do not match its image type")
    stored = storage.save(data, allowed[file.content_type])
    attachment = Attachment(institution_id=user.institution_id, found_item_id=item.id, stored_name=stored,
        original_name=Path(file.filename or "image").name[:255], content_type=file.content_type, size=len(data))
    db.add(attachment); db.commit(); return {"id": attachment.id, "filename": attachment.original_name}


@router.post("/lost-reports/{item_id}/attachments", status_code=201)
async def upload_lost(item_id: str, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db.get(LostReport, item_id), user)
    if item.user_id != user.id: raise HTTPException(403, "Only the report owner may attach a photo")
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if file.content_type not in allowed: raise HTTPException(415, "Only JPEG, PNG, and WebP images are accepted")
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes: raise HTTPException(413, "Image exceeds the 5 MB limit")
    signatures = {"image/jpeg": data[:3] == b"\xff\xd8\xff", "image/png": data[:8] == b"\x89PNG\r\n\x1a\n", "image/webp": data[:4] == b"RIFF" and data[8:12] == b"WEBP"}
    if not signatures[file.content_type]: raise HTTPException(415, "File contents do not match its image type")
    stored = storage.save(data, allowed[file.content_type])
    attachment = Attachment(institution_id=user.institution_id, lost_report_id=item.id, stored_name=stored,
        original_name=Path(file.filename or "image").name[:255], content_type=file.content_type, size=len(data))
    db.add(attachment); db.commit(); return {"id": attachment.id, "filename": attachment.original_name}


@router.get("/attachments/{attachment_id}")
def attachment(attachment_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db.get(Attachment, attachment_id), user); path = storage.path(item.stored_name)
    if not path.exists(): raise HTTPException(404, "File not found")
    return FileResponse(path, media_type=item.content_type, filename=item.original_name)


@router.get("/search/found-items", response_model=Page)
def search(category_id: str, q: str | None = None, color: str | None = None, location: str | None = None,
           date_lost: date | None = None, sort: str = "relevance", page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=50),
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    category_exists(db, category_id,user.institution_id)
    query = select(FoundItem).where(FoundItem.institution_id == user.institution_id, FoundItem.category_id == category_id, FoundItem.status == ReportStatus.OPEN)
    if location: query = query.where(func.lower(FoundItem.location).contains(location.lower()))
    candidates = list(db.scalars(query).all())
    ranked = [(item, *score_item(item, q, color, location, date_lost)) for item in candidates]
    ranked.sort(key=(lambda x: x[0].date_found) if sort == "oldest" else (lambda x: (x[1], x[0].created_at)), reverse=sort != "oldest")
    total = len(ranked); subset = ranked[(page-1)*page_size:page*page_size]
    result = [FoundSearchOut(**FoundOut.model_validate(i).model_dump(), relevance_score=s, relevance_reasons=r) for i,s,r in subset]
    return Page(items=result, total=total, page=page, pages=max(1, math.ceil(total/page_size)))


@router.post("/claims", response_model=ClaimOut, status_code=201)
def create_claim(body: ClaimCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db.get(FoundItem, body.found_item_id), user)
    if item.status != ReportStatus.OPEN: raise HTTPException(409, "This item is no longer claimable")
    claim = Claim(institution_id=user.institution_id, claimant_id=user.id, found_item_id=item.id, ownership_details=body.ownership_details)
    db.add(claim)
    try: db.flush()
    except Exception: db.rollback(); raise HTTPException(409, "You already submitted a claim for this item")
    record(db, user, "claim.submitted", "claim", claim.id); send_notification(db, user.institution_id, user.id, "Claim submitted", f"Your claim for {item.name} is awaiting review.","claim")
    db.commit(); db.refresh(claim); return claim
@router.get("/claims/me", response_model=list[ClaimOut])
def my_claims(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Claim).where(Claim.claimant_id == user.id).order_by(Claim.created_at.desc())).all()
@router.get("/claims/pending", response_model=list[ClaimOut])
def pending_claims(user: User = Depends(officer), db: Session = Depends(get_db)):
    return db.scalars(select(Claim).where(Claim.institution_id == user.institution_id, Claim.status.in_([ClaimStatus.SUBMITTED, ClaimStatus.UNDER_REVIEW, ClaimStatus.APPROVED])).order_by(Claim.created_at)).all()
@router.get("/claims/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    claim = owned(db.get(Claim, claim_id), user)
    if claim.claimant_id != user.id and user.role == Role.USER: raise HTTPException(404, "Record not found")
    return claim
@router.patch("/claims/{claim_id}/decision", response_model=ClaimOut)
def decide(claim_id: str, body: ClaimDecision, user: User = Depends(officer), db: Session = Depends(get_db)):
    claim = owned(db.get(Claim, claim_id), user)
    if claim.status not in (ClaimStatus.SUBMITTED, ClaimStatus.UNDER_REVIEW): raise HTTPException(409, "Claim has already been decided")
    if body.status not in (ClaimStatus.UNDER_REVIEW, ClaimStatus.APPROVED, ClaimStatus.REJECTED): raise HTTPException(422, "Invalid decision status")
    if body.status == ClaimStatus.REJECTED and not (body.rejection_reason or "").strip(): raise HTTPException(422, "A rejection reason is required")
    claim.status = body.status; claim.rejection_reason = body.rejection_reason; claim.reviewed_by = user.id
    action = f"claim.{body.status.value.lower()}"; record(db, user, action, "claim", claim.id, {"status": body.status.value})
    send_notification(db, user.institution_id, claim.claimant_id, f"Claim {body.status.value.replace('_',' ').lower()}", f"Your claim for {claim.found_item.name} was updated.","claim")
    db.commit(); return claim

@router.post("/claims/{claim_id}/verification-request",response_model=ClaimOut)
def request_verification(claim_id:str,body:VerificationRequest,user:User=Depends(officer),db:Session=Depends(get_db)):
    claim=owned(db.get(Claim,claim_id),user)
    if claim.status not in (ClaimStatus.SUBMITTED,ClaimStatus.UNDER_REVIEW):raise HTTPException(409,"Claim is not under review")
    claim.status=ClaimStatus.UNDER_REVIEW;claim.verification_requested_at=datetime.now(timezone.utc);claim.verification_request=body.message;claim.reviewed_by=user.id
    record(db,user,"claim.verification.requested","claim",claim.id);send_notification(db,user.institution_id,claim.claimant_id,"Additional verification required",f"An officer requested more verification for {claim.found_item.name}. Open Findora for details.","claim");db.commit();return claim

@router.post("/claims/{claim_id}/handover-schedule",response_model=ClaimOut)
def schedule_handover(claim_id:str,body:HandoverSchedule,user:User=Depends(officer),db:Session=Depends(get_db)):
    claim=owned(db.get(Claim,claim_id),user)
    scheduled=body.scheduled_at if body.scheduled_at.tzinfo else body.scheduled_at.replace(tzinfo=timezone.utc)
    if claim.status!=ClaimStatus.APPROVED:raise HTTPException(409,"Only approved claims can schedule handover")
    if scheduled<=datetime.now(timezone.utc):raise HTTPException(422,"Handover must be scheduled in the future")
    claim.handover_scheduled_at=scheduled;record(db,user,"handover.scheduled","claim",claim.id,{"scheduled_at":scheduled.isoformat()});send_notification(db,user.institution_id,claim.claimant_id,"Handover scheduled",f"A handover for {claim.found_item.name} has been scheduled. Open Findora for the time.","handover");db.commit();return claim


@router.post("/handovers", response_model=HandoverOut, status_code=201)
def handover(body: HandoverCreate, user: User = Depends(officer), db: Session = Depends(get_db)):
    claim = owned(db.get(Claim, body.claim_id), user)
    if claim.status != ClaimStatus.APPROVED: raise HTTPException(409, "Only approved claims can be handed over")
    result = Handover(institution_id=user.institution_id, claim_id=claim.id, officer_id=user.id, notes=body.notes)
    claim.status = ClaimStatus.HANDED_OVER; claim.found_item.status = ReportStatus.RECOVERED
    db.add(result); db.flush(); record(db, user, "item.handover.completed", "handover", result.id); send_notification(db, user.institution_id, claim.claimant_id, "Handover completed", f"The handover for {claim.found_item.name} was recorded.","handover")
    db.commit(); db.refresh(result); return result
@router.get("/handovers/{handover_id}", response_model=HandoverOut)
def get_handover(handover_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)): return owned(db.get(Handover, handover_id), user)


@router.get("/notifications/me", response_model=list[NotificationOut])
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Notification).where(Notification.user_id == user.id,Notification.in_app_visible.is_(True)).order_by(Notification.created_at.desc())).all()
@router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def read_notification(notification_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db.get(Notification, notification_id), user)
    if item.user_id != user.id: raise HTTPException(404, "Notification not found")
    item.is_read = True; db.commit(); return item


@router.get("/admin/analytics")
def analytics(user: User = Depends(admin), db: Session = Depends(get_db)):
    institution = user.institution_id
    count = lambda model, *conditions: db.scalar(select(func.count()).select_from(model).where(model.institution_id == institution, *conditions)) or 0
    category_rows = db.execute(select(Category.name, func.count(FoundItem.id)).outerjoin(FoundItem, (FoundItem.category_id == Category.id) & (FoundItem.institution_id == institution)).group_by(Category.name)).all()
    return {"total_lost_reports": count(LostReport), "total_found_items": count(FoundItem), "pending_claims": count(Claim, Claim.status.in_([ClaimStatus.SUBMITTED, ClaimStatus.UNDER_REVIEW])),
            "approved_claims": count(Claim, Claim.status == ClaimStatus.APPROVED), "rejected_claims": count(Claim, Claim.status == ClaimStatus.REJECTED),
            "recovered_items": count(FoundItem, FoundItem.status == ReportStatus.RECOVERED), "unclaimed_items": count(FoundItem, FoundItem.status == ReportStatus.OPEN),
            "by_category": [{"category": name, "found_items": total} for name,total in category_rows]}
@router.get("/admin/audit-logs", response_model=list[AuditOut])
def audit_logs(user: User = Depends(admin), db: Session = Depends(get_db)):
    return db.scalars(select(AuditLog).where(AuditLog.institution_id == user.institution_id).order_by(AuditLog.created_at.desc()).limit(250)).all()
@router.get("/admin/users", response_model=list[UserOut])
def admin_users(user: User = Depends(admin), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.institution_id == user.institution_id).order_by(User.name)).all()
@router.patch("/admin/users/{user_id}/role", response_model=UserOut)
def update_user_role(user_id: str, body: RoleUpdate, actor: User = Depends(admin), db: Session = Depends(get_db)):
    target = owned(db.get(User, user_id), actor)
    if target.id == actor.id and body.role != Role.ADMIN: raise HTTPException(409, "You cannot remove your own administrator role")
    previous = target.role.value; target.role = body.role
    membership=db.scalar(select(InstitutionMembership).where(InstitutionMembership.institution_id==actor.institution_id,InstitutionMembership.user_id==target.id))
    if membership:membership.role=body.role
    record(db, actor, "user.role.updated", "user", target.id, {"from": previous, "to": body.role.value}); db.commit(); return target

# V2 intelligent matching
@router.post("/matching/lost-reports/{lost_id}/recompute",response_model=list[MatchOut])
def recompute_matches(lost_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    lost=owned(db.get(LostReport,lost_id),user)
    if lost.user_id!=user.id and user.role==Role.USER:raise HTTPException(404,"Lost report not found")
    if lost.status!=ReportStatus.OPEN or lost.is_archived:raise HTTPException(409,"Only open reports can recompute matches")
    results=generate_matches(db,lost,storage);record(db,user,"matching.recomputed","lost_report",lost.id,{"candidates":len(results)});db.commit()
    return results
@router.get("/matching/lost-reports/{lost_id}",response_model=list[MatchOut])
def get_matches(lost_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    lost=owned(db.get(LostReport,lost_id),user)
    if lost.user_id!=user.id and user.role==Role.USER:raise HTTPException(404,"Lost report not found")
    return db.scalars(select(MatchingResult).where(MatchingResult.lost_report_id==lost.id).order_by(MatchingResult.total_score.desc(),MatchingResult.found_item_id)).all()
@router.get("/matching/lost-reports/{lost_id}/status")
def matching_status(lost_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    lost=owned(db.get(LostReport,lost_id),user)
    job=db.scalar(select(BackgroundJobRecord).where(BackgroundJobRecord.job_type=="matching.generate",BackgroundJobRecord.payload["lost_report_id"].as_string()==lost.id).order_by(BackgroundJobRecord.created_at.desc()))
    return {"status":job.status if job else "NOT_REQUESTED","attempts":job.attempts if job else 0,"last_error":job.last_error if job else None}

# V2 notification preferences and delivery diagnostics
@router.get("/notifications/preferences",response_model=NotificationPreferenceOut)
def get_preferences(user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(NotificationPreference).where(NotificationPreference.user_id==user.id))
    if not row:row=NotificationPreference(institution_id=user.institution_id,user_id=user.id);db.add(row);db.commit();db.refresh(row)
    return row
@router.put("/notifications/preferences",response_model=NotificationPreferenceOut)
def update_preferences(body:NotificationPreferenceIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(NotificationPreference).where(NotificationPreference.user_id==user.id))
    if not row:row=NotificationPreference(institution_id=user.institution_id,user_id=user.id);db.add(row)
    for key,value in body.model_dump().items():setattr(row,key,value)
    record(db,user,"notification.preferences.updated","user",user.id);db.commit();return row
@router.get("/admin/notification-deliveries")
def delivery_status(page:int=Query(1,ge=1),user:User=Depends(admin),db:Session=Depends(get_db)):
    rows=db.scalars(select(NotificationDelivery).where(NotificationDelivery.institution_id==user.institution_id).order_by(NotificationDelivery.created_at.desc()).offset((page-1)*50).limit(50)).all()
    return [{"id":x.id,"channel":x.channel,"status":x.status,"attempts":x.attempts,"provider":x.provider,"last_error":x.last_error,"created_at":x.created_at} for x in rows]

# V2 institution administration
@router.get("/institution/settings",response_model=InstitutionSettingsOut)
def institution_settings(user:User=Depends(admin),db:Session=Depends(get_db)):
    row=db.scalar(select(InstitutionSettings).where(InstitutionSettings.institution_id==user.institution_id))
    if not row:row=InstitutionSettings(institution_id=user.institution_id);db.add(row);db.commit();db.refresh(row)
    return row
@router.put("/institution/settings",response_model=InstitutionSettingsOut)
def update_institution_settings(body:InstitutionSettingsIn,user:User=Depends(admin),db:Session=Depends(get_db)):
    row=db.scalar(select(InstitutionSettings).where(InstitutionSettings.institution_id==user.institution_id)) or InstitutionSettings(institution_id=user.institution_id)
    db.add(row)
    for key,value in body.model_dump().items():setattr(row,key,value)
    record(db,user,"institution.settings.updated","institution",user.institution_id);db.commit();return row
@router.post("/institution/categories",response_model=CategoryOut,status_code=201)
def create_category(body:TaxonomyIn,user:User=Depends(admin),db:Session=Depends(get_db)):
    slug=(body.slug or body.name).lower().strip().replace(" ","-")
    if db.scalar(select(Category).where(Category.institution_id==user.institution_id,Category.slug==slug)):raise HTTPException(409,"Category slug already exists")
    row=Category(institution_id=user.institution_id,name=body.name,slug=slug,icon=body.icon);db.add(row);db.flush();record(db,user,"category.created","category",row.id);db.commit();return row
@router.post("/institution/locations",response_model=LocationOut,status_code=201)
def create_location(body:TaxonomyIn,user:User=Depends(admin),db:Session=Depends(get_db)):
    if db.scalar(select(Location).where(Location.institution_id==user.institution_id,func.lower(Location.name)==body.name.lower())):raise HTTPException(409,"Location already exists")
    row=Location(institution_id=user.institution_id,name=body.name);db.add(row);db.flush();record(db,user,"location.created","location",row.id);db.commit();return row
@router.patch("/institution/categories/{category_id}",response_model=CategoryOut)
def update_category(category_id:str,body:TaxonomyUpdate,user:User=Depends(admin),db:Session=Depends(get_db)):
    row=owned(db.get(Category,category_id),user)
    for key,value in body.model_dump(exclude_unset=True).items():setattr(row,key,value)
    record(db,user,"category.updated","category",row.id,body.model_dump(exclude_unset=True));db.commit();return row
@router.patch("/institution/locations/{location_id}",response_model=LocationOut)
def update_location(location_id:str,body:TaxonomyUpdate,user:User=Depends(admin),db:Session=Depends(get_db)):
    row=owned(db.get(Location,location_id),user)
    if body.name is not None:row.name=body.name
    record(db,user,"location.updated","location",row.id,body.model_dump(exclude_unset=True));db.commit();return row
@router.put("/institution/oidc",response_model=IdentityProviderOut)
def configure_oidc(body:IdentityProviderIn,user:User=Depends(admin),db:Session=Depends(get_db)):
    row=db.scalar(select(IdentityProviderConfig).where(IdentityProviderConfig.institution_id==user.institution_id)) or IdentityProviderConfig(institution_id=user.institution_id,**body.model_dump())
    if row.id:
        for key,value in body.model_dump().items():setattr(row,key,value)
    db.add(row);record(db,user,"identity_provider.configured","institution",user.institution_id,{"enabled":body.enabled});db.commit();return row
@router.get("/institution/oidc",response_model=IdentityProviderOut|None)
def get_oidc_config(user:User=Depends(admin),db:Session=Depends(get_db)):
    return db.scalar(select(IdentityProviderConfig).where(IdentityProviderConfig.institution_id==user.institution_id))

# Optional institution-specific OIDC; password authentication remains available.
@router.get("/sso/{institution_id}/login")
def sso_login(institution_id:str,db:Session=Depends(get_db)):
    config=db.scalar(select(IdentityProviderConfig).where(IdentityProviderConfig.institution_id==institution_id,IdentityProviderConfig.enabled.is_(True)))
    if not config:raise HTTPException(404,"SSO is not configured")
    try:return {"authorization_url":authorization_url(config)}
    except Exception as exc:raise HTTPException(503,"Identity provider unavailable") from exc
@router.get("/sso/callback",response_model=TokenOut)
def sso_callback(code:str,state:str,db:Session=Depends(get_db)):
    try:state_data=verify_state(state)
    except Exception as exc:raise HTTPException(400,"Invalid or expired OIDC state") from exc
    config=db.scalar(select(IdentityProviderConfig).where(IdentityProviderConfig.institution_id==state_data["institution_id"],IdentityProviderConfig.enabled.is_(True)))
    if not config:raise HTTPException(404,"SSO is not configured")
    try:claims=exchange(config,code,state)
    except Exception as exc:raise HTTPException(401,"OIDC authentication failed") from exc
    email=str(claims["email"]).lower();existing=db.scalar(select(User).where(func.lower(User.email)==email))
    if existing and existing.institution_id!=config.institution_id:raise HTTPException(409,"Account belongs to another institution")
    if not existing:
        existing=User(institution_id=config.institution_id,name=claims.get("name") or email.split("@")[0],email=email,password_hash=hash_password(secrets.token_urlsafe(32)),role=Role.USER)
        db.add(existing);db.flush();db.add(InstitutionMembership(institution_id=config.institution_id,user_id=existing.id,role=Role.USER));record(db,existing,"user.sso_linked","user",existing.id)
    db.commit();return TokenOut(access_token=create_token(existing.id),user=UserOut.model_validate(existing))

# V2 analytics
@router.get("/institution/analytics")
def institution_analytics(date_from:date|None=None,date_to:date|None=None,user:User=Depends(admin),db:Session=Depends(get_db)):
    start=datetime.combine(date_from,datetime.min.time(),tzinfo=timezone.utc) if date_from else None;end=datetime.combine(date_to,datetime.max.time(),tzinfo=timezone.utc) if date_to else None
    def scoped(model):
        query=select(model).where(model.institution_id==user.institution_id)
        if start:query=query.where(model.created_at>=start)
        if end:query=query.where(model.created_at<=end)
        return list(db.scalars(query).all())
    lost=scoped(LostReport);found=scoped(FoundItem);claims=scoped(Claim);handovers=scoped(Handover)
    recovery_days=[max(0,(x.handed_over_at-next(f.created_at for f in found if f.id==next(c.found_item_id for c in claims if c.id==x.claim_id))).total_seconds()/86400) for x in handovers if any(c.id==x.claim_id for c in claims) and any(f.id==next(c.found_item_id for c in claims if c.id==x.claim_id) for f in found)]
    locations={};months={};category_counts={};category_names={x.id:x.name for x in db.scalars(select(Category).where(Category.institution_id==user.institution_id)).all()}
    for item in lost:
        locations[item.location]=locations.get(item.location,0)+1;bucket=months.setdefault(item.created_at.strftime("%Y-%m"),{"lost":0,"found":0,"recoveries":0});bucket["lost"]+=1
        category_counts[item.category_id]=category_counts.get(item.category_id,0)+1
    for item in found:
        months.setdefault(item.created_at.strftime("%Y-%m"),{"lost":0,"found":0,"recoveries":0})["found"]+=1;category_counts[item.category_id]=category_counts.get(item.category_id,0)+1
    for item in handovers:months.setdefault(item.handed_over_at.strftime("%Y-%m"),{"lost":0,"found":0,"recoveries":0})["recoveries"]+=1
    return {"total_lost_reports":len(lost),"total_found_items":len(found),"successful_recoveries":len(handovers),"pending_claims":sum(c.status in (ClaimStatus.SUBMITTED,ClaimStatus.UNDER_REVIEW) for c in claims),"rejected_claims":sum(c.status==ClaimStatus.REJECTED for c in claims),"average_recovery_days":round(sum(recovery_days)/len(recovery_days),1) if recovery_days else None,"recovery_rate":round(len(handovers)/len(found)*100,1) if found else 0,"items_awaiting_collection":sum(c.status==ClaimStatus.APPROVED for c in claims),"common_loss_locations":[{"location":k,"count":v} for k,v in sorted(locations.items(),key=lambda x:-x[1])[:10]],"category_distribution":[{"category":category_names.get(k,"Unknown"),"count":v} for k,v in sorted(category_counts.items(),key=lambda x:-x[1])],"monthly_trends":[{"month":k,**v} for k,v in sorted(months.items())]}

# V2 archival
@router.get("/archival/policy",response_model=RetentionPolicyOut)
def get_retention(user:User=Depends(admin),db:Session=Depends(get_db)):
    row=db.scalar(select(RetentionPolicy).where(RetentionPolicy.institution_id==user.institution_id)) or RetentionPolicy(institution_id=user.institution_id);db.add(row);db.commit();return row
@router.put("/archival/policy",response_model=RetentionPolicyOut)
def set_retention(body:RetentionPolicyIn,user:User=Depends(admin),db:Session=Depends(get_db)):
    row=db.scalar(select(RetentionPolicy).where(RetentionPolicy.institution_id==user.institution_id)) or RetentionPolicy(institution_id=user.institution_id);db.add(row);row.retention_days=body.retention_days;row.enabled=body.enabled;record(db,user,"retention.policy.updated","institution",user.institution_id);db.commit();return row
@router.get("/archival/preview")
def archive_preview(user:User=Depends(admin),db:Session=Depends(get_db)):
    policy=db.scalar(select(RetentionPolicy).where(RetentionPolicy.institution_id==user.institution_id));days=policy.retention_days if policy else 730;cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    lost=db.scalars(select(LostReport).where(LostReport.institution_id==user.institution_id,LostReport.status.in_([ReportStatus.RECOVERED,ReportStatus.CLOSED]),LostReport.updated_at<cutoff,LostReport.is_archived.is_(False))).all()
    found=db.scalars(select(FoundItem).where(FoundItem.institution_id==user.institution_id,FoundItem.status.in_([ReportStatus.RECOVERED,ReportStatus.CLOSED]),FoundItem.updated_at<cutoff,FoundItem.is_archived.is_(False))).all()
    handovers=db.scalars(select(Handover).where(Handover.institution_id==user.institution_id,Handover.handed_over_at<cutoff,Handover.is_archived.is_(False))).all()
    return {"cutoff":cutoff,"eligible":[{"entity_type":"lost_report","id":x.id,"reference":x.reference} for x in lost]+[{"entity_type":"found_item","id":x.id,"reference":x.reference} for x in found]+[{"entity_type":"handover","id":x.id,"reference":x.claim_id} for x in handovers]}
@router.post("/archival/execute",response_model=list[ArchiveOut])
def archive_execute(body:ArchiveExecute,user:User=Depends(admin),db:Session=Depends(get_db)):
    model={"lost_report":LostReport,"found_item":FoundItem,"handover":Handover}.get(body.entity_type)
    if not model:raise HTTPException(422,"Unsupported archive entity")
    results=[]
    for entity_id in body.entity_ids:
        item=owned(db.get(model,entity_id),user)
        if model is not Handover and item.status not in (ReportStatus.RECOVERED,ReportStatus.CLOSED):raise HTTPException(409,"Only completed records can be archived")
        if item.is_archived:raise HTTPException(409,"Record is already archived")
        snapshot={c.name:str(getattr(item,c.name)) if isinstance(getattr(item,c.name),(date,datetime)) else getattr(item,c.name) for c in item.__table__.columns}
        item.is_archived=True;item.archived_at=datetime.now(timezone.utc);row=db.scalar(select(ArchiveRecord).where(ArchiveRecord.entity_type==body.entity_type,ArchiveRecord.entity_id==item.id))
        if row:
            if not row.restored_at:raise HTTPException(409,"Record is already archived")
            row.snapshot=snapshot;row.archived_by=user.id;row.restored_at=None;row.restored_by=None;row.created_at=datetime.now(timezone.utc)
        else:row=ArchiveRecord(institution_id=user.institution_id,entity_type=body.entity_type,entity_id=item.id,snapshot=snapshot,archived_by=user.id);db.add(row)
        results.append(row)
    db.flush();record(db,user,"records.archived","archive",results[0].id,{"count":len(results)});db.commit();return results
@router.post("/archival/{archive_id}/restore",response_model=ArchiveOut)
def archive_restore(archive_id:str,user:User=Depends(admin),db:Session=Depends(get_db)):
    row=owned(db.get(ArchiveRecord,archive_id),user)
    if row.restored_at:raise HTTPException(409,"Record is already restored")
    model={"lost_report":LostReport,"found_item":FoundItem,"handover":Handover}.get(row.entity_type)
    if not model:raise HTTPException(422,"Unsupported archive entity")
    item=owned(db.get(model,row.entity_id),user);item.is_archived=False;item.archived_at=None;row.restored_at=datetime.now(timezone.utc);row.restored_by=user.id;record(db,user,"record.restored",row.entity_type,row.entity_id);db.commit();return row

# Controlled provider configuration
@router.get("/institution/providers",response_model=list[ProviderConfigOut])
def provider_configs(user:User=Depends(admin),db:Session=Depends(get_db)):return db.scalars(select(ExtensionProviderConfig).where(ExtensionProviderConfig.institution_id==user.institution_id)).all()
@router.post("/institution/providers",response_model=ProviderConfigOut,status_code=201)
def configure_provider(body:ProviderConfigIn,user:User=Depends(admin),db:Session=Depends(get_db)):
    if any(x.lower() in ("password","secret","token","api_key") for x in body.config):raise HTTPException(422,"Store credentials in environment variables, not provider configuration")
    row=ExtensionProviderConfig(institution_id=user.institution_id,**body.model_dump());db.add(row);db.flush();record(db,user,"provider.configured","provider",row.id,{"type":row.provider_type,"enabled":row.enabled});db.commit();return row
@router.patch("/institution/providers/{provider_id}",response_model=ProviderConfigOut)
def update_provider(provider_id:str,body:ProviderConfigIn,user:User=Depends(admin),db:Session=Depends(get_db)):
    row=owned(db.get(ExtensionProviderConfig,provider_id),user)
    if any(x.lower() in ("password","secret","token","api_key") for x in body.config):raise HTTPException(422,"Store credentials in environment variables, not provider configuration")
    for key,value in body.model_dump().items():setattr(row,key,value)
    record(db,user,"provider.updated","provider",row.id,{"enabled":row.enabled});db.commit();return row

# Platform administration
@router.post("/platform/institutions",response_model=InstitutionOut,status_code=201)
def create_institution(body:InstitutionCreate,actor:User=Depends(platform_admin),db:Session=Depends(get_db)):
    if db.scalar(select(Institution).where(or_(func.lower(Institution.name)==body.name.lower(),func.lower(Institution.email_domain)==body.email_domain.lower()))):raise HTTPException(409,"Institution already exists")
    inst=Institution(name=body.name,email_domain=body.email_domain.lower());db.add(inst);db.flush();administrator=User(institution_id=inst.id,name=body.admin_name,email=body.admin_email.lower(),password_hash=hash_password(body.admin_password),role=Role.ADMIN);db.add(administrator);db.flush();db.add(InstitutionMembership(institution_id=inst.id,user_id=administrator.id,role=Role.ADMIN));db.add(InstitutionSettings(institution_id=inst.id));db.add(RetentionPolicy(institution_id=inst.id));record(db,actor,"institution.created","institution",inst.id);db.commit();return inst
@router.patch("/platform/institutions/{institution_id}",response_model=InstitutionOut)
def update_institution(institution_id:str,body:InstitutionUpdate,actor:User=Depends(platform_admin),db:Session=Depends(get_db)):
    inst=db.get(Institution,institution_id)
    if not inst:raise HTTPException(404,"Institution not found")
    for key,value in body.model_dump(exclude_unset=True).items():setattr(inst,key,value)
    record(db,actor,"institution.updated","institution",inst.id,body.model_dump(exclude_unset=True));db.commit();return inst
@router.patch("/platform/institutions/{institution_id}/users/{user_id}/role",response_model=UserOut)
def platform_assign_role(institution_id:str,user_id:str,body:RoleUpdate,actor:User=Depends(platform_admin),db:Session=Depends(get_db)):
    target=db.get(User,user_id)
    if not target or target.institution_id!=institution_id:raise HTTPException(404,"Institution user not found")
    previous=target.role.value;target.role=body.role;membership=db.scalar(select(InstitutionMembership).where(InstitutionMembership.institution_id==institution_id,InstitutionMembership.user_id==user_id))
    if membership:membership.role=body.role
    db.add(AuditLog(institution_id=institution_id,actor_id=actor.id,action="platform.user.role.updated",entity_type="user",entity_id=target.id,changes={"from":previous,"to":body.role.value}));db.commit();return target
@router.get("/platform/analytics")
def platform_analytics(actor:User=Depends(platform_admin),db:Session=Depends(get_db)):
    institutions=db.scalars(select(Institution)).all()
    return {"active_institutions":sum(x.is_active for x in institutions),"total_registered_users":db.scalar(select(func.count()).select_from(User)) or 0,"total_reports":(db.scalar(select(func.count()).select_from(LostReport)) or 0)+(db.scalar(select(func.count()).select_from(FoundItem)) or 0),"total_recoveries":db.scalar(select(func.count()).select_from(Handover)) or 0,"institutions":[{"id":x.id,"name":x.name,"active":x.is_active,"users":db.scalar(select(func.count()).select_from(User).where(User.institution_id==x.id)) or 0,"reports":(db.scalar(select(func.count()).select_from(LostReport).where(LostReport.institution_id==x.id)) or 0)+(db.scalar(select(func.count()).select_from(FoundItem).where(FoundItem.institution_id==x.id)) or 0),"recoveries":db.scalar(select(func.count()).select_from(Handover).where(Handover.institution_id==x.id)) or 0} for x in institutions]}
@router.get("/platform/providers/health")
def platform_provider_health(actor:User=Depends(platform_admin)):
    from app.adapters.embeddings.local import LocalImageEmbedding,LocalTextEmbedding
    from app.adapters.email.smtp import SMTPEmailProvider
    return [{"identity":x.identity,"version":x.version,"health":x.health()} for x in [LocalTextEmbedding(),LocalImageEmbedding(),SMTPEmailProvider()]]
@router.get("/extensions")
def extensions(user: User = Depends(current_user)): return registry.list()
