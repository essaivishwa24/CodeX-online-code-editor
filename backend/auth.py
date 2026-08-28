import os
from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from .database import get_db
from .db_models import User

SECRET = os.getenv("JWT_SECRET_KEY", "dev-only-change-this-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
oauth2 = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def hash_password(value: str) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(value: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(value.encode("utf-8"), hashed.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def create_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": str(user.id), "role": user.role, "exp": expires_at},
        SECRET,
        algorithm=ALGORITHM,
    )
def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)):
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate":"Bearer"})
    try: user_id = int(jwt.decode(token, SECRET, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError): raise error
    user = db.get(User, user_id)
    if not user or not user.is_active: raise error
    return user
def admin_user(user=Depends(current_user)):
    if user.role != "admin": raise HTTPException(403, "Admin access required")
    return user
