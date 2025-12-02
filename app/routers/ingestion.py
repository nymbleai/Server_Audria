from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.ingestion import IngestionRequest, IngestionResponse, JobStatusResponse, JobFilesResponse
from app.schemas.auth import TokenData
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.job_timeout import job_timeout_registry
from app.core.database import get_db
from app.core.billing_middleware import check_billing_limit, log_billing_usage
from app.services.ingestion_file_service import ingestion_file_service
from app.models.usage_log import FeatureType
from app.utils.utils import get_all_keys
import httpx
import logging
from typing import Iterator, Dict, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/parse", response_model=IngestionResponse)
async def parse_document(
    request: IngestionRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Parse a document using the external ingestion agent.
    
    This endpoint acts as a pass-through to the ingestion agent API,
    forwarding the request and returning the response.
    """
    try:
        # Log the incoming request
        logger.info(f"🔄 INGESTION parse request from user {current_user.user_id}")
        logger.info(f"   Document name: {request.document_name}")
        logger.info(f"   HTML content length: {len(request.html_content)} characters")
        
        # Billing check: Estimate tokens based on content length (rough estimate: 1 token ≈ 4 chars)
        estimated_tokens = len(request.html_content) // 4
        logger.info(f"   Estimated tokens: {estimated_tokens}")
        
        # Check subscription limit (handled by outer HTTPException catch)
        await check_billing_limit(
            db,
            current_user.user_id,
            FeatureType.INGESTION,
            estimated_tokens
        )
        
        # Prepare the payload for the external API
        # NOTE: project_id and file_id are for internal tracking only, not sent to external API
        payload = {
            "html_content": request.html_content,
            "document_name": request.document_name
        }
        
        # Make the external API call
        async with httpx.AsyncClient(timeout=settings.ingestion_api_timeout) as client:
            response = await client.post(
                f"{settings.ingestion_api_url}/parse",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Ingestion API successful: job_id={response_data.get('job_id')}")
                # Register job total-time budget
                job_id = response_data.get('job_id')
                if job_id:
                    job_timeout_registry.register_job(
                        "ingestion",
                        job_id,
                        settings.ingestion_api_timeout,
                        project_id=getattr(request, 'project_id', None),
                        file_id=getattr(request, 'file_id', None)
                    )
                
                # Return the response using our schema
                return IngestionResponse(**response_data)
            else:
                # Log the error and raise HTTPException
                error_detail = f"Ingestion API failed with status {response.status_code}: {response.text}"
                logger.error(f"❌ {error_detail}")
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
                
    except httpx.TimeoutException:
        error_msg = "Ingestion API request timed out"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=error_msg
        )
    except httpx.HTTPError as e:
        error_msg = f"HTTP error occurred: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )
    except HTTPException as e:
        # Format limit reached errors consistently
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
        # Preserve other HTTP errors
        raise e
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the status of an ingestion job.
    
    This endpoint acts as a pass-through to the ingestion agent API,
    forwarding the job status request and returning the response.
    """
    try:
        # Log the incoming request
        logger.info(f"🔍 INGESTION job status request from user {current_user.user_id}")
        logger.info(f"   Job ID: {job_id}")
        
        # Enforce total-time budget
        if job_timeout_registry.is_timed_out("ingestion", job_id):
            logger.error(f"❌ Ingestion job timed out by total budget: {job_id}")
            # Log timeout
            try:
                from app.crud.usage_log import usage_log as usage_log_crud
                if not await usage_log_crud.exists_by_request_id(db, current_user.user_id, FeatureType.INGESTION, job_id):
                    latency_ms = job_timeout_registry.get_latency_ms("ingestion", job_id)
                    await log_billing_usage(
                        db,
                        current_user.user_id,
                        FeatureType.INGESTION,
                        0,
                        request_id=job_id,
                        latency_ms=latency_ms,
                        meta_data=json.dumps({"error": "timeout"}),
                        status='TIMEOUT',
                        project_id=job_timeout_registry.get_project_and_file("ingestion", job_id)[0],
                        file_id=job_timeout_registry.get_project_and_file("ingestion", job_id)[1]
                    )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Ingestion job {job_id} exceeded total timeout of {settings.ingestion_api_timeout}s"
            )

        # Make the external API call
        async with httpx.AsyncClient(timeout=settings.ingestion_api_timeout) as client:
            response = await client.get(
                f"{settings.ingestion_api_url}/job/{job_id}",
                headers={"Content-Type": "application/json"}
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Job status API successful: status={response_data.get('status')}")
                
                # If completed, update usage log with actual tokens BEFORE removing from registry
                if response_data.get('status') == 'completed':
                    try:
                        # Get latency from job_timeout_registry BEFORE removing
                        latency_ms = job_timeout_registry.get_latency_ms("ingestion", job_id)
                        proj_id, f_id = job_timeout_registry.get_project_and_file("ingestion", job_id)
                        
                        token_usage = (response_data or {}).get('token_usage') or {}
                        actual_tokens = token_usage.get('total_tokens')
                        if actual_tokens is None:
                            actual_tokens = 0
                            logger.warning("Ingestion token usage missing at completion for job %s; stored 0", job_id)
                        
                        # Extract model_used from response
                        model_used = response_data.get('results', {}).get('summary', {}).get('model_used') or 'UNKNOWN'
                        logger.info(f"🔍[INGESTION] Results Summary: {response_data.get('results', {}).get('summary', {})}")
                        
                        # Update or create usage log (will update existing PENDING entry or create new one)
                        await log_billing_usage(
                            db,
                            current_user.user_id,
                            FeatureType.INGESTION,
                            int(actual_tokens),
                            request_id=job_id,
                            latency_ms=latency_ms,
                            model_used=model_used,
                            meta_data=json.dumps({"job_status_logging": True}),
                            prompt_tokens=token_usage.get('prompt_tokens'),
                            completion_tokens=token_usage.get('completion_tokens'),
                            status='SUCCESS',
                            project_id=proj_id,
                            file_id=f_id
                        )
                    except Exception as e:
                        logger.warning("Ingestion completion logging failed for job %s: %s", job_id, str(e))
                
                # Remove completed/failed/error jobs from timeout registry AFTER logging
                if response_data.get('status') in ['completed', 'failed', 'error']:
                    job_timeout_registry.remove_job("ingestion", job_id)
                
                # Return the response using our schema
                return JobStatusResponse(**response_data)
            elif response.status_code == 404:
                # Job not found
                logger.warning(f"❌ Job not found: {job_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job with ID {job_id} not found"
                )
            else:
                # Other error
                error_detail = f"Ingestion API failed with status {response.status_code}: {response.text}"
                logger.error(f"❌ {error_detail}")
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
                
    except httpx.TimeoutException:
        error_msg = "Ingestion API request timed out"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=error_msg
        )
    except httpx.HTTPError as e:
        error_msg = f"HTTP error occurred: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )
    except HTTPException as e:
        # Preserve intended HTTP errors
        raise e
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@router.get("/job/{job_id}/files", response_model=JobFilesResponse)
async def get_job_files(
    job_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get the file information for an ingestion job.
    
    This endpoint acts as a pass-through to the ingestion agent API,
    forwarding the job files request and returning the response.
    """
    try:
        # Log the incoming request
        logger.info(f"📁 INGESTION job files request from user {current_user.user_id}")
        logger.info(f"   Job ID: {job_id}")
        
        # Enforce total-time budget
        if job_timeout_registry.is_timed_out("ingestion", job_id):
            logger.error(f"❌ Ingestion job timed out by total budget (files): {job_id}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Ingestion job {job_id} exceeded total timeout of {settings.ingestion_api_timeout}s"
            )

        # Make the external API call
        async with httpx.AsyncClient(timeout=settings.ingestion_api_timeout) as client:
            response = await client.get(
                f"{settings.ingestion_api_url}/job/{job_id}/files",
                headers={"Content-Type": "application/json"}
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Job files API successful: {response_data.get('total_files', 0)} files found")
                
                # Return the response using our schema
                return JobFilesResponse(**response_data)
            elif response.status_code == 404:
                # Job not found
                logger.warning(f"❌ Job not found: {job_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job with ID {job_id} not found"
                )
            else:
                # Other error
                error_detail = f"Ingestion API failed with status {response.status_code}: {response.text}"
                logger.error(f"❌ {error_detail}")
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
                
    except httpx.TimeoutException:
        error_msg = "Ingestion API request timed out"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=error_msg
        )
    except httpx.HTTPError as e:
        error_msg = f"HTTP error occurred: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )
    except HTTPException as e:
        # Preserve intended HTTP errors
        raise e
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        ) 

@router.get("/job/{job_id}/download/{file_type}")
async def download_job_file(
    job_id: str,
    file_type: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Download a specific file from an ingestion job by file type.
    
    Available file types:
    - chunks_csv: Original document chunks
    - structure_extraction_json: Document structure
    - non_clauses_json: Non-clause elements
    - cross_references_json: Cross-references
    - defined_terms_json: Defined terms
    - sections_chapters_csv: Sections and chapters
    - structural_elements_csv: Structural elements
    - xrefs_csv: Cross-references table
    - definitions_csv: Definitions table
    """
    try:
        # Log the incoming request
        logger.info(f"📥 INGESTION file download request from user {current_user.user_id}")
        logger.info(f"   Job ID: {job_id}")
        logger.info(f"   File type: {file_type}")
        
        # Enforce total-time budget
        if job_timeout_registry.is_timed_out("ingestion", job_id):
            logger.error(f"❌ Ingestion job timed out by total budget (download): {job_id}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Ingestion job {job_id} exceeded total timeout of {settings.ingestion_api_timeout}s"
            )

        # Make the external API call
        async with httpx.AsyncClient(timeout=settings.ingestion_api_timeout) as client:
            response = await client.get(
                f"{settings.ingestion_api_url}/job/{job_id}/download/{file_type}",
                headers={"accept": "application/json"}
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                # Get the filename from the response headers or generate one
                content_disposition = response.headers.get('content-disposition', '')
                if 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[1].strip('"')
                else:
                    # Generate filename based on file type
                    file_extension = 'csv' if file_type.endswith('_csv') else 'json'
                    filename = f"{job_id}_{file_type}.{file_extension}"
                
                # Determine content type
                content_type = "text/csv" if file_type.endswith('_csv') else "application/json"
                
                logger.info(f"✅ File download successful: {filename}")
                
                # Create an iterator for the file content
                def iter_content() -> Iterator[bytes]:
                    yield response.content
                
                # Return the file as a streaming response
                return StreamingResponse(
                    iter_content(),
                    media_type=content_type,
                    headers={
                        "Content-Disposition": f"attachment; filename={filename}",
                        "Content-Length": str(len(response.content))
                    }
                )
            elif response.status_code == 404:
                # Job or file not found
                logger.warning(f"❌ Job or file not found: job_id={job_id}, file_type={file_type}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job with ID {job_id} or file type {file_type} not found"
                )
            else:
                # Other error
                error_detail = f"Ingestion API failed with status {response.status_code}: {response.text}"
                logger.error(f"❌ {error_detail}")
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
                
    except httpx.TimeoutException:
        error_msg = "Ingestion API request timed out"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=error_msg
        )
    except httpx.HTTPError as e:
        error_msg = f"HTTP error occurred: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )
    except HTTPException as e:
        # Preserve intended HTTP errors
        raise e
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        ) 

@router.post("/job/{job_id}/store-files")
async def store_job_files_locally(
    job_id: str,
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Download and store all ingestion job files locally to the mounted volume.
    
    This endpoint downloads all available files from the ingestion job and stores them
    in the persistent volume at /app/data/ingestion_files/{job_id}/
    """
    try:
        logger.info(f"💾 INGESTION store files request from user {current_user.user_id}")
        logger.info(f"   Job ID: {job_id}")
        
        # Download all files for the job
        download_results = await ingestion_file_service.download_all_job_files(job_id)
        
        # Count successful downloads
        successful_downloads = sum(1 for path in download_results.values() if path is not None)
        failed_downloads = sum(1 for path in download_results.values() if path is None)
        
        # List all stored files
        stored_files = ingestion_file_service.list_job_files(job_id)
        
        logger.info(f"✅ Stored {successful_downloads} files for job {job_id}")
        
        return {
            "success": True,
            "job_id": job_id,
            "download_results": download_results,
            "summary": {
                "total_attempted": len(download_results),
                "successful_downloads": successful_downloads,
                "failed_downloads": failed_downloads
            },
            "stored_files": stored_files,
            "storage_location": f"/app/data/ingestion_files/{job_id}/"
        }
        
    except Exception as e:
        error_msg = f"Failed to store files for job {job_id}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/job/{job_id}/stored-files")
async def list_stored_files(
    job_id: str,
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    List all locally stored files for a specific ingestion job.
    """
    try:
        logger.info(f"📁 INGESTION list stored files from user {current_user.user_id}")
        logger.info(f"   Job ID: {job_id}")
        
        stored_files = ingestion_file_service.list_job_files(job_id)
        
        return {
            "success": True,
            "job_id": job_id,
            "stored_files": stored_files,
            "total_files": len(stored_files),
            "storage_location": f"/app/data/ingestion_files/{job_id}/"
        }
        
    except Exception as e:
        error_msg = f"Failed to list stored files for job {job_id}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        ) 