"""Change photo_hashes and text_embeddings to JSONB

Revision ID: 39d4cdae1ffd
Revises: d7499a6679b7
Create Date: 2025-06-24 11:54:11.741566

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39d4cdae1ffd'
down_revision: Union[str, Sequence[str], None] = 'd7499a6679b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Меняем тип photo_hashes и text_embeddings на JSONB
    op.alter_column('unique_ads', 'photo_hashes', type_=sa.dialects.postgresql.JSONB, postgresql_using='photo_hashes::jsonb')
    op.alter_column('unique_ads', 'text_embeddings', type_=sa.dialects.postgresql.JSONB, postgresql_using='text_embeddings::jsonb')


def downgrade() -> None:
    """Downgrade schema."""
    # Возвращаем обратно в JSON
    op.alter_column('unique_ads', 'photo_hashes', type_=sa.JSON, postgresql_using='photo_hashes::json')
    op.alter_column('unique_ads', 'text_embeddings', type_=sa.JSON, postgresql_using='text_embeddings::json')
