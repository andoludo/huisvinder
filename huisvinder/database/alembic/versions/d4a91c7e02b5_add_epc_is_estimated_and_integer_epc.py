"""add epc_is_estimated column and make epc an integer

Revision ID: d4a91c7e02b5
Revises: c6795426538c
Create Date: 2026-07-21 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd4a91c7e02b5'
down_revision: Union[str, None] = 'c6795426538c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # epc becomes kWh/m² per year as an integer; the SQLite table rebuild keeps
    # pre-existing raw text values as-is (they parse on the next scrape), while
    # numeric strings gain INTEGER affinity. epc_is_estimated records whether
    # the value came from a band-label fallback rather than a measurement.
    with op.batch_alter_table('basehouse', schema=None) as batch_op:
        batch_op.alter_column('epc', existing_type=sqlmodel.sql.sqltypes.AutoString(), type_=sa.Integer(), existing_nullable=True)
        batch_op.add_column(sa.Column('epc_is_estimated', sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('basehouse', schema=None) as batch_op:
        batch_op.drop_column('epc_is_estimated')
        batch_op.alter_column('epc', existing_type=sa.Integer(), type_=sqlmodel.sql.sqltypes.AutoString(), existing_nullable=True)
