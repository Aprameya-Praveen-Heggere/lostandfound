import os
os.environ["DATABASE_URL"] = "sqlite:///./test_bootstrap.db"
os.environ["SECRET_KEY"] = "test-secret-not-for-production"
os.environ["ENVIRONMENT"] = "test"
import pytest
import secrets
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app, requests as rate_limit_buckets
from app.models import Category, Institution, InstitutionMembership, InstitutionSettings, RetentionPolicy, Role, User
import app.api.v1.router as router_module

engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

class TestStorage:
    def __init__(self, root): self.root = root
    def save(self, data: bytes, suffix: str) -> str:
        name = f"{secrets.token_hex(12)}{suffix}"
        (self.root / name).write_bytes(data)
        return name
    def path(self, stored_name: str): return self.root / stored_name.split("/")[-1]

@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    rate_limit_buckets.clear()
    monkeypatch.setattr(router_module, "storage", TestStorage(tmp_path))
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        inst = Institution(name="Test University", email_domain="test.edu")
        other = Institution(name="Other University", email_domain="other.edu")
        db.add_all([inst,other]); db.flush()
        db.add_all([Category(institution_id=inst.id,name="Water Bottles",slug="water-bottles",icon="bottle"),Category(institution_id=inst.id,name="Electronics",slug="electronics",icon="laptop")])
        people=[User(institution_id=inst.id,name="Officer",email="officer@test.edu",password_hash=hash_password("Password123!"),role=Role.OFFICER),User(institution_id=inst.id,name="Admin",email="admin@test.edu",password_hash=hash_password("Password123!"),role=Role.ADMIN,is_platform_admin=True),User(institution_id=other.id,name="Outsider",email="user@other.edu",password_hash=hash_password("Password123!"),role=Role.USER)]
        db.add_all(people);db.flush()
        db.add_all([InstitutionMembership(institution_id=p.institution_id,user_id=p.id,role=p.role) for p in people])
        db.add_all([InstitutionSettings(institution_id=inst.id),InstitutionSettings(institution_id=other.id),RetentionPolicy(institution_id=inst.id),RetentionPolicy(institution_id=other.id)])
        db.commit()
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def client():
    def override():
        db=TestingSession()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db]=override
    with TestClient(app) as result: yield result
    app.dependency_overrides.clear()

def auth(client,email,password="Password123!"):
    response=client.post("/api/v1/auth/login",json={"email":email,"password":password})
    assert response.status_code==200,response.text
    return {"Authorization":f"Bearer {response.json()['access_token']}"}

@pytest.fixture
def student(client):
    response=client.post("/api/v1/auth/register",json={"name":"Student","email":"student@test.edu","password":"Password123!"})
    assert response.status_code==201
    return {"Authorization":f"Bearer {response.json()['access_token']}"}
