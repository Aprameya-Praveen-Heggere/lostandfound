"""Allow email delivery independently of in-app visibility.

Revision ID: 0005_notification_channels
Revises: 0004_handover_archival
"""
from alembic import op
import sqlalchemy as sa

revision="0005_notification_channels"
down_revision="0004_handover_archival"
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind();columns={x["name"] for x in sa.inspect(bind).get_columns("notifications")}
    if "in_app_visible" not in columns:op.add_column("notifications",sa.Column("in_app_visible",sa.Boolean(),nullable=False,server_default=sa.true()))
    indexes={x["name"] for x in sa.inspect(bind).get_indexes("notifications")}
    if "ix_notifications_in_app_visible" not in indexes:op.create_index("ix_notifications_in_app_visible","notifications",["in_app_visible"])


def downgrade():
    bind=op.get_bind();inspector=sa.inspect(bind)
    if "ix_notifications_in_app_visible" in {x["name"] for x in inspector.get_indexes("notifications")}:op.drop_index("ix_notifications_in_app_visible",table_name="notifications")
    if "in_app_visible" in {x["name"] for x in sa.inspect(bind).get_columns("notifications")}:op.drop_column("notifications","in_app_visible")
