from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class SearchClausesRequest(BaseModel):
    """Request schema for searching clauses"""
    query: str
    n_results: Optional[int] = 5
    min_words: Optional[int] = 5
    collection_name: Optional[str] = "precedents"
    chroma_db_path: Optional[str] = "./chroma_db"
    embedding_model: Optional[str] = "text-embedding-3-small"
    where_filter: Optional[Dict[str, Any]] = {}
    # Traceability context
    project_id: Optional[str] = None
    file_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "indemnification clause with good faith requirement",
                "n_results": 5,
                "min_words": 5,
                "collection_name": "precedents", 
                "chroma_db_path": "./chroma_db",
                "embedding_model": "text-embedding-3-small",
                "where_filter": {}
            }
        }


class SearchClausesResponse(BaseModel):
    """Response schema for clause search results"""
    results: List[Dict[str, Any]]
    query: str
    n_results: int
    total_found: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "id": "clause-123",
                        "text": "The Company shall indemnify and hold harmless...",
                        "similarity_score": 0.95,
                        "metadata": {
                            "document_name": "master_service_agreement.pdf",
                            "clause_type": "indemnification"
                        }
                    }
                ],
                "query": "indemnification clause",
                "n_results": 5,
                "total_found": 12
            }
        }


class EmbedJobStatusResponse(BaseModel):
    """Response schema for embed job status"""
    job_id: Optional[str] = None
    status: str
    document_name: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    processing_time: Optional[float] = None
    progress: Optional[str] = None
    errors: Optional[List[str]] = None  # ✅ Fixed: Now allows None values
    embedded_clause_count: Optional[int] = None
    chroma_collection: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    # Allow any additional fields from the external service
    class Config:
        extra = "allow"  # Allow extra fields from external service
        json_schema_extra = {
            "example": {
                "job_id": "embed-123-456",
                "status": "completed",
                "document_name": "contract_template.pdf",
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:05Z", 
                "completed_at": "2024-01-15T10:32:15Z",
                "processing_time": 130.5,
                "progress": "100%",
                "errors": None,
                "embedded_clause_count": 47,
                "chroma_collection": "legal_precedents",
                "result": {}
            }
        }


class EmbedPrecedentResponse(BaseModel):
    """Response schema for embed precedent endpoint"""
    status: str
    job_id: Optional[str] = None
    message: Optional[str] = None
    document_name: Optional[str] = None
    errors: Optional[List[str]] = None
    
    # Allow any additional fields from the external service
    class Config:
        extra = "allow"  # Allow extra fields from external service
        json_schema_extra = {
            "example": {
                "status": "started",
                "job_id": "embed-precedent-123-456",
                "message": "Precedent embedding job started successfully",
                "document_name": "contract_template.pdf",
                "errors": None
            }
        } 