"""Fix CLIP embedding indexes - remove them as they're too large

Revision ID: fix_clip_embedding_indexes
Revises: update_photo_hash_structure
Create Date: 2025-07-30 08:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fix_clip_embedding_indexes'
down_revision = 'update_photo_hash_structure'
branch_labels = None
depends_on = None

def upgrade():
    """Remove indexes on clip_embedding as they're too large for PostgreSQL"""
    
    # Удаляем индексы с clip_embedding (слишком большие)
    op.drop_index(op.f('ix_photos_clip_embedding'), table_name='photos')
    op.drop_index(op.f('ix_unique_photos_clip_embedding'), table_name='unique_photos')
    
    # Оставляем только индексы для perceptual_hashes (они нормального размера)
    # Индексы для perceptual_hashes уже созданы в предыдущей миграции

def downgrade():
    """Recreate indexes on clip_embedding (not recommended due to size)"""
    
    # Восстанавливаем индексы (но это может вызвать ошибки)
    op.create_index(op.f('ix_photos_clip_embedding'), 'photos', ['clip_embedding'], unique=False)
    op.create_index(op.f('ix_unique_photos_clip_embedding'), 'unique_photos', ['clip_embedding'], unique=False) 