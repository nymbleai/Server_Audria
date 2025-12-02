from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, func, Boolean
from datetime import datetime

Base = declarative_base()

class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps to models"""
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)