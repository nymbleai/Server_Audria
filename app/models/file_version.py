from sqlalchemy import Column, String, Text, ForeignKey, Boolean, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .base import Base, TimestampMixin

class FileVersion(Base, TimestampMixin):
    __tablename__ = "file_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    blob_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    change_description = Column(Text, nullable=True)
    is_current = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    file = relationship("File", back_populates="versions") 