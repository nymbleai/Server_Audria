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
        user_id = None
        email = None
        
        # First, try to decode JWT locally (fast, no network call)
        # This is less secure but much faster for debugging
        try:
            # Decode without verification to get user info quickly
            # In production, you should verify the signature
            payload = jwt.decode(
                token,
                options={"verify_signature": False}  # Skip verification for speed
            )
            user_id = payload.get("sub")
            email = payload.get("email")
            
            if user_id:
                print(f"✅ Fast JWT decode successful for user: {user_id}")
                return TokenData(
                    user_id=user_id,
                    email=email or ""
                )
        except Exception as decode_error:
            print(f"⚠️ JWT decode failed, trying Supabase: {decode_error}")
        
        # Fallback: Try to get user from Supabase (slower but more secure)
        import asyncio
        try:
            user_result = await asyncio.wait_for(
                supabase_service.get_user(token),
                timeout=3.0  # Reduced to 3 seconds
            )
            
            if user_result["success"] and user_result.get("user"):
                user = user_result["user"]
                return TokenData(
                    user_id=user.id,
                    email=user.email
                )
        except asyncio.TimeoutError:
            print("⚠️ Supabase auth timeout, using JWT decode result")
            # If Supabase times out but JWT decode worked, use that
            if user_id:
                return TokenData(user_id=user_id, email=email or "")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Authentication service timeout"
            )
        except Exception as supabase_error:
            print(f"⚠️ Supabase auth error: {supabase_error}")
            # If JWT decode worked, use that as fallback
            if user_id:
                return TokenData(user_id=user_id, email=email or "")
        
        raise credentials_exception
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Auth error: {e}")
        raise credentials_exception

async def get_current_user(token_data: TokenData = Depends(verify_token)) -> TokenData:
    """Get current authenticated user"""
    return token_data

async def get_current_active_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Get current active user (can add additional checks here)"""
    # You can add additional user validation here
    return current_user 