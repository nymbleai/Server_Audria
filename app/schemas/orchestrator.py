from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from fastapi import UploadFile

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# === PYDANTIC MODELS ===

class OrchestratorRequest(BaseModel):
    user_instruction: str = Field(..., description="User instruction for document revision")
    document: str = Field(..., description="Complete legal document text")
    marked_clause: Optional[str] = Field(None, description="Specific clause to revise (optional)")
    precedent: Optional[str] = Field(None, description="Legal precedent or context")
    model_name: str = Field("o4-mini-2025-04-16", description="AI model to use for processing")
    user_response: Optional[str] = Field(None, description="User response for interaction workflows (optional)")
    context: Optional[str] = Field(None, description="Additional context including chat history (optional)")
    always_plan_first: bool = Field(False, description="Always call the planner first before determining workflow")
    # Traceability context
    project_id: Optional[str] = Field(None, description="Project/Conversation ID for traceability")
    file_id: Optional[str] = Field(None, description="File ID for traceability")
    
    # Parser output files - can be file paths or direct content
    parser_outputs_dir: Optional[str] = Field(None, description="Directory containing parser outputs (e.g., 'parser_outputs_test') - not needed if providing content directly")
    
    # Content fields (for direct content submission)
    chunks_csv_file: Optional[str] = Field(None, description="Chunks CSV file name or CSV content directly")
    structure_json_file: Optional[str] = Field(None, description="Structure JSON file name or JSON content directly (as string)")  
    cross_references_json_file: Optional[str] = Field(None, description="Cross-references JSON file name or JSON content directly (as string)")
    sections_csv_file: Optional[str] = Field(None, description="Sections CSV file name or CSV content directly")
    xrefs_csv_file: Optional[str] = Field(None, description="Cross-references CSV file name or CSV content directly")
    metadata_json_file: Optional[str] = Field(None, description="Metadata JSON file name or JSON content directly (as string, optional)")

    @model_validator(mode='after')
    def validate_parser_inputs(self):
        """Validate parser inputs - all fields are optional per external API spec"""
        # Per external orchestrator API, all parser fields are optional
        # No validation needed - external service will handle validation
        return self

# New model for file upload support
class OrchestratorFileRequest(BaseModel):
    user_instruction: str = Field(..., description="User instruction for document revision")
    document: str = Field(..., description="Complete legal document text")
    marked_clause: Optional[str] = Field(None, description="Specific clause to revise (optional)")
    precedent: Optional[str] = Field(None, description="Legal precedent or context")
    model_name: str = Field("o4-mini-2025-04-16", description="AI model to use for processing")
    always_plan_first: bool = Field(False, description="Always call the planner first before determining workflow")
    # Traceability context
    project_id: Optional[str] = Field(None, description="Project/Conversation ID for traceability")
    file_id: Optional[str] = Field(None, description="File ID for traceability")

class OrchestratorResponse(BaseModel):
    job_id: str
    status: str
    message: str
    created_at: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    processing_time: Optional[float] = None
    progress: Optional[str] = None
    dev_logs: Optional[List[Dict[str, str]]] = None
    orchestrator_logs: Optional[Dict[str, Any]] = None
    apply_outputs: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    warnings: List[str] = []
    available_files: Optional[List[str]] = None
    # User interaction fields
    user_interaction_required: Optional[bool] = None
    questions_for_user: Optional[str] = None
    message_to_user: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    active_jobs: int
    timeout_configuration: Optional[Dict[str, Any]] = Field(None, description="API timeout configuration")

class JobContinuationRequest(BaseModel):
    user_response: str = Field(..., description="User response to continue the job")

# Keep backward compatibility for existing code
class ProcessJsonRequest(OrchestratorRequest):
    pass

class ContinueJobRequest(JobContinuationRequest):
    pass