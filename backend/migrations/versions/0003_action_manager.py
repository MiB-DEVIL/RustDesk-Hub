"""action manager

Revision ID: 0003_action_manager
Revises: 0002_machine_identity
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_action_manager"
down_revision = "0002_machine_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action_uuid", sa.String(), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(), nullable=False, server_default="admin"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("result_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("result_data", sa.Text(), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("action_uuid", name="uq_agent_actions_action_uuid"),
    )
    op.create_index("ix_agent_actions_action_uuid", "agent_actions", ["action_uuid"])
    op.create_index("ix_agent_actions_client_id", "agent_actions", ["client_id"])
    op.create_index("ix_agent_actions_action_type", "agent_actions", ["action_type"])
    op.create_index("ix_agent_actions_status", "agent_actions", ["status"])
    op.create_index("ix_agent_actions_created_at", "agent_actions", ["created_at"])


def downgrade():
    op.drop_index("ix_agent_actions_created_at", table_name="agent_actions")
    op.drop_index("ix_agent_actions_status", table_name="agent_actions")
    op.drop_index("ix_agent_actions_action_type", table_name="agent_actions")
    op.drop_index("ix_agent_actions_client_id", table_name="agent_actions")
    op.drop_index("ix_agent_actions_action_uuid", table_name="agent_actions")
    op.drop_table("agent_actions")
