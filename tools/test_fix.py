#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database import SessionLocal
from app.database import db_models
from app.utils.duplicate_processor import DuplicateProcessor
from sqlalchemy import and_

def test_fix():
    db = SessionLocal()
    try:
        processor = DuplicateProcessor(db)
        
        # Находим объявление без unique_ad_id
        orphan_ads = db.query(db_models.DBAd).filter(
            and_(
                db_models.DBAd.is_processed == True,
                db_models.DBAd.unique_ad_id.is_(None)
            )
        ).limit(1).all()
        
        if not orphan_ads:
            print("No orphan ads found")
            return
            
        ad = orphan_ads[0]
        print(f"Testing with ad {ad.id}")
        print(f"Title: {ad.title[:50]}...")
        print(f"Price: {ad.price}, Area: {ad.area_sqm}, Rooms: {ad.rooms}")
        
        # Тестируем дедупликацию
        ad_photo_hashes = [photo.hash for photo in ad.photos if photo.hash]
        print(f"Photo hashes: {len(ad_photo_hashes)}")
        
        text_embeddings = processor._get_text_embeddings(ad)
        print(f"Text embeddings shape: {text_embeddings.shape}")
        
        similar_ads = processor._find_similar_unique_ads(ad, ad_photo_hashes, text_embeddings)
        print(f"Found {len(similar_ads)} similar ads")
        
        if similar_ads:
            unique_ad, similarity = similar_ads[0]
            print(f"Best match: ID {unique_ad.id}, similarity {similarity:.3f}")
            
            # Тестируем characteristics similarity
            char_sim = processor._calculate_property_characteristics_similarity(ad, unique_ad)
            print(f"Characteristics similarity: {char_sim:.3f}")
            
            # Тестируем общую схожесть
            overall_sim, threshold = processor._calculate_similarity_with_unique(
                ad, unique_ad, ad_photo_hashes, text_embeddings
            )
            print(f"Overall similarity: {overall_sim:.3f}, Threshold: {threshold:.3f}")
            print(f"Is duplicate: {overall_sim > threshold}")
        else:
            print("No similar ads found")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_fix() 