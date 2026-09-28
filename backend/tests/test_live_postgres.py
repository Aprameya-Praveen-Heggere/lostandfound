import os
import httpx
import pytest

pytestmark = [pytest.mark.live, pytest.mark.integration]
BASE=os.getenv("LIVE_BASE_URL")
pytestmark.append(pytest.mark.skipif(not BASE, reason="LIVE_BASE_URL is not set"))

def login(email):
    response=httpx.post(f"{BASE}/auth/login",json={"email":email,"password":"Findora123!"},timeout=10)
    assert response.status_code == 200, response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}

def test_live_health_readiness_and_seeded_database():
    assert httpx.get(f"{BASE}/health",timeout=10).json()["status"] == "healthy"
    assert httpx.get(f"{BASE}/ready",timeout=10).json()["status"] == "ready"
    categories=httpx.get(f"{BASE}/categories",headers=login("student@findora.edu"),timeout=10).json()
    assert len(categories) == 9

def test_live_role_access_and_category_isolation():
    student=login("student@findora.edu"); admin=login("admin@findora.edu")
    categories=httpx.get(f"{BASE}/categories",headers=student,timeout=10).json()
    bottle=next(x for x in categories if x["slug"] == "water-bottles")
    result=httpx.get(f"{BASE}/search/found-items",params={"category_id":bottle["id"]},headers=student,timeout=10)
    assert result.status_code == 200
    assert all(x["category_id"] == bottle["id"] for x in result.json()["items"])
    assert httpx.get(f"{BASE}/admin/analytics",headers=student,timeout=10).status_code == 403
    assert httpx.get(f"{BASE}/admin/analytics",headers=admin,timeout=10).status_code == 200

def test_live_v2_matching_and_platform_provider_health():
    student=login("student@findora.edu");admin=login("admin@findora.edu")
    lost=httpx.get(f"{BASE}/lost-reports/me",headers=student,timeout=10).json()[0]
    matches=httpx.post(f"{BASE}/matching/lost-reports/{lost['id']}/recompute",headers=student,timeout=10)
    assert matches.status_code==200
    assert all(x["found_item"]["category_id"]==lost["category_id"] for x in matches.json())
    platform=httpx.get(f"{BASE}/platform/analytics",headers=admin,timeout=10)
    health=httpx.get(f"{BASE}/platform/providers/health",headers=admin,timeout=10)
    assert platform.status_code==200 and platform.json()["active_institutions"]>=1
    assert health.status_code==200 and any(x["identity"]=="local.semantic-hash" for x in health.json())
