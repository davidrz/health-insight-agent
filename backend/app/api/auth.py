"""
Authentication and authorization utilities for the Health Insight Agent API.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """Token data model"""
    username: Optional[str] = None
    user_id: Optional[str] = None
    roles: list = []


class User(BaseModel):
    """User model for authentication"""
    username: str
    user_id: str
    email: Optional[str] = None
    roles: list = []
    is_active: bool = True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    """Verify and decode JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        roles: list = payload.get("roles", [])
        
        if username is None:
            raise credentials_exception
            
        token_data = TokenData(username=username, user_id=user_id, roles=roles)
        return token_data
    except JWTError:
        raise credentials_exception


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    token_data = verify_token(token)
    
    # In a real application, you would fetch user data from database
    # For now, we'll create a user object from token data
    user = User(
        username=token_data.username,
        user_id=token_data.user_id or token_data.username,
        roles=token_data.roles
    )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_roles(required_roles: list):
    """Decorator to require specific roles for endpoint access"""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if not any(role in current_user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker


# Mock user database for demonstration
# In production, this would be replaced with actual database queries
MOCK_USERS_DB = {
    "healthcare_provider": {
        "username": "healthcare_provider",
        "hashed_password": get_password_hash("demo_password"),
        "user_id": "hp_001",
        "email": "provider@healthcare.com",
        "roles": ["healthcare_provider", "user"],
        "is_active": True
    },
    "patient": {
        "username": "patient",
        "hashed_password": get_password_hash("demo_password"),
        "user_id": "patient_001",
        "email": "patient@example.com",
        "roles": ["patient", "user"],
        "is_active": True
    },
    "admin": {
        "username": "admin",
        "hashed_password": get_password_hash("admin_password"),
        "user_id": "admin_001",
        "email": "admin@healthcare.com",
        "roles": ["admin", "healthcare_provider", "user"],
        "is_active": True
    }
}


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user with username and password"""
    user = MOCK_USERS_DB.get(username)
    if not user:
        return None
    
    if not verify_password(password, user["hashed_password"]):
        return None
    
    return user


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username"""
    return MOCK_USERS_DB.get(username)