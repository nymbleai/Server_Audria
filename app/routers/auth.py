from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.schemas.auth import (
    UserSignUp,
    UserSignIn,
    AuthResponse,
    TokenData,
    SignOutResponse,
    UserInfoResponse,
    StatusResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse
)
from app.services.supabase_service import supabase_service
from app.core.auth import get_current_user
from typing import Dict, Any, Optional

security = HTTPBearer()

def convert_supabase_session(session, user) -> Optional[Dict[str, Any]]:
    """Convert Supabase session and user objects to our format"""
    if not session or not user:
        return None
    
    try:
        return {
            "access_token": getattr(session, 'access_token', ''),
            "refresh_token": getattr(session, 'refresh_token', ''),
            "expires_in": getattr(session, 'expires_in', 3600),
            "token_type": getattr(session, 'token_type', 'bearer'),
            "user": {
                "id": getattr(user, 'id', ''),
                "email": getattr(user, 'email', ''),
                "email_confirmed_at": getattr(user, 'email_confirmed_at', None),
                "last_sign_in_at": getattr(user, 'last_sign_in_at', None),
                "created_at": getattr(user, 'created_at', None),
                "updated_at": getattr(user, 'updated_at', None),
                "user_metadata": getattr(user, 'user_metadata', {})
            }
        }
    except Exception as e:
        print(f"Error converting session: {e}")
        return None


router = APIRouter()


@router.post(
    "/signup",
    response_model=AuthResponse,
    summary="Sign up new user",
    description="Create a new user account with email and password",
    tags=["Authentication"]
)
async def sign_up(user_data: UserSignUp):
    """Sign up a new user with Supabase"""
    try:
        result = await supabase_service.sign_up(
            email=user_data.email,
            password=user_data.password,
            metadata={"name": user_data.name} if user_data.name else None
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Sign up failed")
            )
        
        return AuthResponse(
            success=True,
            message="User created successfully. Please check your email for verification.",
            session=convert_supabase_session(result.get("session"), result.get("user"))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/signin",
    response_model=AuthResponse,
    summary="Sign in user",
    description="Authenticate user with email and password",
    tags=["Authentication"]
)
async def sign_in(user_credentials: UserSignIn):
    """Sign in a user with Supabase"""
    try:
        result = await supabase_service.sign_in(
            email=user_credentials.email,
            password=user_credentials.password
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.get("error", "Invalid credentials")
            )
        
        return AuthResponse(
            success=True,
            message="Signed in successfully",
            session=convert_supabase_session(result.get("session"), result.get("user"))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Refresh access token",
    description="Refresh the access token using a valid refresh token",
    tags=["Authentication"]
)
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Refresh access token using refresh token"""
    try:
        refresh_token = credentials.credentials
        result = await supabase_service.refresh_session(refresh_token)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token refresh failed: {result.get('error', 'Unknown error')}"
            )
        
        session_data = convert_supabase_session(result["session"], result["user"])
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process refreshed session"
            )
        
        return AuthResponse(
            success=True,
            message="Token refreshed successfully",
            session=session_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Refresh token error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token refresh"
        )


@router.post(
    "/signout",
    response_model=SignOutResponse,
    summary="Sign out user",
    description="Sign out the currently authenticated user",
    tags=["Authentication"]
)
async def sign_out(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: TokenData = Depends(get_current_user)
):
    """Sign out the currently authenticated user"""
    try:
        access_token = credentials.credentials
        result = await supabase_service.sign_out(access_token)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Sign out failed")
            )
        
        return SignOutResponse(
            success=True,
            message=result.get("message", "Signed out successfully")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="Get current user info",
    description="Get information about the currently authenticated user",
    tags=["Authentication"]
)
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    """Get current user information"""
    try:
        return UserInfoResponse(
            success=True,
            user={
                "id": current_user.user_id,
                "email": current_user.email
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Send password reset email",
    description="Send a password reset email to the user's email address",
    tags=["Authentication"]
)
async def forgot_password(request: ForgotPasswordRequest):
    """Send password reset email to user"""
    try:
        email_lower = request.email.lower().strip()
        
        # Check if user exists first
        user_check = await supabase_service.get_user_by_email(email_lower)
        if not user_check.get("success") or not user_check.get("user"):
            # Return success but don't send email
            return ForgotPasswordResponse(
                success=True,
                message="If an account with this email exists, you will receive a password reset email shortly."
            )
        
        # User exists, send password reset email
        result = await supabase_service.forgot_password(email_lower)
        
        return ForgotPasswordResponse(
            success=True,
            message="If an account with this email exists, you will receive a password reset email shortly."
        )
        
    except Exception as e:
        print(f"Exception in forgot_password: {str(e)}")
        return ForgotPasswordResponse(
            success=True,
            message="If an account with this email exists, you will receive a password reset email shortly."
        )


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Reset user password",
    description="Reset user password using the token from the reset email",
    tags=["Authentication"]
)
async def reset_password(request: ResetPasswordRequest):
    """Reset user password using access token from reset email"""
    try:
        result = await supabase_service.reset_password(
            access_token=request.access_token,
            new_password=request.new_password
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Password reset failed")
            )
        
        return ResetPasswordResponse(
            success=True,
            message="Password updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Check auth service status",
    description="Check if the authentication service and Supabase integration are working",
    tags=["Authentication", "Health"]
)
async def auth_status():
    """Check authentication service status"""
    try:
        return StatusResponse(
            success=True,
            message="Authentication service is running",
            supabase_configured=bool(supabase_service.supabase)
        )
    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": str(e)
            },
            status_code=500
        )
