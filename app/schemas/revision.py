from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class RevisionRequest(BaseModel):
    """Request schema for revision processing"""
    clause: str
    user_instruction: str
    precedent: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "clause": "The Company shall indemnify and hold harmless each person who was or is a party to any proceeding...",
                "user_instruction": "Incorporate good faith requirement and update indemnification scope",
                "precedent": "Each person who was or is a party or is threatened to be made a party to any threatened, pending or completed action..."
            }
        }


class RevisionResponse(BaseModel):
    """Response schema for revision processing - flexible to handle various revision agent response formats"""
    # Make success optional and default it based on presence of other fields
    success: Optional[bool] = None
    
    # Common revision agent response fields (all optional to be flexible)
    action: Optional[str] = None
    revised_clause: Optional[str] = None
    original_clause: Optional[str] = None
    user_instruction: Optional[str] = None
    changes_made: Optional[str] = None
    explanation: Optional[str] = None
    error: Optional[str] = None
    
    # Allow any additional fields from the revision agent
    additional_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        extra = "allow"  # Allow extra fields from revision agent
        json_schema_extra = {
            "example": {
                "success": True,
                "action": "return_to_user",
                "revised_clause": "The Company shall, in good faith, indemnify and hold harmless...",
                "original_clause": "The Company shall indemnify and hold harmless...",
                "user_instruction": "Incorporate good faith requirement",
                "changes_made": "Added 'in good faith' clause to strengthen indemnification language",
                "explanation": "The revision incorporates a good faith requirement as requested..."
            }
        }
    
    def __init__(self, **data):
        # If success is not provided, infer it from the response
        if 'success' not in data:
            # Consider it successful if there's no error and we have content
            data['success'] = 'error' not in data and (
                'revised_clause' in data or 
                'action' in data or
                any(key for key in data.keys() if key not in ['error'])
            )
        super().__init__(**data)


class RevisionProcessRequest(BaseModel):
    """Schema for synchronous revision processing"""
    clause: str
    user_instruction: str
    precedent: Optional[str] = None
    revision_prompt: Optional[str] = None  # Custom system prompt when user enables editing
    revision_model: Optional[str] = "gpt-4o-2024-08-06"  # AI model selection
    use_reflection: Optional[bool] = None  # Toggle reflection behavior in revision agent
    evaluation_prompt: Optional[str] = None  # Prompt for evaluation
    # Traceability context
    project_id: Optional[str] = None
    file_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "clause": "The contractor agrees to provide services as specified",
                "user_instruction": "Add liability limitations and indemnification clauses",
                "precedent": "Standard professional services agreement language",
                "revision_prompt": "You are an AI assistant that specializes in legal document revision...",
                "revision_model": "gpt-4o-2024-08-06",
                "use_reflection":  True,
                "evaluation_prompt": "You are an AI assistant that specializes in reflection..."
            }
        } 