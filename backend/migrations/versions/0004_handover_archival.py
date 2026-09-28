"""Archive completed handovers without deleting audit history.

Revision ID: 0004_handover_archival
Revises: 0003_v2_workflow
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_handover_archival"
down_revision = "0003_v2_workflow"
branch_labels = None
depends_on = None


def upgrade():
    bind=op.get_bind();inspector=sa.inspect(bind)
    columns={column["name"] for column in inspector.get_columns("handovers")}
    if "is_archived" not in columns:op.add_column("handovers",sa.Column("is_archived",sa.Boolean(),nullable=False,server_default=sa.false()))
    if "archived_at" not in columns:op.add_column("handovers",sa.Column("archived_at",sa.DateTime(timezone=True),nullable=True))
    indexes={index["name"] for index in sa.inspect(bind).get_indexes("handovers")}
    if "ix_handovers_is_archived" not in indexes:op.create_index("ix_handovers_is_archived","handovers",["is_archived"])


def downgrade():
    bind=op.get_bind();inspector=sa.inspect(bind)
    indexes={index["name"] for index in inspector.get_indexes("handovers")}
    if "ix_handovers_is_archived" in indexes:op.drop_index("ix_handovers_is_archived",table_name="handovers")
    columns={column["name"] for column in sa.inspect(bind).get_columns("handovers")}
    if "archived_at" in columns:op.drop_column("handovers","archived_at")
    if "is_archived" in columns:op.drop_column("handovers","is_archived")
