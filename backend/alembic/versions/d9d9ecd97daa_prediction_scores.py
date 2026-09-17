"""prediction scores

Revision ID: d9d9ecd97daa
Revises: 58e2eff31b28
Create Date: 2026-09-17

Note: LangGraph's checkpoint tables live in the same database and are owned by
the checkpoint saver, never by Alembic (see include_object in env.py).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d9d9ecd97daa"
down_revision: Union[str, None] = "58e2eff31b28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prediction_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("matured_on", sa.Date(), nullable=False),
        sa.Column("n", sa.Integer(), nullable=True),
        sa.Column("auc", sa.Float(), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("top_decile_hit", sa.Float(), nullable=True),
        sa.Column("top_decile_excess_pct", sa.Float(), nullable=True),
        sa.Column("median_return_pct", sa.Float(), nullable=True),
        sa.Column("scored_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_date", "horizon", name="uq_prediction_score"),
    )
    with op.batch_alter_table("prediction_scores", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_prediction_scores_run_date"), ["run_date"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("prediction_scores", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_prediction_scores_run_date"))
    op.drop_table("prediction_scores")
