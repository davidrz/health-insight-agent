"""
Authentication endpoints for the Health Insight Agent API.
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer

from app.api.schemas import TokenRequest, TokenResponse, ErrorResponse
from app.api.auth import authenticate_user, create_access_token
from app.core.config import settings


router = APIRouter()
security = HTTPBearer()


@router.post(
    "/token",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    },
    summary="Obtain JWT access token",
    description="Authenticate with username and password to receive a JWT access token"
)
async def login(token_request: TokenRequest):
    """
    Authenticate user and return JWT access token.
    
    - **username**: User's username
    - **password**: User's password
    
    Returns JWT access token for API authentication.
    """
    user = authenticate_user(token_request.username, token_request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["user_id"],
            "roles": user["roles"]
        },
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )