import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
import jwt
from sqlalchemy.orm import Session
from app.database.db_models import DBAdmin
from app.database.models import AdminCreate, AdminResponse, Token, AdminLogin
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """Сервис для авторизации и управления администраторами"""
    
    def __init__(self):
        # Секретный ключ для JWT (в продакшене должен быть в переменных окружения)
        import os
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        self.JWT_ALGORITHM = "HS256"
        self.JWT_EXPIRATION_HOURS = 24
        
        # Проверяем, что секретный ключ установлен правильно
        if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == "your-secret-key-change-in-production":
            logger.error("❌ JWT_SECRET_KEY не установлен или использует значение по умолчанию!")
            logger.error("❌ Установите переменную окружения JWT_SECRET_KEY")
        else:
            logger.info(f"✅ JWT_SECRET_KEY установлен: {self.JWT_SECRET_KEY[:10]}...")
        
        logger.info(f"🔑 AuthService initialized with JWT_SECRET_KEY: {self.JWT_SECRET_KEY[:10]}..." if self.JWT_SECRET_KEY else "🔑 AuthService initialized with JWT_SECRET_KEY: None")

    def hash_password(self, password: str) -> str:
        """Хэширует пароль с солью"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', 
                                          password.encode('utf-8'), 
                                          salt.encode('utf-8'), 
                                          100000)
        return salt + password_hash.hex()

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Проверяет пароль против хэша"""
        try:
            salt = stored_hash[:32]
            stored_password_hash = stored_hash[32:]
            
            password_hash = hashlib.pbkdf2_hmac('sha256',
                                             password.encode('utf-8'),
                                             salt.encode('utf-8'),
                                             100000)
            
            return password_hash.hex() == stored_password_hash
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def create_access_token(self, admin_id: int, username: str) -> Token:
        """Создает JWT токен для администратора (без срока действия)"""
        payload = {
            "sub": str(admin_id),
            "username": username,
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(payload, self.JWT_SECRET_KEY, algorithm=self.JWT_ALGORITHM)
        
        return Token(
            access_token=token,
            token_type="bearer",
            expires_in=315360000  # 10 лет в секундах
        )

    def verify_token(self, token: str) -> Optional[dict]:
        """Проверяет JWT токен и возвращает данные пользователя"""
        logger.info(f"🔍 Verifying JWT token")
        logger.info(f"🔑 Secret key: {self.JWT_SECRET_KEY[:10]}..." if self.JWT_SECRET_KEY else "🔑 Secret key: None")
        logger.info(f"🔑 Algorithm: {self.JWT_ALGORITHM}")
        
        try:
            payload = jwt.decode(token, self.JWT_SECRET_KEY, algorithms=[self.JWT_ALGORITHM])
            logger.info(f"✅ Token decoded successfully: {payload}")
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("❌ Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"❌ Invalid token: {e}")
            return None
        except jwt.DecodeError as e:
            logger.warning(f"❌ Token decode error: {e}")
            return None
        except jwt.InvalidSignatureError as e:
            logger.warning(f"❌ Invalid signature: {e}")
            logger.warning(f"❌ Возможно, JWT_SECRET_KEY не совпадает с ключом, которым был подписан токен")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error during token verification: {e}")
            logger.exception("Full traceback:")
            return None

    def create_admin(self, db: Session, admin_data: AdminCreate) -> AdminResponse:
        """Создает нового администратора"""
        # Проверяем, что пользователь с таким именем не существует
        existing_admin = db.query(DBAdmin).filter(DBAdmin.username == admin_data.username).first()
        if existing_admin:
            raise ValueError("Пользователь с таким именем уже существует")
        
        # Хэшируем пароль
        password_hash = self.hash_password(admin_data.password)
        
        # Создаем нового администратора
        db_admin = DBAdmin(
            username=admin_data.username,
            password_hash=password_hash,
            full_name=admin_data.full_name,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        db.add(db_admin)
        db.commit()
        db.refresh(db_admin)
        
        logger.info(f"Created new admin: {admin_data.username}")
        
        return AdminResponse(
            id=db_admin.id,
            username=db_admin.username,
            full_name=db_admin.full_name,
            created_at=db_admin.created_at,
            last_login_at=db_admin.last_login_at,
            is_active=db_admin.is_active
        )

    def authenticate_admin(self, db: Session, login_data: AdminLogin) -> Optional[Token]:
        """Аутентифицирует администратора и возвращает токен"""
        # Находим администратора по имени пользователя
        admin = db.query(DBAdmin).filter(
            DBAdmin.username == login_data.username,
            DBAdmin.is_active == True
        ).first()
        
        if not admin:
            logger.warning(f"Admin not found or inactive: {login_data.username}")
            return None
        
        # Проверяем пароль
        if not self.verify_password(login_data.password, admin.password_hash):
            logger.warning(f"Invalid password for admin: {login_data.username}")
            return None
        
        # Обновляем время последнего входа
        admin.last_login_at = datetime.utcnow()
        db.commit()
        
        # Создаем токен
        token = self.create_access_token(admin.id, admin.username)
        
        logger.info(f"Admin authenticated successfully: {login_data.username}")
        return token

    def get_admin_by_token(self, db: Session, token: str) -> Optional[AdminResponse]:
        """Получает данные администратора по токену"""
        logger.info(f"🔍 Verifying token for admin lookup")
        
        payload = self.verify_token(token)
        if not payload:
            logger.warning(f"❌ Token verification failed")
            return None
        
        logger.info(f"✅ Token verified, payload: {payload}")
        
        admin_id = int(payload.get("sub"))
        logger.info(f"🔍 Looking for admin with ID: {admin_id}")
        
        admin = db.query(DBAdmin).filter(
            DBAdmin.id == admin_id,
            DBAdmin.is_active == True
        ).first()
        
        if not admin:
            logger.warning(f"❌ Admin not found or inactive: ID={admin_id}")
            return None
        
        logger.info(f"✅ Admin found: {admin.username} (ID: {admin.id})")
        
        return AdminResponse(
            id=admin.id,
            username=admin.username,
            full_name=admin.full_name,
            created_at=admin.created_at,
            last_login_at=admin.last_login_at,
            is_active=admin.is_active
        )

    def change_admin_password(self, db: Session, admin_id: int, current_password: str, new_password: str) -> bool:
        """Изменяет пароль администратора"""
        admin = db.query(DBAdmin).filter(DBAdmin.id == admin_id).first()
        if not admin:
            return False
        
        # Проверяем текущий пароль
        if not self.verify_password(current_password, admin.password_hash):
            return False
        
        # Хэшируем новый пароль
        new_password_hash = self.hash_password(new_password)
        admin.password_hash = new_password_hash
        
        db.commit()
        logger.info(f"Password changed for admin: {admin.username}")
        return True

    def deactivate_admin(self, db: Session, admin_id: int) -> bool:
        """Деактивирует администратора"""
        admin = db.query(DBAdmin).filter(DBAdmin.id == admin_id).first()
        if not admin:
            return False
        
        admin.is_active = False
        db.commit()
        
        logger.info(f"Admin deactivated: {admin.username}")
        return True

    def get_all_admins(self, db: Session) -> list[AdminResponse]:
        """Получает список всех администраторов"""
        admins = db.query(DBAdmin).all()
        return [
            AdminResponse(
                id=admin.id,
                username=admin.username,
                full_name=admin.full_name,
                created_at=admin.created_at,
                last_login_at=admin.last_login_at,
                is_active=admin.is_active
            )
            for admin in admins
        ]

# Создаем экземпляр сервиса
auth_service = AuthService() 
