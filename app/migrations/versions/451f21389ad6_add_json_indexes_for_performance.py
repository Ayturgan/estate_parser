"""Add JSON indexes for performance

Revision ID: 451f21389ad6
Revises: 721121692678
Create Date: 2025-06-24 11:41:26.620906

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '451f21389ad6'
down_revision: Union[str, Sequence[str], None] = '721121692678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Составной индекс для быстрого поиска по локации и цене
    op.create_index('idx_unique_ads_location_price', 'unique_ads', ['location_id', 'price'])
    
    # Составной индекс для быстрого поиска по локации и комнатам
    op.create_index('idx_unique_ads_location_rooms', 'unique_ads', ['location_id', 'rooms'])
    
    # Индекс для is_processed для быстрого поиска необработанных объявлений
    op.create_index('idx_ads_is_processed', 'ads', ['is_processed'])
    
    # Индекс для is_duplicate
    op.create_index('idx_ads_is_duplicate', 'ads', ['is_duplicate'])


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем индексы
    op.drop_index('idx_unique_ads_location_price', table_name='unique_ads')
    op.drop_index('idx_unique_ads_location_rooms', table_name='unique_ads')
    op.drop_index('idx_ads_is_processed', table_name='ads')
    op.drop_index('idx_ads_is_duplicate', table_name='ads')
