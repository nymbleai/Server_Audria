from supabase import create_client, Client
from app.core.config import settings
from typing import Optional, Dict, Any
import asyncio
from functools import wraps
import inspect

class SupabaseService:
    def __init__(self):
        self.supabase = None
        if settings.supabase_url and settings.supabase_key:
            try:
                # Create client with minimal options to avoid compatibility issues
                self.supabase: Client = create_client(
                    supabase_url=settings.supabase_url, 
                    supabase_key=settings.supabase_key
                )
                print("✅ Supabase client initialized successfully")
            except Exception as e:
                print(f"❌ Warning: Failed to initialize Supabase client: {e}")
                self.supabase = None
        else:
            print("❌ Warning: Supabase URL or KEY not provided")

    def _check_client(self):
        if not self.supabase:
            raise Exception("Supabase client not initialized. Check your SUPABASE_URL and SUPABASE_KEY.")

    async def sign_up(self, email: str, password: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Sign up a new user"""
        self._check_client()
        try:
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": metadata or {}
                }
            })
            return {
                "success": True,
                "user": response.user,
                "session": response.session
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in a user"""
        self._check_client()
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            return {
                "success": True,
                "user": response.user,
                "session": response.session
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh user session using refresh token"""
        self._check_client()
        try:
            response = self.supabase.auth.refresh_session(refresh_token)
            return {
                "success": True,
                "user": response.user,
                "session": response.session
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def sign_out(self, access_token: str) -> Dict[str, Any]:
        """Sign out a user - validates token and confirms signout"""
        self._check_client()
        try:
            # First, validate that the token belongs to a real user
            user_result = await self.get_user(access_token)
            
            if user_result["success"]:
                # Token is valid, user exists - signout successful
                # Note: Actual token invalidation happens client-side in Supabase
                return {
                    "success": True,
                    "message": "User signed out successfully"
                }
            else:
                # Token is invalid/expired - but that's still a "successful" signout
                return {
                    "success": True,
                    "message": "Session already expired"
                }
                
        except Exception as e:
            # Even if there's an error, signout should generally succeed
            # to avoid leaving users in a "stuck" state
            return {
                "success": True,
                "message": "Sign out completed"
            }

    async def refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh user session using refresh token"""
        self._check_client()
        try:
            response = self.supabase.auth.refresh_session(refresh_token)
            return {
                "success": True,
                "user": response.user,
                "session": response.session
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def get_user(self, access_token: str) -> Dict[str, Any]:
        """Get user details from access token"""
        self._check_client()
        try:
            # Get user from JWT token directly
            response = self.supabase.auth.get_user(access_token)
            return {
                "success": True,
                "user": response.user
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def get_user_by_id(self, user_id: str) -> Dict[str, Any]:
        """Get user details by user ID"""
        self._check_client()
        try:
            response = self.supabase.table('auth.users').select('*').eq('id', user_id).execute()
            
            if response.data and len(response.data) > 0:
                return {
                    "success": True,
                    "user": response.data[0]
                }
            else:
                return {
                    "success": False,
                    "error": "User not found"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def update_user_metadata(self, user_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update user metadata (like subscription status)"""
        self._check_client()
        try:
            response = self.supabase.table('auth.users').update({
                "raw_user_meta_data": metadata
            }).eq('id', user_id).execute()
            
            return {
                "success": True,
                "data": response.data
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def get_user_by_email(self, email: str) -> Dict[str, Any]:
        """Check if user exists by email"""
        self._check_client()
        try:
            # Query auth.users table for user with this email
            response = self.supabase.table('auth.users').select('id, email, email_confirmed_at').eq('email', email).execute()
            
            if response.data and len(response.data) > 0:
                return {
                    "success": True,
                    "user": response.data[0]
                }
            else:
                return {
                    "success": False,
                    "error": "User not found"
                }
        except Exception as e:
            # If we can't check, err on the side of caution and say user doesn't exist
            return {
                "success": False,
                "error": str(e)
            }

    async def forgot_password(self, email: str) -> Dict[str, Any]:
        """Send password reset email"""
        self._check_client()
        try:
            print(f"Attempting to send password reset email to: {email}")
            
            # Supabase reset password email method
            from app.core.config import settings
            redirect_url = f"{settings.frontend_url}/reset-password"
            
            # Try different parameter approaches
            try:
                # Try with options parameter
                response = self.supabase.auth.reset_password_email(
                    email,
                    options={"redirect_to": redirect_url}
                )
            except TypeError:
                try:
                    # Try with direct parameters
                    response = self.supabase.auth.reset_password_email(
                        email,
                        redirect_url
                    )
                except TypeError:
                    # Try with just email
                    response = self.supabase.auth.reset_password_email(email)
            
            print(f"Supabase response: {response}")
            
            return {
                "success": True,
                "message": "Password reset email sent successfully",
                "response": response
            }
            
        except Exception as e:
            print(f"Error in forgot_password service: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def reset_password(self, access_token: str, new_password: str) -> Dict[str, Any]:
        """Reset user password using access token from reset email"""
        self._check_client()
        try:
            # First verify the token is valid
            user_result = await self.get_user(access_token)
            if not user_result["success"]:
                return {
                    "success": False,
                    "error": "Invalid or expired reset token"
                }
            
            # Set the session with the access token
            self.supabase.auth.set_session(access_token, "")
            
            # Update the password
            response = self.supabase.auth.update_user({"password": new_password})
            
            return {
                "success": True,
                "message": "Password updated successfully",
                "user": response.user
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# Create a singleton instance
supabase_service = SupabaseService() 