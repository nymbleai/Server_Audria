from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import httpx
import logging
import json

from app.schemas.orchestrator import OrchestratorRequest, OrchestratorFileRequest, JobContinuationRequest
from app.schemas.auth import TokenData
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.billing_middleware import check_billing_limit, log_billing_usage
from app.models.usage_log import FeatureType
from app.services.orchestrator_service import orchestrator_service
from app.core.job_timeout import job_timeout_registry
from app.utils.utils import get_all_keys

logger = logging.getLogger(__name__)
router = APIRouter()

# Testing mode - disable authentication
TESTING_MODE = False  # Set to False in production

def get_auth_dependency():
    """Conditionally return authentication dependency based on testing mode"""
    if TESTING_MODE:
        return None
    return Depends(get_current_user)

@router.post("/process")
async def process_json(
    request: OrchestratorRequest,
    current_user: Optional[TokenData] = get_auth_dependency(),
    db: Optional[AsyncSession] = Depends(get_db)
):
    """Process document with JSON data using new OrchestratorRequest schema"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Billing check (only if not in testing mode)
        if not TESTING_MODE and current_user and db:
            # Estimate tokens based on user instruction and document length
            estimated_tokens = len(request.user_instruction) // 4
            estimated_tokens += len(request.document) // 4 if request.document else 0
            
            try:
                await check_billing_limit(
                    db,
                    current_user.user_id,
                    FeatureType.ORCHESTRATOR,
                    estimated_tokens
                )
            except HTTPException as e:
                if e.status_code == status.HTTP_402_PAYMENT_REQUIRED:
                    detail = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
                    return JSONResponse(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        content=jsonable_encoder({
                            "success": False,
                            "error": "limit_reached",
                            "message": detail.get("message", "Token limit reached for this billing period"),
                            "tokens_remaining": detail.get("tokens_remaining"),
                            "subscription": detail.get("subscription"),
                            "tier": detail.get("tier")
                        })
                    )
                raise
        
        # Send the request data directly to the external orchestrator
        start_time = __import__('datetime').datetime.utcnow()
        request_data = request.model_dump(exclude_none=True)
        logger.info(f"[ORCHESTRATOR] Sending request data: {request_data}")
        result = await orchestrator_service.proxy_request(
            "POST", "/process", 
            json=request_data, 
            headers=orchestrator_service._get_headers()
        )
        # Register total-time budget by returned job_id if present
        job_id_value = result.get("job_id") if isinstance(result, dict) else None
        if job_id_value:
            job_timeout_registry.register_job(
                "orchestrator",
                job_id_value,
                settings.orchestrator_timeout,
                project_id=getattr(request, 'project_id', None),
                file_id=getattr(request, 'file_id', None)
            )
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")

@router.post("/process-files")
async def process_files(
    user_instruction: str = Form(...),
    document: str = Form(...),
    marked_clause: Optional[str] = Form(None),
    precedent: Optional[str] = Form(None),
    model_name: str = Form("o4-mini-2025-04-16"),
    always_plan_first: bool = Form(False),
    # File uploads - these are now optional based on your schema
    chunks_csv_file: Optional[UploadFile] = File(None),
    structure_json_file: Optional[UploadFile] = File(None),
    cross_references_json_file: Optional[UploadFile] = File(None),
    sections_csv_file: Optional[UploadFile] = File(None),
    xrefs_csv_file: Optional[UploadFile] = File(None),
    metadata_json_file: Optional[UploadFile] = File(None),
    current_user: Optional[TokenData] = get_auth_dependency()
):
    """Process document with file uploads using new OrchestratorFileRequest schema"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Build files dict only for files that were actually uploaded
        files = {}
        if chunks_csv_file:
            files['chunks_csv_file'] = await chunks_csv_file.read()
        if structure_json_file:
            files['structure_json_file'] = await structure_json_file.read()
        if cross_references_json_file:
            files['cross_references_json_file'] = await cross_references_json_file.read()
        if sections_csv_file:
            files['sections_csv_file'] = await sections_csv_file.read()
        if xrefs_csv_file:
            files['xrefs_csv_file'] = await xrefs_csv_file.read()
        if metadata_json_file:
            files['metadata_json_file'] = await metadata_json_file.read()
        
        # Build data dict with required fields
        data = {
            'user_instruction': user_instruction,
            'document': document,
            'model_name': model_name,
            'always_plan_first': str(always_plan_first).lower()
        }
        
        # Add optional fields only if they have values
        if marked_clause:
            data['marked_clause'] = marked_clause
        if precedent:
            data['precedent'] = precedent
        
        result = await orchestrator_service.proxy_request(
            "POST", "/process-files", 
            files=files, 
            data=data
        )
        job_id_value = result.get("job_id") if isinstance(result, dict) else None
        if job_id_value:
            job_timeout_registry.register_job("orchestrator", job_id_value, settings.orchestrator_timeout)
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")

@router.get("/job/{job_id}")
async def get_job(
    job_id: str, 
    current_user: Optional[TokenData] = get_auth_dependency(),
    db: Optional[AsyncSession] = Depends(get_db)
):
    """Get job status"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Enforce total-time budget
        if job_timeout_registry.is_timed_out("orchestrator", job_id):
            # Log timeout
            if current_user and db:
                try:
                    from app.crud.usage_log import usage_log as usage_log_crud
                    if not await usage_log_crud.exists_by_request_id(db, current_user.user_id, FeatureType.ORCHESTRATOR, job_id):
                        latency_ms = job_timeout_registry.get_latency_ms("orchestrator", job_id)
                        await log_billing_usage(
                            db,
                            current_user.user_id,
                            FeatureType.ORCHESTRATOR,
                            0,
                            request_id=job_id,
                            latency_ms=latency_ms,
                            meta_data=json.dumps({"error": "timeout"}),
                            status='TIMEOUT',
                            project_id=job_timeout_registry.get_project_and_file("orchestrator", job_id)[0],
                            file_id=job_timeout_registry.get_project_and_file("orchestrator", job_id)[1]
                        )
                except Exception:
                    pass
            raise HTTPException(status_code=504, detail=f"Orchestrator job {job_id} exceeded total timeout of {settings.orchestrator_timeout}s")
        result = await orchestrator_service.proxy_request("GET", f"/job/{job_id}")
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")

@router.get("/job/{job_id}/logs")
async def get_job_logs(
    job_id: str, 
    current_user: Optional[TokenData] = get_auth_dependency()
):
    """Get job logs"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        if job_timeout_registry.is_timed_out("orchestrator", job_id):
            raise HTTPException(status_code=504, detail=f"Orchestrator job {job_id} exceeded total timeout of {settings.orchestrator_timeout}s")
        result = await orchestrator_service.proxy_request("GET", f"/job/{job_id}/logs")
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")

@router.get("/job/{job_id}/apply")
async def get_job_apply(
    job_id: str, 
    current_user: Optional[TokenData] = get_auth_dependency(),
    db: Optional[AsyncSession] = Depends(get_db)
):
    """Get job apply outputs"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    logger.info(f"🔍[ORCHESTRATOR] Getting job apply for job {job_id}")
    try:
        if job_timeout_registry.is_timed_out("orchestrator", job_id):
            raise HTTPException(status_code=504, detail=f"Orchestrator job {job_id} exceeded total timeout of {settings.orchestrator_timeout}s")
        result = await orchestrator_service.proxy_request("GET", f"/job/{job_id}")
        # When job finalizes, fetch aggregated token usage and log exactly once
        logger.info(f"🔍[ORCHESTRATOR] Result: {result}")
        if current_user and db:
            try:
                # Guard against duplicate inserts
                from app.crud.usage_log import usage_log as usage_log_crud
                if not await usage_log_crud.exists_by_request_id(db, current_user.user_id, FeatureType.ORCHESTRATOR, job_id):
                    # Get latency from job_timeout_registry BEFORE any potential removal
                    latency_ms = job_timeout_registry.get_latency_ms("orchestrator", job_id)
                    
                    # Preferred: aggregated token usage from /job/{job_id}
                    job_status = await orchestrator_service.proxy_request("GET", f"/job/{job_id}")
                    logger.info(f"🔍[ORCHESTRATOR] Job status: {job_status}")
                    token_usage = ((job_status or {}).get('orchestrator_logs') or {}).get('token_usage') or {}
                    actual_tokens = token_usage.get('total_tokens')
                    if actual_tokens is None:
                        # Fallback: try logs endpoint
                        logs = await orchestrator_service.proxy_request("GET", f"/job/{job_id}/logs")
                        token_usage = (((logs or {}).get('orchestrator_logs') or {}).get('token_usage')) or {}
                        actual_tokens = token_usage.get('total_tokens')
                    if actual_tokens is None:
                        actual_tokens = 0
                        logger.warning("Orchestrator token usage missing for job %s; stored 0", job_id)
                    
                    # Extract model_used from token_usage or job_status
                    model_used = token_usage.get('model_used') or token_usage.get('model') or token_usage.get('model_name') or 'UNKNOWN'
                    
                    await log_billing_usage(
                        db,
                        current_user.user_id,
                        FeatureType.ORCHESTRATOR,
                        int(actual_tokens or 0),
                        request_id=job_id,
                        latency_ms=latency_ms,
                        model_used=model_used,
                        prompt_tokens=token_usage.get('prompt_tokens'),
                        completion_tokens=token_usage.get('completion_tokens'),
                        status='SUCCESS' if (actual_tokens or 0) >= 0 else 'FAILED',
                        project_id=job_timeout_registry.get_project_and_file("orchestrator", job_id)[0],
                        file_id=job_timeout_registry.get_project_and_file("orchestrator", job_id)[1]
                    )
                    
                    # Remove from timeout registry AFTER logging
                    job_timeout_registry.remove_job("orchestrator", job_id)
            except Exception:
                pass
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")

@router.get("/job/{job_id}/download/{file_type}")
async def download_job_file(
    job_id: str, 
    file_type: str, 
    current_user: Optional[TokenData] = get_auth_dependency()
):
    """Download job file"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        if job_timeout_registry.is_timed_out("orchestrator", job_id):
            raise HTTPException(status_code=504, detail=f"Orchestrator job {job_id} exceeded total timeout of {settings.orchestrator_timeout}s")
        result = await orchestrator_service.proxy_request("GET", f"/job/{job_id}/download/{file_type}")
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")

@router.put("/job/{job_id}/continue")
async def continue_job(
    job_id: str, 
    request: JobContinuationRequest, 
    current_user: Optional[TokenData] = get_auth_dependency()
):
    """Continue job with user response using new JobContinuationRequest schema"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Send the request data directly to the external orchestrator
        result = await orchestrator_service.proxy_request(
            "PUT", f"/job/{job_id}/continue", 
            json=request.model_dump(exclude_none=True),
            headers=orchestrator_service._get_headers()
        )
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")

@router.get("/jobs")
async def list_jobs(current_user: Optional[TokenData] = get_auth_dependency()):
    """List all jobs"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        result = await orchestrator_service.proxy_request("GET", "/jobs")
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")

@router.delete("/job/{job_id}")
async def delete_job(
    job_id: str, 
    current_user: Optional[TokenData] = get_auth_dependency()
):
    """Delete job"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        result = await orchestrator_service.proxy_request("DELETE", f"/job/{job_id}")
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")

@router.get("/health")
async def health_check(current_user: Optional[TokenData] = get_auth_dependency()):
    """Health check"""
    # Skip auth check in testing mode
    if not TESTING_MODE and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        result = await orchestrator_service.proxy_request("GET", "/health")
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Orchestrator request timed out")