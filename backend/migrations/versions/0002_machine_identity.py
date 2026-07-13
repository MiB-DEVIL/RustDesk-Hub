"""machine identity and history

Revision ID: 0002_machine_identity
Revises: 0001_baseline
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_machine_identity"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("clients") as batch:
        batch.add_column(sa.Column("machine_uuid", sa.String(), nullable=True))
        batch.add_column(sa.Column("bios_serial", sa.String(), server_default=""))
        batch.add_column(sa.Column("motherboard_serial", sa.String(), server_default=""))
        batch.add_column(sa.Column("primary_mac", sa.String(), server_default=""))
        batch.add_column(sa.Column("agent_version", sa.String(), server_default=""))
        batch.add_column(sa.Column("first_seen", sa.DateTime(), nullable=True))
        batch.create_unique_constraint("uq_clients_machine_uuid", ["machine_uuid"])
        batch.create_index("ix_clients_machine_uuid", ["machine_uuid"], unique=False)

    op.execute("UPDATE clients SET first_seen = COALESCE(last_seen, CURRENT_TIMESTAMP) WHERE first_seen IS NULL")

    op.create_table(
        "machine_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("old_value", sa.Text(), server_default=""),
        sa.Column("new_value", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_machine_changes_client_id", "machine_changes", ["client_id"])
    op.create_index("ix_machine_changes_created_at", "machine_changes", ["created_at"])


def downgrade():
    op.drop_index("ix_machine_changes_created_at", table_name="machine_changes")
    op.drop_index("ix_machine_changes_client_id", table_name="machine_changes")
    op.drop_table("machine_changes")

    with op.batch_alter_table("clients") as batch:
        batch.drop_index("ix_clients_machine_uuid")
        batch.drop_constraint("uq_clients_machine_uuid", type_="unique")
        batch.drop_column("first_seen")
        batch.drop_column("agent_version")
        batch.drop_column("primary_mac")
        batch.drop_column("motherboard_serial")
        batch.drop_column("bios_serial")
        batch.drop_column("machine_uuid")
