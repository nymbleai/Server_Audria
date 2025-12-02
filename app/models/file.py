from sqlalchemy import Column, String, Text, ForeignKey, Boolean, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .base import Base, TimestampMixin

class File(Base, TimestampMixin):
    __tablename__ = "files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True, index=True)
    job_id = Column(String, nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    blob_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="files")
    category = relationship("Category", back_populates="files")
    versions = relationship("FileVersion", back_populates="file", cascade="all, delete-orphan") 