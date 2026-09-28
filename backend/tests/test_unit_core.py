from datetime import date, timedelta
from pathlib import Path
import jwt
import pytest
from pydantic import ValidationError
from app.adapters.storage.local import LocalStorage
from app.core.config import Settings, settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.extensions.contracts import Extension
from app.extensions.registry import ExtensionRegistry
from app.models import FoundItem
from app.schemas import ClaimCreate, FoundCreate, LostCreate, RegisterIn
from app.services.matching import score_item

pytestmark = pytest.mark.unit

def candidate(**overrides):
    values = dict(name="Insulated water bottle", description="Matte blue bottle with mountain sticker",
        color="Blue", brand="Milton", location="Central Library", date_found=date(2026, 9, 20))
    values.update(overrides)
    return FoundItem(**values)

def test_password_hash_is_salted_and_verifies():
    first, second = hash_password("CorrectHorse123!"), hash_password("CorrectHorse123!")
    assert first != second
    assert verify_password("CorrectHorse123!", first)
    assert not verify_password("wrong-password", first)

def test_token_round_trip_and_tamper_rejection():
    token = create_token("user-123")
    assert decode_token(token) == "user-123"
    with pytest.raises(jwt.InvalidTokenError): decode_token(token + "tampered")

def test_matching_combines_explainable_signals():
    score, reasons = score_item(candidate(), "water bottle Milton", "blue", "Central Library", date(2026, 9, 19))
    assert score >= 50
    assert "Similar color" in reasons
    assert "Same campus location" in reasons
    assert "Found close to the date lost" in reasons

def test_matching_no_signal_has_safe_fallback():
    score, reasons = score_item(candidate(), None, None, None, None)
    assert score == 0
    assert reasons == ["Recently reported in this category"]

def test_matching_score_is_capped_at_100():
    score, _ = score_item(candidate(name="bottle", description="bottle", brand="bottle"), "bottle", "Blue", "Central Library", date(2026, 9, 20))
    assert score == 100

@pytest.mark.parametrize("schema,date_field", [(LostCreate,"date_lost"),(FoundCreate,"date_found")])
def test_report_dates_cannot_be_in_future(schema, date_field):
    values = {"category_id":"cat","name":"Bottle","location":"Library",date_field:date.today()+timedelta(days=1)}
    if schema is FoundCreate: values["custody"] = "Security desk"
    with pytest.raises(ValidationError, match="cannot be in the future"): schema(**values)

def test_claim_evidence_minimum_and_password_minimum():
    with pytest.raises(ValidationError): ClaimCreate(found_item_id="item", ownership_details="short")
    with pytest.raises(ValidationError): RegisterIn(name="A User", email="a@test.edu", password="short")

def test_extension_registry_dispatches_only_enabled_handler():
    calls=[]; registry=ExtensionRegistry()
    registry.register(Extension("enabled","1.0",handlers={"item.found":lambda payload:calls.append(payload)}))
    registry.register(Extension("disabled","1.0",handlers={"item.found":lambda payload:calls.append("bad")},enabled=False))
    registry.dispatch("item.found",{"id":"123"})
    assert calls == [{"id":"123"}]
    assert registry.list()[1]["health"]["status"] == "disabled"

def test_local_storage_generates_safe_names_and_blocks_traversal(tmp_path):
    original = settings.upload_dir; settings.upload_dir = tmp_path
    try:
        storage=LocalStorage(); name=storage.save(b"image", ".PNG")
        assert name.endswith(".png") and "/" not in name
        assert storage.path("../../"+name) == Path(tmp_path) / name
        assert storage.path(name).read_bytes() == b"image"
    finally: settings.upload_dir = original

def test_production_configuration_rejects_default_secret_and_sqlite():
    with pytest.raises(ValidationError): Settings(environment="production",secret_key="development-only-change-me",database_url="sqlite:///bad.db",_env_file=None)
