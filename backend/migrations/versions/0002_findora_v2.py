"""Findora V2 tenancy, matching, providers, jobs, and archival.

Revision ID: 0002_findora_v2
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from app.core.database import Base
from app.models import *

revision = "0002_findora_v2"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "institution_memberships", "institution_settings", "identity_provider_configs",
    "item_embeddings", "matching_results", "notification_preferences",
    "notification_deliveries", "background_jobs", "retention_policies",
    "archive_records", "extension_provider_configs",
]

def columns(bind, table): return {x["name"] for x in sa.inspect(bind).get_columns(table)}

def add_column(bind, table, column):
    if column.name not in columns(bind, table): op.add_column(table, column)

def upgrade():
    bind = op.get_bind()
    add_column(bind, "institutions", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    add_column(bind, "institutions", sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'" if bind.dialect.name == "postgresql" else "'{}'")))
    add_column(bind, "users", sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    add_column(bind, "categories", sa.Column("institution_id", sa.String(36), nullable=True))
    add_column(bind, "categories", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    add_column(bind, "lost_reports", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    add_column(bind, "lost_reports", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    add_column(bind, "found_items", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    add_column(bind, "found_items", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    if bind.execute(sa.text("SELECT COUNT(*) FROM categories WHERE institution_id IS NULL")).scalar():
        bind.execute(sa.text("UPDATE categories SET institution_id=(SELECT id FROM institutions ORDER BY created_at LIMIT 1) WHERE institution_id IS NULL"))
    if bind.dialect.name == "postgresql":
        uniques = {x["name"] for x in sa.inspect(bind).get_unique_constraints("categories")}
        for name in ("categories_name_key", "categories_slug_key"):
            if name in uniques: op.drop_constraint(name, "categories", type_="unique")
        fks = {x["name"] for x in sa.inspect(bind).get_foreign_keys("categories")}
        if "fk_categories_institution" not in fks: op.create_foreign_key("fk_categories_institution", "categories", "institutions", ["institution_id"], ["id"])
        op.alter_column("categories", "institution_id", nullable=False)
        uniques = {x["name"] for x in sa.inspect(bind).get_unique_constraints("categories")}
        if "uq_categories_institution_slug" not in uniques: op.create_unique_constraint("uq_categories_institution_slug", "categories", ["institution_id", "slug"])

    for name in NEW_TABLES: Base.metadata.tables[name].create(bind, checkfirst=True)
    bind.execute(sa.text("INSERT INTO institution_memberships (id,institution_id,user_id,role,is_active,created_at,updated_at) SELECT id,institution_id,id,role,true,created_at,updated_at FROM users WHERE NOT EXISTS (SELECT 1 FROM institution_memberships m WHERE m.user_id=users.id AND m.institution_id=users.institution_id)"))
    bind.execute(sa.text("INSERT INTO institution_settings (id,institution_id,timezone,matching_threshold,email_enabled,retention_days,created_at,updated_at) SELECT id,id,'UTC',35,false,730,created_at,updated_at FROM institutions WHERE NOT EXISTS (SELECT 1 FROM institution_settings s WHERE s.institution_id=institutions.id)"))
    bind.execute(sa.text("INSERT INTO retention_policies (id,institution_id,retention_days,enabled,created_at,updated_at) SELECT id,id,730,false,created_at,updated_at FROM institutions WHERE NOT EXISTS (SELECT 1 FROM retention_policies p WHERE p.institution_id=institutions.id)"))

def downgrade():
    bind=op.get_bind()
    for name in reversed(NEW_TABLES): Base.metadata.tables[name].drop(bind, checkfirst=True)
    for table, names in [("found_items",["archived_at","is_archived"]),("lost_reports",["archived_at","is_archived"]),("categories",["is_active","institution_id"]),("users",["is_platform_admin"]),("institutions",["settings","is_active"])]:
        existing=columns(bind,table)
        for name in names:
            if name in existing: op.drop_column(table,name)
