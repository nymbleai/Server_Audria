from fastapi import HTTPException, status
from functools import wraps
from typing import Callable, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth import TokenData

class DatabaseError(HTTPException):
    """Custom exception for database errors"""
    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)

class NotFoundError(HTTPException):
    """Custom exception for not found errors"""
    def __init__(self, resource: str = "Resource"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found")

class ForbiddenError(HTTPException):
    """Custom exception for forbidden errors"""
    def __init__(self, detail: str = "Not authorized to access this resource"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

class ValidationError(HTTPException):
    """Custom exception for validation errors"""
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

def handle_database_errors(func: Callable) -> Callable:
    """Decorator to handle database errors"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            raise DatabaseError(f"Database operation failed: {str(e)}")
    return wrapper 