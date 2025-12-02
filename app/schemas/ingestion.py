from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class IngestionRequest(BaseModel):
    """Schema for ingestion API request"""
    html_content: str
    document_name: str
    # Traceability context
    project_id: Optional[str] = None
    file_id: Optional[str] = None

class IngestionResponse(BaseModel):
    """Schema for ingestion API response"""
    job_id: str
    status: str
    message: str
    created_at: datetime

# Job Status Response Schemas
class ExtractedData(BaseModel):
    """Schema for extracted data within each chunk"""
    data: List[Dict[str, Any]]

class ChunkExtractionResult(BaseModel):
    """Schema for extraction result of a single chunk"""
    chunk_id: str
    extracted_data: ExtractedData
    schema_validated: bool

class CsvDataSection(BaseModel):
    """Schema for CSV data sections"""
    count: int
    data: List[Dict[str, Any]]
    truncated: bool

class CsvData(BaseModel):
    """Schema for CSV data structure"""
    sections_chapters: CsvDataSection
    structural_elements: CsvDataSection
    xrefs: CsvDataSection
    definitions: CsvDataSection

class ResultsSummary(BaseModel):
    """Schema for extraction results summary"""
    total_extractions: int
    chunk_count: int
    model_used: str
    prompts_used: List[str]

class ExtractionResults(BaseModel):
    """Schema for extraction results"""
    structure_extraction: List[ChunkExtractionResult]
    non_clauses: List[ChunkExtractionResult]
    cross_references: List[ChunkExtractionResult]
    defined_terms: List[ChunkExtractionResult]
    csv_data: CsvData
    summary: ResultsSummary

class JobStatusResponse(BaseModel):
    """Schema for job status response"""
    job_id: str
    status: str
    document_name: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time: Optional[float] = None
    chunk_count: Optional[int] = None
    progress: Optional[str] = None
    results: Optional[ExtractionResults] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    available_files: Optional[List[str]] = None
    file_contents: Optional[Dict[str, Any]] = None

class FileInfo(BaseModel):
    """Schema for individual file information"""
    filename: str
    file_type: str
    size_bytes: int
    description: str

class JobFilesResponse(BaseModel):
    """Schema for job files response"""
    job_id: str
    total_files: int
    files: List[FileInfo] 