from datetime import date, timedelta
import pytest
from sqlalchemy import select
from app.models import Attachment, AuditLog, Claim, Notification
from .conftest import TestingSession, auth
from .test_workflows import category, found_payload

pytestmark = pytest.mark.integration

def create_found(client, headers, category_id, **overrides):
    body=found_payload(category_id); body.update(overrides)
    response=client.post("/api/v1/found-items",headers=headers,json=body)
    assert response.status_code == 201, response.text
    return response.json()

def test_duplicate_registration_login_failure_and_logout(client,student):
    duplicate=client.post("/api/v1/auth/register",json={"name":"Student Again","email":"student@test.edu","password":"Password123!"})
    assert duplicate.status_code == 409
    assert client.post("/api/v1/auth/login",json={"email":"student@test.edu","password":"WrongPassword!"}).status_code == 401
    assert client.post("/api/v1/auth/logout",headers=student).status_code == 204

def test_invalid_category_and_future_dates(client,student):
    invalid=client.post("/api/v1/lost-reports",headers=student,json={"category_id":"missing","name":"Bottle","location":"Library","date_lost":str(date.today())})
    assert invalid.status_code == 422
    bottle=category(client,"water-bottles")
    future=client.post("/api/v1/found-items",headers=student,json={**found_payload(bottle),"date_found":str(date.today()+timedelta(days=1))})
    assert future.status_code == 422

def test_lost_report_owner_update_and_non_owner_denial(client,student):
    bottle=category(client,"water-bottles")
    report=client.post("/api/v1/lost-reports",headers=student,json={"category_id":bottle,"name":"Bottle","location":"Library","date_lost":str(date.today())}).json()
    updated=client.patch(f"/api/v1/lost-reports/{report['id']}",headers=student,json={"color":"Green"})
    assert updated.status_code == 200 and updated.json()["color"] == "Green"
    outsider=auth(client,"user@other.edu")
    assert client.get(f"/api/v1/lost-reports/{report['id']}",headers=outsider).status_code == 404

def test_lost_report_status_lifecycle_controls_matching(client,student):
    bottle=category(client,"water-bottles")
    report=client.post("/api/v1/lost-reports",headers=student,json={"category_id":bottle,"name":"Bottle","location":"Library","date_lost":str(date.today())}).json()
    closed=client.patch(f"/api/v1/lost-reports/{report['id']}/status",headers=student,json={"status":"CLOSED"})
    assert closed.status_code==200 and closed.json()["status"]=="CLOSED"
    assert client.post(f"/api/v1/matching/lost-reports/{report['id']}/recompute",headers=student).status_code==409
    reopened=client.patch(f"/api/v1/lost-reports/{report['id']}/status",headers=student,json={"status":"OPEN"})
    assert reopened.status_code==200 and reopened.json()["status"]=="OPEN"
    recovered=client.patch(f"/api/v1/lost-reports/{report['id']}/status",headers=student,json={"status":"RECOVERED"})
    assert recovered.status_code==200 and recovered.json()["status"]=="RECOVERED"
    assert client.patch(f"/api/v1/lost-reports/{report['id']}/status",headers=student,json={"status":"OPEN"}).status_code==409

def test_found_item_update_requires_officer(client,student):
    bottle=category(client,"water-bottles"); item=create_found(client,student,bottle)
    assert client.patch(f"/api/v1/found-items/{item['id']}",headers=student,json={"custody":"New desk"}).status_code == 403
    officer=auth(client,"officer@test.edu")
    result=client.patch(f"/api/v1/found-items/{item['id']}",headers=officer,json={"custody":"Officer locker 2"})
    assert result.status_code == 200 and result.json()["custody"] == "Officer locker 2"

def test_search_pagination_location_and_category_boundary(client,student):
    bottle=category(client,"water-bottles"); electronics=category(client,"electronics")
    for index in range(3): create_found(client,student,bottle,name=f"Bottle {index}",location="Library")
    create_found(client,student,electronics,name="Phone",location="Library")
    first=client.get(f"/api/v1/search/found-items?category_id={bottle}&location=Library&page=1&page_size=2",headers=student).json()
    second=client.get(f"/api/v1/search/found-items?category_id={bottle}&location=Library&page=2&page_size=2",headers=student).json()
    assert first["total"] == 3 and first["pages"] == 2 and len(first["items"]) == 2
    assert len(second["items"]) == 1
    assert all(x["category_id"] == bottle for x in first["items"] + second["items"])

@pytest.mark.parametrize("filename,content_type,data,status", [
    ("photo.txt","text/plain",b"not an image",415),
    ("fake.png","image/png",b"not-png",415),
])
def test_upload_rejects_bad_type_or_signature(client,student,filename,content_type,data,status):
    bottle=category(client,"water-bottles"); item=create_found(client,student,bottle)
    response=client.post(f"/api/v1/found-items/{item['id']}/attachments",headers=student,files={"file":(filename,data,content_type)})
    assert response.status_code == status

def test_attachment_upload_and_authenticated_download(client,student):
    bottle=category(client,"water-bottles"); item=create_found(client,student,bottle)
    png=b"\x89PNG\r\n\x1a\n"+b"test-image"
    uploaded=client.post(f"/api/v1/found-items/{item['id']}/attachments",headers=student,files={"file":("item.png",png,"image/png")})
    assert uploaded.status_code == 201
    attachment_id=uploaded.json()["id"]
    assert client.get(f"/api/v1/attachments/{attachment_id}").status_code == 401
    downloaded=client.get(f"/api/v1/attachments/{attachment_id}",headers=student)
    assert downloaded.status_code == 200 and downloaded.content == png
    outsider=auth(client,"user@other.edu")
    assert client.get(f"/api/v1/attachments/{attachment_id}",headers=outsider).status_code == 404

def test_duplicate_claim_is_conflict_and_notification_is_created(client,student):
    bottle=category(client,"water-bottles"); item=create_found(client,student,bottle)
    payload={"found_item_id":item["id"],"ownership_details":"Initials AB are engraved under the bottle."}
    first=client.post("/api/v1/claims",headers=student,json=payload)
    assert first.status_code == 201
    assert client.post("/api/v1/claims",headers=student,json=payload).status_code == 409
    notes=client.get("/api/v1/notifications/me",headers=student).json()
    assert any(x["title"] == "Claim submitted" for x in notes)

def test_notification_read_is_owner_only(client,student):
    bottle=category(client,"water-bottles"); item=create_found(client,student,bottle)
    client.post("/api/v1/claims",headers=student,json={"found_item_id":item["id"],"ownership_details":"A hidden serial is under the base."})
    note=client.get("/api/v1/notifications/me",headers=student).json()[0]
    read=client.patch(f"/api/v1/notifications/{note['id']}/read",headers=student)
    assert read.status_code == 200 and read.json()["is_read"] is True
    outsider=auth(client,"user@other.edu")
    assert client.patch(f"/api/v1/notifications/{note['id']}/read",headers=outsider).status_code == 404

def test_invalid_claim_transition_and_unapproved_handover(client,student):
    bottle=category(client,"water-bottles"); item=create_found(client,student,bottle)
    claim=client.post("/api/v1/claims",headers=student,json={"found_item_id":item["id"],"ownership_details":"The base contains initials XYZ."}).json()
    officer=auth(client,"officer@test.edu")
    assert client.patch(f"/api/v1/claims/{claim['id']}/decision",headers=officer,json={"status":"HANDED_OVER"}).status_code == 422
    assert client.post("/api/v1/handovers",headers=officer,json={"claim_id":claim["id"]}).status_code == 409

def test_analytics_uses_actual_records_and_admin_isolation(client,student):
    bottle=category(client,"water-bottles"); create_found(client,student,bottle)
    client.post("/api/v1/lost-reports",headers=student,json={"category_id":bottle,"name":"Bottle","location":"Library","date_lost":str(date.today())})
    admin=auth(client,"admin@test.edu")
    result=client.get("/api/v1/admin/analytics",headers=admin)
    assert result.status_code == 200
    assert result.json()["total_found_items"] == 1 and result.json()["total_lost_reports"] == 1
    assert client.get("/api/v1/admin/analytics",headers=student).status_code == 403

def test_admin_cannot_demote_self_and_role_change_is_audited(client):
    admin=auth(client,"admin@test.edu")
    users=client.get("/api/v1/admin/users",headers=admin).json()
    administrator=next(x for x in users if x["email"] == "admin@test.edu")
    officer=next(x for x in users if x["email"] == "officer@test.edu")
    assert client.patch(f"/api/v1/admin/users/{administrator['id']}/role",headers=admin,json={"role":"USER"}).status_code == 409
    assert client.patch(f"/api/v1/admin/users/{officer['id']}/role",headers=admin,json={"role":"ADMIN"}).status_code == 200
    actions=[x["action"] for x in client.get("/api/v1/admin/audit-logs",headers=admin).json()]
    assert "user.role.updated" in actions

def test_health_ready_extensions_and_security_headers(client,student):
    health=client.get("/api/v1/health"); ready=client.get("/api/v1/ready")
    assert health.status_code == 200 and ready.status_code == 200
    assert health.headers["x-content-type-options"] == "nosniff"
    extensions=client.get("/api/v1/extensions",headers=student)
    assert extensions.status_code == 200 and extensions.json()[0]["health"]["status"] == "healthy"

def test_sensitive_auth_endpoint_is_rate_limited(client):
    for _ in range(10):
        response=client.post("/api/v1/auth/login",json={"email":"nobody@test.edu","password":"Password123!"})
        assert response.status_code == 401
    limited=client.post("/api/v1/auth/login",json={"email":"nobody@test.edu","password":"Password123!"})
    assert limited.status_code == 429
