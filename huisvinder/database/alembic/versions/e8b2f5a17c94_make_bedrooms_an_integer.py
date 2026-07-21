"""make bedrooms an integer

Revision ID: e8b2f5a17c94
Revises: 6d206eddcb0c
Create Date: 2026-07-21 21:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e8b2f5a17c94'
down_revision: Union[str, None] = '6d206eddcb0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # bedrooms becomes an integer count; the SQLite table rebuild converts
    # numeric strings via INTEGER affinity and keeps unparsed raw text as-is
    # (it parses on the next scrape).
    with op.batch_alter_table('basehouse', schema=None) as batch_op:
        batch_op.alter_column('bedrooms', existing_type=sqlmodel.sql.sqltypes.AutoString(), type_=sa.Integer(), existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('basehouse', schema=None) as batch_op:
        batch_op.alter_column('bedrooms', existing_type=sa.Integer(), type_=sqlmodel.sql.sqltypes.AutoString(), existing_nullable=True)
