import enum
import uuid
from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def uid() -> str: return str(uuid.uuid4())
def now() -> datetime: return datetime.now(timezone.utc)


class Role(str, enum.Enum): USER = "USER"; OFFICER = "OFFICER"; ADMIN = "ADMIN"
class ReportStatus(str, enum.Enum): OPEN = "OPEN"; MATCHED = "MATCHED"; RECOVERED = "RECOVERED"; CLOSED = "CLOSED"
class ClaimStatus(str, enum.Enum): SUBMITTED = "SUBMITTED"; UNDER_REVIEW = "UNDER_REVIEW"; APPROVED = "APPROVED"; REJECTED = "REJECTED"; HANDED_OVER = "HANDED_OVER"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Institution(Base, TimestampMixin):
    __tablename__ = "institutions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    email_domain: Mapped[str] = mapped_column(String(120), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.USER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class InstitutionMembership(Base, TimestampMixin):
    __tablename__ = "institution_memberships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.USER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("institution_id", "user_id"),)


class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), index=True)
    icon: Mapped[str] = mapped_column(String(24), default="package")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("institution_id", "slug"),)


class Location(Base, TimestampMixin):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("institution_id", "name"),)


class LostReport(Base, TimestampMixin):
    __tablename__ = "lost_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(60))
    brand: Mapped[str | None] = mapped_column(String(80))
    location: Mapped[str] = mapped_column(String(160))
    date_lost: Mapped[date] = mapped_column(Date)
    private_details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.OPEN, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    category: Mapped[Category] = relationship()


class FoundItem(Base, TimestampMixin):
    __tablename__ = "found_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(60))
    brand: Mapped[str | None] = mapped_column(String(80))
    location: Mapped[str] = mapped_column(String(160))
    date_found: Mapped[date] = mapped_column(Date)
    custody: Mapped[str] = mapped_column(String(240))
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.OPEN, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    category: Mapped[Category] = relationship()


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    found_item_id: Mapped[str | None] = mapped_column(ForeignKey("found_items.id", ondelete="CASCADE"), index=True)
    lost_report_id: Mapped[str | None] = mapped_column(ForeignKey("lost_reports.id", ondelete="CASCADE"), index=True)
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    claimant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    found_item_id: Mapped[str] = mapped_column(ForeignKey("found_items.id"), index=True)
    ownership_details: Mapped[str] = mapped_column(Text)
    status: Mapped[ClaimStatus] = mapped_column(Enum(ClaimStatus), default=ClaimStatus.SUBMITTED, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    verification_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_request: Mapped[str | None] = mapped_column(Text)
    handover_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    found_item: Mapped[FoundItem] = relationship()
    __table_args__ = (UniqueConstraint("claimant_id", "found_item_id"),)


class Handover(Base, TimestampMixin):
    __tablename__ = "handovers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), unique=True)
    officer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    handed_over_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    in_app_visible: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(36))
    changes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)


class ExtensionMetadata(Base, TimestampMixin):
    __tablename__ = "extension_metadata"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    extension_key: Mapped[str] = mapped_column(String(100), unique=True)
    version: Mapped[str] = mapped_column(String(30))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class InstitutionSettings(Base, TimestampMixin):
    __tablename__ = "institution_settings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC")
    matching_threshold: Mapped[int] = mapped_column(Integer, default=35)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=730)


class IdentityProviderConfig(Base, TimestampMixin):
    __tablename__ = "identity_provider_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), unique=True, index=True)
    issuer_url: Mapped[str] = mapped_column(String(500))
    client_id: Mapped[str] = mapped_column(String(255))
    client_secret_env: Mapped[str] = mapped_column(String(120))
    scopes: Mapped[str] = mapped_column(String(300), default="openid email profile")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class ItemEmbedding(Base, TimestampMixin):
    __tablename__ = "item_embeddings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    provider: Mapped[str] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    vector: Mapped[list] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "kind", "provider"), Index("ix_embedding_scope", "institution_id", "category_id", "kind"))


class MatchingResult(Base, TimestampMixin):
    __tablename__ = "matching_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    lost_report_id: Mapped[str] = mapped_column(ForeignKey("lost_reports.id", ondelete="CASCADE"), index=True)
    found_item_id: Mapped[str] = mapped_column(ForeignKey("found_items.id", ondelete="CASCADE"), index=True)
    structured_score: Mapped[int] = mapped_column(Integer, default=0)
    semantic_score: Mapped[int] = mapped_column(Integer, default=0)
    image_score: Mapped[int] = mapped_column(Integer, default=0)
    total_score: Mapped[int] = mapped_column(Integer, index=True)
    confidence: Mapped[str] = mapped_column(String(20))
    factors: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(100), default="deterministic-fallback")
    found_item: Mapped[FoundItem] = relationship()
    __table_args__ = (UniqueConstraint("lost_report_id", "found_item_id"),)


class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    match_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    claim_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    handover_notifications: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationDelivery(Base, TimestampMixin):
    __tablename__ = "notification_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    notification_id: Mapped[str] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    provider: Mapped[str] = mapped_column(String(100))
    last_error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BackgroundJobRecord(Base, TimestampMixin):
    __tablename__ = "background_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RetentionPolicy(Base, TimestampMixin):
    __tablename__ = "retention_policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), unique=True, index=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=730)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class ArchiveRecord(Base, TimestampMixin):
    __tablename__ = "archive_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    archived_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restored_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("entity_type", "entity_id"),)


class ExtensionProviderConfig(Base, TimestampMixin):
    __tablename__ = "extension_provider_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"), index=True)
    provider_type: Mapped[str] = mapped_column(String(50), index=True)
    provider_name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[str] = mapped_column(String(30), default="1.0")
    __table_args__ = (UniqueConstraint("institution_id", "provider_type", "provider_name"),)
