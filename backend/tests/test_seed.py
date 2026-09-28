import pytest
from sqlalchemy import func, select

import seed
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models import Category, FoundItem, Institution, User
from .conftest import TestingSession


pytestmark = pytest.mark.integration


def test_demo_seed_is_idempotent_and_preserves_existing_user_data():
    first = seed.run(session_factory=TestingSession)
    assert first["institutions"] == 1 and first["users"] == 4

    with TestingSession() as db:
        demo = db.scalar(select(Institution).where(Institution.email_domain == "findora.edu"))
        student = db.scalar(select(User).where(User.email == "student@findora.edu"))
        assert demo and demo.is_active and student and verify_password(seed.DEMO_PASSWORD, student.password_hash)
        assert db.scalar(select(func.count()).select_from(Category).where(Category.institution_id == demo.id)) == 9
        assert db.scalar(select(func.count()).select_from(FoundItem).where(FoundItem.institution_id == demo.id)) == 3
        student.name = "Preserved Demo Name"; db.commit()

    second = seed.run(session_factory=TestingSession)
    assert sum(second.values()) == 0
    with TestingSession() as db:
        assert db.scalar(select(User).where(User.email == "student@findora.edu")).name == "Preserved Demo Name"
        student = db.scalar(select(User).where(User.email == "student@findora.edu"))
        student.password_hash = hash_password("AnExistingDifferentPassword!"); db.commit()
        preserved_hash = student.password_hash
    with pytest.raises(RuntimeError, match="different password"):
        seed.run(session_factory=TestingSession)
    with TestingSession() as db:
        assert db.scalar(select(User).where(User.email == "student@findora.edu")).password_hash == preserved_hash


def test_demo_seed_requires_explicit_production_confirmation():
    original = settings.environment
    settings.environment = "production"
    try:
        with pytest.raises(RuntimeError, match="Production demo seeding is disabled"):
            seed.run(session_factory=TestingSession)
        assert seed.run(session_factory=TestingSession, allow_production=True)["users"] == 4
    finally:
        settings.environment = original
