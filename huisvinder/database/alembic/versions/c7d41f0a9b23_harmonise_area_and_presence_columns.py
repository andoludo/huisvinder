"""harmonise area and presence columns

living_area/surface_ground become FLOAT square metres, garden/garage become
BOOLEAN presence flags. The raw strings are parsed row by row BEFORE the type
change so nothing is lost to SQLite's affinity conversion during the table
rebuild. The downgrade restores parseable string forms ('297.0', 'ja'/'nee'),
not the original scraped text — that text is unrecoverable by design and the
next scrape refills it.

Revision ID: c7d41f0a9b23
Revises: e8b2f5a17c94
Create Date: 2026-07-22 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

from huisvinder.models import parse_area, parse_presence


# revision identifiers, used by Alembic.
revision: str = 'c7d41f0a9b23'
down_revision: Union[str, None] = 'e8b2f5a17c94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UPDATE = sa.text(
    "UPDATE basehouse SET living_area = :living_area, surface_ground = :surface_ground, "
    "garden = :garden, garage = :garage WHERE rowid = :rowid"
)


def upgrade() -> None:
    # backfill first: parse the raw strings while the columns are still text.
    # parse_area/parse_presence pass floats and bools through, so re-running
    # on already-clean values is a no-op.
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT rowid, living_area, surface_ground, garden, garage FROM basehouse"))
    for rowid, living_area, surface_ground, garden, garage in rows.fetchall():
        bind.execute(
            _UPDATE,
            {
                "rowid": rowid,
                "living_area": parse_area(living_area),
                "surface_ground": parse_area(surface_ground),
                "garden": parse_presence(garden),
                "garage": parse_presence(garage),
            },
        )
    with op.batch_alter_table('basehouse', schema=None) as batch_op:
        batch_op.alter_column('living_area', existing_type=sqlmodel.sql.sqltypes.AutoString(), type_=sa.Float(), existing_nullable=True)
        batch_op.alter_column('surface_ground', existing_type=sqlmodel.sql.sqltypes.AutoString(), type_=sa.Float(), existing_nullable=True)
        batch_op.alter_column('garden', existing_type=sqlmodel.sql.sqltypes.AutoString(), type_=sa.Boolean(), existing_nullable=True)
        batch_op.alter_column('garage', existing_type=sqlmodel.sql.sqltypes.AutoString(), type_=sa.Boolean(), existing_nullable=True)


def downgrade() -> None:
    # type change first: TEXT affinity renders the floats as '297.0' and the
    # flags as '1'/'0' during the rebuild; then rewrite the flags as 'ja'/'nee'
    # so the upgrade parser round-trips them.
    with op.batch_alter_table('basehouse', schema=None) as batch_op:
        batch_op.alter_column('living_area', existing_type=sa.Float(), type_=sqlmodel.sql.sqltypes.AutoString(), existing_nullable=True)
        batch_op.alter_column('surface_ground', existing_type=sa.Float(), type_=sqlmodel.sql.sqltypes.AutoString(), existing_nullable=True)
        batch_op.alter_column('garden', existing_type=sa.Boolean(), type_=sqlmodel.sql.sqltypes.AutoString(), existing_nullable=True)
        batch_op.alter_column('garage', existing_type=sa.Boolean(), type_=sqlmodel.sql.sqltypes.AutoString(), existing_nullable=True)
    bind = op.get_bind()
    for column in ("garden", "garage"):
        bind.execute(
            sa.text(
                f"UPDATE basehouse SET {column} = "  # noqa: S608 -- column names are the literals above
                f"CASE {column} WHEN '1' THEN 'ja' WHEN '0' THEN 'nee' ELSE {column} END"
            )
        )
