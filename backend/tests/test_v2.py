from datetime import date
import pytest
from sqlalchemy import select
from app.adapters.embeddings.local import UnavailableEmbedding
from app.api.v1 import router as router_module
from app.core.config import settings
from app.models import BackgroundJobRecord, ClaimStatus, FoundItem, IdentityProviderConfig, Institution, InstitutionSettings, LostReport, NotificationDelivery, ReportStatus, User
from app.services.notification_hub import send as send_notification
from app.workers import tasks
from app.services.hybrid_matching import generate_matches
from app.services.oidc import make_state, verify_state
from .conftest import TestingSession, auth
from .test_workflows import category, found_payload

pytestmark=pytest.mark.integration

def reports(client,student):
    bottle=category(client,"water-bottles")
    found=client.post("/api/v1/found-items",headers=student,json={**found_payload(bottle),"name":"Dark black college bag","description":"Computer sleeve near central library","color":"Black"}).json()
    lost=client.post("/api/v1/lost-reports",headers=student,json={"category_id":bottle,"name":"Black backpack","description":"Laptop compartment left by the library","color":"Black","location":"Central Library","date_lost":str(date.today())}).json()
    return bottle,lost,found

def test_hybrid_semantic_matching_explanation_and_no_auto_approval(client,student):
    _,lost,found=reports(client,student)
    result=client.post(f"/api/v1/matching/lost-reports/{lost['id']}/recompute",headers=student)
    assert result.status_code==200
    match=result.json()[0]
    assert match["found_item_id"]==found["id"] and match["semantic_score"]>0
    assert match["confidence"] in ("LOW","MEDIUM","HIGH") and match["explanation"].startswith("Suggested because")
    assert client.get("/api/v1/claims/me",headers=student).json()==[]

def test_closed_and_cross_category_candidates_are_excluded(client,student):
    bottle,lost,found=reports(client,student);electronics=category(client,"electronics")
    client.post("/api/v1/found-items",headers=student,json=found_payload(electronics,"Mobile phone"))
    with TestingSession() as db:
        db.get(FoundItem,found["id"]).status=ReportStatus.CLOSED;db.commit()
    result=client.post(f"/api/v1/matching/lost-reports/{lost['id']}/recompute",headers=student).json()
    assert result==[]

def test_embedding_provider_failure_uses_deterministic_fallback(client,student):
    _,lost,_=reports(client,student)
    with TestingSession() as db:
        rows=generate_matches(db,db.get(LostReport,lost["id"]),router_module.storage,text_provider=UnavailableEmbedding());db.commit()
        assert rows and rows[0].provider=="deterministic-fallback"

def test_image_assisted_signal_is_private_and_optional(client,student):
    _,lost,found=reports(client,student);png=b"\x89PNG\r\n\x1a\n"+b"same-private-image"
    assert client.post(f"/api/v1/lost-reports/{lost['id']}/attachments",headers=student,files={"file":("lost.png",png,"image/png")}).status_code==201
    assert client.post(f"/api/v1/found-items/{found['id']}/attachments",headers=student,files={"file":("found.png",png,"image/png")}).status_code==201
    result=client.post(f"/api/v1/matching/lost-reports/{lost['id']}/recompute",headers=student).json()[0]
    assert result["image_score"]==100 and "Similar item photograph" in result["factors"]

def test_notification_preferences_suppress_configured_event(client,student):
    update=client.put("/api/v1/notifications/preferences",headers=student,json={"in_app_enabled":True,"email_enabled":True,"match_notifications":False,"claim_notifications":False,"handover_notifications":True})
    assert update.status_code==200
    _,_,found=reports(client,student)
    client.post("/api/v1/claims",headers=student,json={"found_item_id":found["id"],"ownership_details":"Hidden initials are under the base."})
    assert client.get("/api/v1/notifications/me",headers=student).json()==[]

def test_oidc_state_nonce_and_tamper_rejection():
    state,nonce=make_state("institution-1");assert verify_state(state)["nonce"]==nonce
    with pytest.raises(Exception):verify_state(state+"tampered")

def test_valid_oidc_callback_maps_only_basic_user_role(client,monkeypatch):
    with TestingSession() as db:
        inst=db.scalar(select(Institution).where(Institution.email_domain=="test.edu"));db.add(IdentityProviderConfig(institution_id=inst.id,issuer_url="https://idp.example",client_id="findora",client_secret_env="TEST_OIDC_SECRET",enabled=True));db.commit();institution_id=inst.id
    state,_=make_state(institution_id)
    monkeypatch.setattr(router_module,"exchange",lambda config,code,state:{"email":"oidc-user@test.edu","email_verified":True,"name":"OIDC User","role":"ADMIN"})
    response=client.get("/api/v1/sso/callback",params={"code":"valid-code","state":state})
    assert response.status_code==200 and response.json()["user"]["role"]=="USER"

def test_institution_admin_taxonomy_settings_and_provider_secret_guard(client):
    admin=auth(client,"admin@test.edu")
    assert client.put("/api/v1/institution/settings",headers=admin,json={"timezone":"Asia/Kolkata","matching_threshold":55,"email_enabled":False,"retention_days":365}).json()["matching_threshold"]==55
    assert client.post("/api/v1/institution/categories",headers=admin,json={"name":"Sports Equipment","icon":"package"}).status_code==201
    assert client.post("/api/v1/institution/locations",headers=admin,json={"name":"North Gate"}).status_code==201
    rejected=client.post("/api/v1/institution/providers",headers=admin,json={"provider_type":"email","provider_name":"vendor","config":{"api_key":"secret"}})
    assert rejected.status_code==422
    assert client.put("/api/v1/institution/oidc",headers=admin,json={"issuer_url":"http://unsafe.example","client_id":"findora","client_secret_env":"OIDC_SECRET","enabled":False}).status_code==422

def test_platform_admin_creates_isolated_institution_and_gets_real_metrics(client):
    platform=auth(client,"admin@test.edu")
    response=client.post("/api/v1/platform/institutions",headers=platform,json={"name":"Second College","email_domain":"second.edu","admin_name":"Second Admin","admin_email":"admin@second.edu","admin_password":"StrongPassword123!"})
    assert response.status_code==201
    metrics=client.get("/api/v1/platform/analytics",headers=platform).json()
    assert metrics["active_institutions"]==3 and metrics["total_registered_users"]>=4
    ordinary=auth(client,"officer@test.edu")
    assert client.get("/api/v1/platform/analytics",headers=ordinary).status_code==403

def test_archival_requires_completed_item_and_restores(client,student):
    _,_,found=reports(client,student);admin=auth(client,"admin@test.edu")
    rejected=client.post("/api/v1/archival/execute",headers=admin,json={"entity_type":"found_item","entity_ids":[found["id"]]})
    assert rejected.status_code==409
    with TestingSession() as db:db.get(FoundItem,found["id"]).status=ReportStatus.RECOVERED;db.commit()
    assert client.post("/api/v1/archival/execute",headers=student,json={"entity_type":"found_item","entity_ids":[found["id"]]}).status_code==403
    archived=client.post("/api/v1/archival/execute",headers=admin,json={"entity_type":"found_item","entity_ids":[found["id"]]})
    assert archived.status_code==200
    restored=client.post(f"/api/v1/archival/{archived.json()[0]['id']}/restore",headers=admin)
    assert restored.status_code==200 and restored.json()["restored_at"]
    rearchived=client.post("/api/v1/archival/execute",headers=admin,json={"entity_type":"found_item","entity_ids":[found["id"]]})
    assert rearchived.status_code==200 and rearchived.json()[0]["id"]==archived.json()[0]["id"]
    actions=[x["action"] for x in client.get("/api/v1/admin/audit-logs",headers=admin).json()]
    assert "records.archived" in actions and "record.restored" in actions

def test_advanced_analytics_exposes_category_and_monthly_activity(client,student):
    reports(client,student);admin=auth(client,"admin@test.edu")
    data=client.get("/api/v1/institution/analytics",headers=admin).json()
    assert data["category_distribution"] and data["monthly_trends"]
    assert {"lost","found","recoveries"}.issubset(data["monthly_trends"][0])

def test_other_institution_officer_cannot_review_claim(client,student):
    _,_,found=reports(client,student)
    claim=client.post("/api/v1/claims",headers=student,json={"found_item_id":found["id"],"ownership_details":"Hidden initials are underneath."}).json()
    outsider=auth(client,"user@other.edu")
    with TestingSession() as db:
        user=db.scalar(select(__import__('app.models',fromlist=['User']).User).where(__import__('app.models',fromlist=['User']).User.email=="user@other.edu"));user.role=__import__('app.models',fromlist=['Role']).Role.OFFICER;db.commit()
    assert client.patch(f"/api/v1/claims/{claim['id']}/decision",headers=outsider,json={"status":"APPROVED"}).status_code==404

def test_failed_email_delivery_is_recorded_for_retry(client,student,monkeypatch):
    previous=settings.smtp_host;settings.smtp_host="smtp.invalid"
    try:
        with TestingSession() as db:
            person=db.scalar(select(User).where(User.email=="student@test.edu"));config=db.scalar(select(InstitutionSettings).where(InstitutionSettings.institution_id==person.institution_id));config.email_enabled=True
            send_notification(db,person.institution_id,person.id,"Safe preview","No private ownership details.","claim");db.commit();job=db.scalar(select(BackgroundJobRecord).where(BackgroundJobRecord.job_type=="email.delivery"));job_id=job.id
        monkeypatch.setattr(tasks,"SessionLocal",TestingSession);monkeypatch.setattr(tasks.SMTPEmailProvider,"send",lambda *args,**kwargs:(_ for _ in ()).throw(RuntimeError("SMTP unavailable")))
        tasks.run_job(job_id)
        with TestingSession() as db:
            job=db.get(BackgroundJobRecord,job_id);delivery=db.scalar(select(NotificationDelivery))
            assert job.status=="RETRY" and delivery.status=="RETRY" and delivery.last_error=="SMTP unavailable"
    finally:settings.smtp_host=previous

def test_email_only_preference_creates_delivery_without_in_app_alert(client,student):
    previous=settings.smtp_host;settings.smtp_host="smtp.example"
    try:
        client.put("/api/v1/notifications/preferences",headers=student,json={"in_app_enabled":False,"email_enabled":True,"match_notifications":True,"claim_notifications":True,"handover_notifications":True})
        with TestingSession() as db:
            person=db.scalar(select(User).where(User.email=="student@test.edu"));config=db.scalar(select(InstitutionSettings).where(InstitutionSettings.institution_id==person.institution_id));config.email_enabled=True
            notification=send_notification(db,person.institution_id,person.id,"Email only","No private evidence.","claim");db.commit()
            assert notification and not notification.in_app_visible and db.scalar(select(NotificationDelivery))
        assert client.get("/api/v1/notifications/me",headers=student).json()==[]
    finally:settings.smtp_host=previous

def test_verification_request_and_handover_schedule_notifications(client,student):
    from datetime import datetime,timedelta,timezone
    _,_,found=reports(client,student);claim=client.post("/api/v1/claims",headers=student,json={"found_item_id":found["id"],"ownership_details":"Hidden initials underneath the base."}).json();officer=auth(client,"officer@test.edu")
    requested=client.post(f"/api/v1/claims/{claim['id']}/verification-request",headers=officer,json={"message":"Please provide the serial suffix."})
    assert requested.status_code==200 and requested.json()["verification_request"]
    client.patch(f"/api/v1/claims/{claim['id']}/decision",headers=officer,json={"status":"APPROVED"})
    scheduled=client.post(f"/api/v1/claims/{claim['id']}/handover-schedule",headers=officer,json={"scheduled_at":(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
    assert scheduled.status_code==200 and scheduled.json()["handover_scheduled_at"]
