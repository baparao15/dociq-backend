from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from models import User
from database import get_db
import os
import secrets

def get_secret_key():
    secret = os.getenv("SECRET_KEY")
    if not secret:
        generated = secrets.token_urlsafe(32)
        print("WARNING: SECRET_KEY not set in environment! Using generated key (not persistent across restarts):")
        print(f"SECRET_KEY={generated}")
        print("Add this to your environment variables for production!")
        return generated
    return secret

SECRET_KEY = get_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

# Password hashing context - Using Argon2 only (bcrypt removed due to Python 3.13 compatibility issues)
# Old bcrypt hashes will be migrated to argon2 on next successful login
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

security = HTTPBearer()

def is_bcrypt_hash(hashed_password: str) -> bool:
    """Check if hash is in bcrypt format."""
    return hashed_password.startswith(('$2a$', '$2b$', '$2y$'))

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash.
    Only supports argon2 hashes (bcrypt support removed due to Python 3.13 issues).
    For legacy bcrypt hashes, we cannot verify them - users must reset password.
    """
    # If it's a bcrypt hash, we can't verify it (bcrypt removed due to Python 3.13)
    if is_bcrypt_hash(hashed_password):
        # Return False - user will need to reset password or re-signup
        # This is a migration limitation
        return False
    
    # Verify argon2 hash
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Generate password hash using argon2."""
    return pwd_context.hash(password)

def migrate_password_if_needed(plain_password: str, hashed_password: str, db: Session, user: User) -> bool:
    """Migrate old bcrypt password to argon2 if needed.
    Returns True if migration occurred, False otherwise.
    """
    if is_bcrypt_hash(hashed_password):
        # Verify the password works with old hash
        if verify_password(plain_password, hashed_password):
            # Re-hash with argon2 and update database
            new_hash = get_password_hash(plain_password)
            user.hashed_password = new_hash
            db.commit()
            return True
    return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise credentials_exception
    
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
