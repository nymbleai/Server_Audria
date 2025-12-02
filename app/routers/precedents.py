from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from app.schemas.precedent import EmbedPrecedentResponse, SearchClausesRequest, SearchClausesResponse, EmbedJobStatusResponse
from app.schemas.auth import TokenData
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.job_timeout import job_timeout_registry
from app.services.ingestion_file_service import ingestion_file_service
from typing import Optional
import httpx
import logging
import aiofiles
from pathlib import Path
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.billing_middleware import log_billing_usage
from app.models.usage_log import FeatureType
import json
from app.utils.utils import get_all_keys

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/search_clauses", response_model=SearchClausesResponse)
async def search_clauses(
    request: SearchClausesRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for clauses using the external precedent service.
    
    This endpoint acts as a pass-through to the precedent service API,
    forwarding the search request and returning the results.
    """
    try:
        # Log the incoming request
        logger.info(f"🔍 PRECEDENT search clauses request from user {current_user.user_id}")
        logger.info(f"   Query: {request.query}")
        logger.info(f"   Collection: {request.collection_name}")
        logger.info(f"   Max results: {request.n_results}")
        logger.info(f"   Where filter: {request.where_filter}")
        
        # Prepare the payload for the external API (preserve None as null)
        payload = {
            "query": request.query,
            "n_results": request.n_results,
            "min_words": request.min_words,
            "collection_name": request.collection_name,
            "chroma_db_path": request.chroma_db_path,
            "embedding_model": request.embedding_model,
            "where_filter": request.where_filter  # ✅ Keep None as None, don't convert to {}
        }
        
        # Log what we're sending to external API
        logger.info(f"🌐 Sending to external API: {settings.precedent_retrieval_api_url}/search_clauses")
        logger.info(f"📋 Payload: {payload}")
        
        # Make the external API call
        start_time = datetime.utcnow()
        async with httpx.AsyncClient(timeout=settings.precedent_retrieval_api_timeout) as client:
            response = await client.post(
                f"{settings.precedent_retrieval_api_url}/search_clauses",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Precedent search API successful")
                logger.info(f"   Found results: {len(response_data.get('results', []))}")
                logger.info(f"   External API response keys: {list(response_data.keys())}")
                
                # Build response compatible with our schema
                # External API returns: {"results": [...], "count": 5}  
                # Our schema expects: {"results": [...], "query": "...", "n_results": 5, "total_found": 5}
                formatted_response = {
                    "results": response_data.get("results", []),
                    "query": request.query,  # ✅ Add from original request
                    "n_results": request.n_results,  # ✅ Add from original request  
                    "total_found": response_data.get("count")  # ✅ Map "count" to "total_found"
                }
                
                # Log usage (tokens are minimal; approximate by query length)
                try:
                    latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    actual_tokens = response_data.get('token_usage', {}).get('total_tokens')
                    if actual_tokens is None:
                        actual_tokens = 0
                        logger.warning("Precedent search token usage missing; stored 0. Keys present: %s", list(response_data.keys()))
                    
                    prompt_tokens = response_data.get('token_usage', {}).get('prompt_tokens')
                    completion_tokens = response_data.get('token_usage', {}).get('completion_tokens')
                    model_used = payload.get('embedding_model') or 'UNKNOWN'

                    all_keys = get_all_keys(response_data)
                    logger.info(f"🔍[PRECEDENT_SEARCH] All Nested Keys: {all_keys}")
                    await log_billing_usage(
                        db,
                        current_user.user_id,
                        FeatureType.PRECEDENT_SEARCH,
                        tokens_used=actual_tokens,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        request_id=None,
                        meta_data=json.dumps({"query": request.query, "collection": request.collection_name}),
                        latency_ms=latency_ms,
                        model_used=model_used or 'UNKNOWN',
                        status='SUCCESS',
                        project_id=getattr(request, 'project_id', None),
                        file_id=getattr(request, 'file_id', None)
                    )
                except Exception:
                    pass
                return SearchClausesResponse(**formatted_response)
            else:
                # Log the error and raise HTTPException
                error_detail = f"Precedent search API failed with status {response.status_code}: {response.text}"
                logger.error(f"❌ {error_detail}")
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
                
    except httpx.TimeoutException:
        error_msg = "Precedent search API request timed out"
        logger.error(f"❌ {error_msg}")
        # Log timeout with status='TIMEOUT'
        try:
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000) if 'start_time' in locals() else None
            await log_billing_usage(
                db,
                current_user.user_id,
                FeatureType.PRECEDENT_SEARCH,
                0,
                request_id=None,
                meta_data=json.dumps({"error": "timeout", "query": request.query}),
                latency_ms=latency_ms,
                status='TIMEOUT'
            )
        except Exception:
            pass
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
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"❌ Exception type: {type(e).__name__}")
        logger.error(f"❌ Exception args: {e.args}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/embed_job/{job_id}", response_model=EmbedJobStatusResponse)
async def get_embed_job_status(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the status of an embed job using the external precedent service.
    
    This endpoint acts as a pass-through to the precedent service API,
    forwarding the request and returning the response.
    """
    try:
        # Log the incoming request
        logger.info(f"🔄 PRECEDENT embed job status request from user {current_user.user_id}")
        logger.info(f"   Job ID: {job_id}")
        
        # Enforce total-time budget
        if job_timeout_registry.is_timed_out("precedent", job_id):
            logger.error(f"❌ Precedent embed job timed out by total budget: {job_id}")
            # Log timeout
            try:
                from app.crud.usage_log import usage_log as usage_log_crud
                if not await usage_log_crud.exists_by_request_id(db, current_user.user_id, FeatureType.PRECEDENT_EMBED, job_id):
                    latency_ms = job_timeout_registry.get_latency_ms("precedent", job_id)
                    await log_billing_usage(
                        db,
                        current_user.user_id,
                        FeatureType.PRECEDENT_EMBED,
                        0,
                        request_id=job_id,
                        latency_ms=latency_ms,
                        meta_data=json.dumps({"error": "timeout"}),
                        status='TIMEOUT',
                        project_id=job_timeout_registry.get_project_and_file("precedent", job_id)[0],
                        file_id=job_timeout_registry.get_project_and_file("precedent", job_id)[1]
                    )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Precedent embed job {job_id} exceeded total timeout of {settings.precedent_retrieval_api_timeout}s"
            )

        # Make the external API call
        async with httpx.AsyncClient(timeout=settings.precedent_retrieval_api_timeout) as client:
            response = await client.get(
                f"{settings.precedent_retrieval_api_url}/embed_job/{job_id}",
                headers={"Accept": "application/json"}
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Precedent API successful")
                logger.info(f"   Job status: {response_data.get('status')}")
                logger.info(f"   Progress: {response_data.get('progress')}")
                
                # If completed, log actual tokens (idempotent by request_id)
                if response_data.get('status') == 'completed':
                    try:
                        from app.crud.usage_log import usage_log as usage_log_crud
                        exists = await usage_log_crud.exists_by_request_id(
                            db=db,
                            user_id=current_user.user_id,
                            feature_type=FeatureType.PRECEDENT_EMBED,
                            request_id=job_id
                        )
                        if not exists:
                            # Get latency from job_timeout_registry BEFORE removing
                            latency_ms = job_timeout_registry.get_latency_ms("precedent", job_id)
                            proj_id, f_id = job_timeout_registry.get_project_and_file("precedent", job_id)
                            
                            token_usage = ((response_data or {}).get('token_usage') or {}).get('embedding_token_usage') or {}
                            actual_tokens = token_usage.get('total_tokens')
                            if actual_tokens is None:
                                actual_tokens = 0
                                logger.warning("Precedent embed token usage missing at completion for job %s; stored 0", job_id)
                            
                            all_keys = get_all_keys(response_data)
                            logger.info(f"🔍[PRECEDENT_EMBED] All Nested Keys: {all_keys}")
                            logger.info(f"🔍[PRECEDENT_EMBED] Response Data: {response_data}")
                            
                            model_used = token_usage.get('model_used') or response_data.get('embedding_model') or 'UNKNOWN'
                            
                            await log_billing_usage(
                                db,
                                current_user.user_id,
                                FeatureType.PRECEDENT_EMBED,
                                int(actual_tokens),
                                request_id=job_id,
                                latency_ms=latency_ms,
                                model_used=model_used,
                                meta_data=json.dumps({
                                    "document_name": response_data.get('document_name'),
                                    "collection": response_data.get('collection_name'),
                                    "clauses_embedded": response_data.get('clauses_embedded', 0)
                                }),
                                prompt_tokens=token_usage.get('prompt_tokens'),
                                completion_tokens=token_usage.get('completion_tokens'),
                                status='SUCCESS',
                                project_id=proj_id,
                                file_id=f_id
                            )
                    except Exception as e:
                        logger.warning("Precedent embed completion logging failed for job %s: %s", job_id, str(e))
                
                # Remove completed/failed/error jobs from timeout registry AFTER logging
                if response_data.get('status') in ['completed', 'failed', 'error']:
                    job_timeout_registry.remove_job("precedent", job_id)
                
                # Return the response using our schema
                return EmbedJobStatusResponse(**response_data)
            else:
                # Log the error and raise HTTPException
                error_detail = f"Precedent API failed with status {response.status_code}: {response.text}"
                logger.error(f"❌ {error_detail}")
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
                
    except httpx.TimeoutException:
        error_msg = "Precedent API request timed out"
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
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.post("/embed_precedent", response_model=EmbedPrecedentResponse)
async def embed_precedent(
    # Required parameters
    job_id: str = Form(..., description="Ingestion job ID to load files from"),
    document_name: str = Form(..., description="Name of the document for reference in the DB"),
    collection_name: str = Form(..., description="ChromaDB collection name"),
    
    # Optional parameters
    document_id: Optional[str] = Form(None, description="Optional document ID for DB storage"),
    use_filtered_extraction: bool = Form(True, description="Use filtered extraction from chunks if available"),
    force_re_embed: bool = Form(False, description="Force re-embedding even if clauses exist"),
    embedding_model: str = Form("text-embedding-3-small", description="OpenAI embedding model to use"),
    chroma_db_path: str = Form("./chroma_db", description="Path to ChromaDB storage"),
    
    current_user: TokenData = Depends(get_current_user)
):
    """
    Embed extracted clauses into ChromaDB using files from a completed ingestion job.
    
    This endpoint loads the required files (structure_json, sections_csv, chunks_csv) 
    from the local storage based on the provided job_id, then forwards them to the 
    external precedent service API.
    """
    try:
        # Log the incoming request
        logger.info(f"📤 PRECEDENT embed request from user {current_user.user_id}")
        logger.info(f"   Job ID: {job_id}")
        logger.info(f"   Document: {document_name}")
        logger.info(f"   Collection: {collection_name}")
        
        # Required file types to load from local storage
        required_files = {
            "structure_json": "structure_extraction_json",
            "sections_csv": "sections_chapters_csv", 
            "chunks_csv": "chunks_csv"
        }
        
        # Load files from local storage
        files = {}
        missing_files = []
        
        for form_name, file_type in required_files.items():
            local_path = ingestion_file_service.get_local_file_path(job_id, file_type)
            
            if local_path and Path(local_path).exists():
                # Read file content
                async with aiofiles.open(local_path, 'rb') as f:
                    file_content = await f.read()
                
                # Determine content type and filename
                filename = f"{file_type}.{'json' if file_type.endswith('_json') else 'csv'}"
                content_type = "application/json" if file_type.endswith('_json') else "text/csv"
                
                files[form_name] = (filename, file_content, content_type)
                logger.info(f"   ✅ Loaded {form_name}: {filename}")
            else:
                missing_files.append(file_type)
        
        if missing_files:
            error_msg = f"Required files not found for job {job_id}: {missing_files}"
            logger.error(f"❌ {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Required files not found in local storage. Missing: {missing_files}. Please ensure the ingestion job has completed and files are stored locally."
            )
        
        # Check for optional files (structural_elements_csv, definitions_csv)
        optional_files = {
            "structural_elements_csv": "structural_elements_csv",
            "definitions_csv": "definitions_csv"
        }
        
        for form_name, file_type in optional_files.items():
            local_path = ingestion_file_service.get_local_file_path(job_id, file_type)
            
            if local_path and Path(local_path).exists():
                async with aiofiles.open(local_path, 'rb') as f:
                    file_content = await f.read()
                
                filename = f"{file_type}.csv"
                files[form_name] = (filename, file_content, "text/csv")
                logger.info(f"   ✅ Loaded optional {form_name}: {filename}")
        
        # Prepare form data
        form_data = {
            "document_name": document_name,
            "use_filtered_extraction": str(use_filtered_extraction).lower(),
            "force_re_embed": str(force_re_embed).lower(),
            "embedding_model": embedding_model,
            "chroma_db_path": chroma_db_path,
            "collection_name": collection_name,
        }
        
        # Add optional document_id if provided
        if document_id:
            form_data["document_id"] = document_id
        
        # 📋 Log the equivalent curl command for debugging
        logger.info(f"🌐 Making API call to: {settings.precedent_retrieval_api_url}/embed_precedent")
        logger.info(f"📁 Files being sent:")
        for form_name, (filename, content, content_type) in files.items():
            file_size_kb = len(content) / 1024
            logger.info(f"   • {form_name}: {filename} ({content_type}, {file_size_kb:.1f}KB)")
        
        logger.info(f"📝 Form data being sent:")
        for key, value in form_data.items():
            logger.info(f"   • {key}: {value}")
        

        
        # Make the external API call
        async with httpx.AsyncClient(timeout=settings.precedent_retrieval_api_timeout) as client:
            response = await client.post(
                f"{settings.precedent_retrieval_api_url}/embed_precedent",
                files=files,
                data=form_data
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Precedent embed API successful")
                logger.info(f"   Job ID: {response_data.get('job_id')}")
                # Register job total-time budget for embed job
                job_id_value = response_data.get('job_id')
                if job_id_value:
                    job_timeout_registry.register_job("precedent", job_id_value, settings.precedent_retrieval_api_timeout)
                
                # Return the response using our schema
                return EmbedPrecedentResponse(**response_data)
            else:
                # Log the error and raise HTTPException
                error_detail = f"Precedent embed API failed with status {response.status_code}: {response.text}"
                logger.error(f"❌ {error_detail}")
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
                
    except HTTPException:
        # Re-raise HTTP exceptions (like 404 for missing files)
        raise
    except httpx.TimeoutException:
        error_msg = "Precedent embed API request timed out"
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
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/health")
async def precedent_health_check(
    current_user: TokenData = Depends(get_current_user)
):
    """
    Check the health of the precedent service API.
    """
    try:
        logger.info(f"🔍 PRECEDENT health check from user {current_user.user_id}")
        
        async with httpx.AsyncClient(timeout=10) as client:
            # Try to reach the precedent service (assuming it has a health endpoint)
            response = await client.get(f"{settings.precedent_retrieval_api_url}/health")
            
            if response.status_code == 200:
                logger.info("✅ Precedent API is healthy")
                return {
                    "status": "healthy",
                    "precedent_api_url": settings.precedent_retrieval_api_url,
                    "timeout": settings.precedent_retrieval_api_timeout,
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            else:
                logger.warning(f"⚠️ Precedent API returned status {response.status_code}")
                return {
                    "status": "unhealthy",
                    "precedent_api_url": settings.precedent_retrieval_api_url,
                    "error": f"API returned status {response.status_code}"
                }
                
    except httpx.TimeoutException:
        logger.error("❌ Precedent API health check timed out")
        return {
            "status": "timeout",
            "precedent_api_url": settings.precedent_retrieval_api_url,
            "error": "Health check timed out"
        }
    except Exception as e:
        logger.error(f"❌ Precedent API health check failed: {str(e)}")
        return {
            "status": "error",
            "precedent_api_url": settings.precedent_retrieval_api_url,
            "error": str(e)
        } 