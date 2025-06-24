"""Change phone_numbers and attributes to JSONB

Revision ID: d7499a6679b7
Revises: 451f21389ad6
Create Date: 2025-06-24 11:43:57.221737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7499a6679b7'
down_revision: Union[str, Sequence[str], None] = '451f21389ad6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Меняем тип phone_numbers и attributes на JSONB
    op.alter_column('ads', 'phone_numbers', type_=sa.dialects.postgresql.JSONB, postgresql_using='phone_numbers::jsonb')
    op.alter_column('ads', 'attributes', type_=sa.dialects.postgresql.JSONB, postgresql_using='attributes::jsonb')
    op.alter_column('unique_ads', 'phone_numbers', type_=sa.dialects.postgresql.JSONB, postgresql_using='phone_numbers::jsonb')
    op.alter_column('unique_ads', 'attributes', type_=sa.dialects.postgresql.JSONB, postgresql_using='attributes::jsonb')


def downgrade() -> None:
    """Downgrade schema."""
    # Возвращаем обратно в JSON
    op.alter_column('ads', 'phone_numbers', type_=sa.JSON, postgresql_using='phone_numbers::json')
    op.alter_column('ads', 'attributes', type_=sa.JSON, postgresql_using='attributes::json')
    op.alter_column('unique_ads', 'phone_numbers', type_=sa.JSON, postgresql_using='phone_numbers::json')
    op.alter_column('unique_ads', 'attributes', type_=sa.JSON, postgresql_using='attributes::json')
