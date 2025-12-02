from sqlalchemy import Column, String, Integer, Float, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from .base import Base, TimestampMixin

class FeatureType(str, enum.Enum):
    """Feature types for usage tracking"""
    INGESTION = "ingestion"
    REVISION = "revision"
    ORCHESTRATOR = "orchestrator"
    CHAT = "chat"
    PRECEDENT_SEARCH = "precedent_search"
    PRECEDENT_EMBED = "precedent_embed"

class UsageLog(Base, TimestampMixin):
    """Tracks every request and computes its token and dollar cost"""
    __tablename__ = "usage_log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    supabase_user_id = Column(String, nullable=False, index=True)  # References user in Supabase
    feature_used = Column(SQLEnum(FeatureType), nullable=False)  # Chat, Inline Revision, Orchestrator, Ingestion
    tokens_used = Column(Integer, nullable=False)  # Tokens consumed in request
    dollar_cost = Column(Float, nullable=False)  # Dollar cost of the request
    prompt_tokens = Column(Integer, nullable=True)  # Input tokens
    completion_tokens = Column(Integer, nullable=True)  # Output tokens
    status = Column(String(20), nullable=True)  # SUCCESS | FAILED | TIMEOUT
    latency_ms = Column(Integer, nullable=True)  # Total duration in milliseconds
    model_used = Column(String(255), nullable=True)  # Model name used
    project_id = Column(String(64), nullable=True)  # Project linkage (string to avoid FK complexity)
    file_id = Column(String(64), nullable=True)  # File linkage (string to avoid FK complexity)
    
    # Optional metadata for tracking
    request_id = Column(String(255), nullable=True)  # Job ID or request identifier
    meta_data = Column(String, nullable=True)  # Additional metadata as JSON string

