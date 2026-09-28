"""V2 workflow scheduling and platform bootstrap."""
from alembic import op
import sqlalchemy as sa
revision="0003_v2_workflow";down_revision="0002_findora_v2";branch_labels=None;depends_on=None
def upgrade():
    bind=op.get_bind();existing={x["name"] for x in sa.inspect(bind).get_columns("claims")}
    for column in [sa.Column("verification_requested_at",sa.DateTime(timezone=True)),sa.Column("verification_request",sa.Text()),sa.Column("handover_scheduled_at",sa.DateTime(timezone=True))]:
        if column.name not in existing:op.add_column("claims",column)
    bind.execute(sa.text("UPDATE users SET is_platform_admin=true WHERE id=(SELECT id FROM users WHERE role='ADMIN' ORDER BY created_at LIMIT 1) AND NOT EXISTS (SELECT 1 FROM users WHERE is_platform_admin=true)"))
def downgrade():
    bind=op.get_bind();existing={x["name"] for x in sa.inspect(bind).get_columns("claims")}
    for name in ["handover_scheduled_at","verification_request","verification_requested_at"]:
        if name in existing:op.drop_column("claims",name)
