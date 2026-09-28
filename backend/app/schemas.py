from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from app.models import ClaimStatus, ReportStatus, Role


class ORM(BaseModel): model_config = ConfigDict(from_attributes=True)
class UserOut(ORM):
    id: str; name: str; email: EmailStr; role: Role; institution_id: str; is_platform_admin: bool = False
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120); email: EmailStr; password: str = Field(min_length=8, max_length=128)
class LoginIn(BaseModel): email: EmailStr; password: str
class TokenOut(BaseModel): access_token: str; token_type: str = "bearer"; user: UserOut
class RoleUpdate(BaseModel): role: Role
class CategoryOut(ORM): id: str; name: str; slug: str; icon: str
class LocationOut(ORM): id: str; name: str


class LostCreate(BaseModel):
    category_id: str; name: str = Field(min_length=2, max_length=120); description: str | None = Field(None, max_length=2000)
    color: str | None = Field(None, max_length=60); brand: str | None = Field(None, max_length=80)
    location: str = Field(min_length=2, max_length=160); date_lost: date; private_details: str | None = Field(None, max_length=2000)
    @model_validator(mode="after")
    def date_valid(self):
        if self.date_lost > date.today(): raise ValueError("Date lost cannot be in the future")
        return self
class LostUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120); description: str | None = Field(None, max_length=2000)
    color: str | None = Field(None, max_length=60); brand: str | None = Field(None, max_length=80)
    location: str | None = Field(None, min_length=2, max_length=160); date_lost: date | None = None; private_details: str | None = Field(None, max_length=2000)
class LostStatusUpdate(BaseModel): status: ReportStatus
class LostOut(ORM):
    id: str; reference: str; category_id: str; name: str; description: str | None; color: str | None; brand: str | None
    location: str; date_lost: date; status: ReportStatus; created_at: datetime; category: CategoryOut


class FoundCreate(BaseModel):
    category_id: str; name: str = Field(min_length=2, max_length=120); description: str | None = Field(None, max_length=2000)
    color: str | None = Field(None, max_length=60); brand: str | None = Field(None, max_length=80)
    location: str = Field(min_length=2, max_length=160); date_found: date; custody: str = Field(min_length=3, max_length=240)
    @model_validator(mode="after")
    def date_valid(self):
        if self.date_found > date.today(): raise ValueError("Date found cannot be in the future")
        return self
class FoundUpdate(BaseModel):
    description: str | None = Field(None, max_length=2000); custody: str | None = Field(None, min_length=3, max_length=240)
class FoundOut(ORM):
    id: str; reference: str; category_id: str; name: str; description: str | None; color: str | None; brand: str | None
    location: str; date_found: date; custody: str; status: ReportStatus; created_at: datetime; category: CategoryOut
class FoundSearchOut(FoundOut):
    relevance_score: int = 0; relevance_reasons: list[str] = []
class Page(BaseModel): items: list[FoundSearchOut]; total: int; page: int; pages: int


class ClaimCreate(BaseModel): found_item_id: str; ownership_details: str = Field(min_length=10, max_length=3000)
class ClaimDecision(BaseModel): status: ClaimStatus; rejection_reason: str | None = Field(None, max_length=1000)
class ClaimOut(ORM):
    id: str; found_item_id: str; claimant_id: str; ownership_details: str; status: ClaimStatus
    rejection_reason: str | None; created_at: datetime; found_item: FoundOut
    verification_requested_at: datetime | None = None; verification_request: str | None = None; handover_scheduled_at: datetime | None = None
class VerificationRequest(BaseModel): message:str=Field(min_length=5,max_length=1000)
class HandoverSchedule(BaseModel): scheduled_at:datetime
class HandoverCreate(BaseModel): claim_id: str; notes: str | None = Field(None, max_length=1000)
class HandoverOut(ORM): id: str; claim_id: str; officer_id: str; notes: str | None; handed_over_at: datetime
class NotificationOut(ORM): id: str; title: str; message: str; is_read: bool; created_at: datetime
class AuditOut(ORM): id: str; actor_id: str; action: str; entity_type: str; entity_id: str; changes: dict; created_at: datetime

class MatchOut(ORM):
    id: str; lost_report_id: str; found_item_id: str; structured_score: int; semantic_score: int
    image_score: int; total_score: int; confidence: str; factors: list[str]; explanation: str; provider: str
    found_item: FoundOut | None = None
class NotificationPreferenceIn(BaseModel):
    in_app_enabled: bool = True; email_enabled: bool = True; match_notifications: bool = True
    claim_notifications: bool = True; handover_notifications: bool = True
class NotificationPreferenceOut(NotificationPreferenceIn, ORM): id: str; user_id: str
class InstitutionCreate(BaseModel):
    name: str = Field(min_length=2,max_length=160); email_domain: str = Field(min_length=3,max_length=120)
    admin_name: str = Field(min_length=2,max_length=120); admin_email: EmailStr; admin_password: str = Field(min_length=12,max_length=128)
class InstitutionUpdate(BaseModel):
    name: str | None = Field(None,min_length=2,max_length=160); is_active: bool | None = None
class InstitutionOut(ORM): id: str; name: str; email_domain: str; is_active: bool; settings: dict; created_at: datetime
class InstitutionSettingsIn(BaseModel):
    timezone: str = Field("UTC",max_length=80); matching_threshold: int = Field(35,ge=0,le=100)
    email_enabled: bool = False; retention_days: int = Field(730,ge=30,le=3650)
class InstitutionSettingsOut(InstitutionSettingsIn, ORM): id: str; institution_id: str
class TaxonomyIn(BaseModel): name: str = Field(min_length=2,max_length=120); slug: str | None = Field(None,max_length=80); icon: str = Field("package",max_length=24)
class TaxonomyUpdate(BaseModel): name:str|None=Field(None,min_length=2,max_length=120);icon:str|None=Field(None,max_length=24);is_active:bool|None=None
class IdentityProviderIn(BaseModel):
    issuer_url: str = Field(max_length=500); client_id: str = Field(max_length=255); client_secret_env: str = Field(max_length=120)
    scopes: str = Field("openid email profile",max_length=300); enabled: bool = False
    @field_validator("issuer_url")
    @classmethod
    def issuer_must_be_http(cls,value:str):
        if not value.startswith(("https://","http://localhost","http://127.0.0.1")): raise ValueError("Issuer must use HTTPS (localhost HTTP is allowed for development)")
        return value.rstrip("/")
class IdentityProviderOut(ORM): id:str;institution_id:str;issuer_url:str;client_id:str;client_secret_env:str;scopes:str;enabled:bool
class RetentionPolicyIn(BaseModel): retention_days:int=Field(730,ge=30,le=3650);enabled:bool=False
class RetentionPolicyOut(RetentionPolicyIn,ORM):id:str;institution_id:str
class ArchiveExecute(BaseModel): entity_type:str;entity_ids:list[str]=Field(min_length=1,max_length=100)
class ArchiveOut(ORM):id:str;entity_type:str;entity_id:str;snapshot:dict;created_at:datetime;restored_at:datetime|None
class ProviderConfigIn(BaseModel):provider_type:str=Field(max_length=50);provider_name:str=Field(max_length=100);enabled:bool=True;config:dict={};version:str="1.0"
class ProviderConfigOut(ProviderConfigIn,ORM):id:str;institution_id:str|None
