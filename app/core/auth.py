from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional
from app.services.supabase_service import supabase_service
from app.schemas.auth import TokenData
from app.core.config import settings

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """Verify JWT token and return user data"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        
        # Try to get user from Supabase using the token
        user_result = await supabase_service.get_user(token)
        
        if not user_result["success"]:
            raise credentials_exception
            
        user = user_result["user"]
        
        if user is None:
            raise credentials_exception
            
        token_data = TokenData(
            user_id=user.id,
            email=user.email
        )
        
        return token_data
        
    except Exception:
        raise credentials_exception

async def get_current_user(token_data: TokenData = Depends(verify_token)) -> TokenData:
    """Get current authenticated user"""
    return token_data

async def get_current_active_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Get current active user (can add additional checks here)"""
    # You can add additional user validation here
    return current_user 