from datetime import date
import pytest
from .conftest import auth

pytestmark = pytest.mark.integration

def category(client,slug): return next(x for x in client.get("/api/v1/categories",headers=auth(client,"student@test.edu")).json() if x["slug"]==slug)["id"]
def found_payload(category_id,name="Blue bottle"):
    return {"category_id":category_id,"name":name,"description":"Matte insulated bottle","color":"Blue","brand":"Milton","location":"Library","date_found":str(date.today()),"custody":"Main security desk"}

def test_authentication_and_institutional_registration(client,student):
    assert client.get("/api/v1/auth/me",headers=student).status_code==200
    assert client.post("/api/v1/auth/register",json={"name":"X User","email":"x@gmail.com","password":"Password123!"}).status_code==422
    assert client.get("/api/v1/auth/me").status_code==401

def test_reports_category_filter_and_relevance(client,student):
    bottle=category(client,"water-bottles"); electronics=category(client,"electronics")
    lost=client.post("/api/v1/lost-reports",headers=student,json={"category_id":bottle,"name":"Milton bottle","color":"Blue","location":"Library","date_lost":str(date.today()),"description":"Matte bottle"})
    assert lost.status_code==201 and lost.json()["reference"].startswith("LOST-")
    assert client.post("/api/v1/found-items",headers=student,json=found_payload(bottle)).status_code==201
    assert client.post("/api/v1/found-items",headers=student,json=found_payload(electronics,"Laptop")).status_code==201
    result=client.get(f"/api/v1/search/found-items?category_id={bottle}&q=bottle&color=Blue&location=Library",headers=student)
    assert result.status_code==200
    assert len(result.json()["items"])==1
    assert result.json()["items"][0]["category_id"]==bottle
    assert "Similar color" in result.json()["items"][0]["relevance_reasons"]

def test_claim_approval_handover_and_audit(client,student):
    bottle=category(client,"water-bottles")
    item=client.post("/api/v1/found-items",headers=student,json=found_payload(bottle)).json()
    claim=client.post("/api/v1/claims",headers=student,json={"found_item_id":item["id"],"ownership_details":"My initials are hidden under the base."})
    assert claim.status_code==201
    officer=auth(client,"officer@test.edu")
    decision=client.patch(f"/api/v1/claims/{claim.json()['id']}/decision",headers=officer,json={"status":"APPROVED"})
    assert decision.status_code==200 and decision.json()["status"]=="APPROVED"
    handover=client.post("/api/v1/handovers",headers=officer,json={"claim_id":claim.json()["id"],"notes":"ID checked"})
    assert handover.status_code==201
    assert client.get(f"/api/v1/claims/{claim.json()['id']}",headers=student).json()["status"]=="HANDED_OVER"
    admin=auth(client,"admin@test.edu")
    actions=[x["action"] for x in client.get("/api/v1/admin/audit-logs",headers=admin).json()]
    assert "claim.submitted" in actions and "item.handover.completed" in actions

def test_rejection_requires_reason_and_role(client,student):
    bottle=category(client,"water-bottles"); item=client.post("/api/v1/found-items",headers=student,json=found_payload(bottle)).json()
    claim=client.post("/api/v1/claims",headers=student,json={"found_item_id":item["id"],"ownership_details":"A hidden mark is underneath the label."}).json()
    assert client.patch(f"/api/v1/claims/{claim['id']}/decision",headers=student,json={"status":"APPROVED"}).status_code==403
    officer=auth(client,"officer@test.edu")
    assert client.patch(f"/api/v1/claims/{claim['id']}/decision",headers=officer,json={"status":"REJECTED"}).status_code==422
    rejected=client.patch(f"/api/v1/claims/{claim['id']}/decision",headers=officer,json={"status":"REJECTED","rejection_reason":"Identifying details did not match."})
    assert rejected.status_code==200 and rejected.json()["rejection_reason"]

def test_institution_isolation(client,student):
    bottle=category(client,"water-bottles"); item=client.post("/api/v1/found-items",headers=student,json=found_payload(bottle)).json()
    outsider=auth(client,"user@other.edu")
    assert client.get(f"/api/v1/found-items/{item['id']}",headers=outsider).status_code==404
    assert client.get(f"/api/v1/search/found-items?category_id={bottle}",headers=outsider).status_code==422

def test_admin_role_management_and_lost_photo(client,student):
    admin=auth(client,"admin@test.edu")
    student_user=next(x for x in client.get("/api/v1/admin/users",headers=admin).json() if x["email"]=="student@test.edu")
    changed=client.patch(f"/api/v1/admin/users/{student_user['id']}/role",headers=admin,json={"role":"OFFICER"})
    assert changed.status_code==200 and changed.json()["role"]=="OFFICER"
    bottle=category(client,"water-bottles")
    report=client.post("/api/v1/lost-reports",headers=student,json={"category_id":bottle,"name":"Bottle","location":"Library","date_lost":str(date.today())}).json()
    tiny_png=b"\x89PNG\r\n\x1a\n"+b"valid-demo-image"
    uploaded=client.post(f"/api/v1/lost-reports/{report['id']}/attachments",headers=student,files={"file":("bottle.png",tiny_png,"image/png")})
    assert uploaded.status_code==201
