from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime

class UserSignUp(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class UserSignIn(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    access_token: str
    new_password: str

class ForgotPasswordResponse(BaseModel):
    success: bool
    message: str

class ResetPasswordResponse(BaseModel):
    success: bool
    message: str

class UserResponse(BaseModel):
    id: str
    email: str
    email_confirmed_at: Optional[datetime] = None
    last_sign_in_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    user_metadata: Optional[Dict[str, Any]] = None

class SessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    user: UserResponse

class AuthResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    session: Optional[SessionResponse] = None
    error: Optional[str] = None

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None

class SignOutResponse(BaseModel):
    success: bool
    message: str

class UserInfoResponse(BaseModel):
    success: bool
    user: Dict[str, Any]

class StatusResponse(BaseModel):
    success: bool
    message: str
    supabase_configured: bool 