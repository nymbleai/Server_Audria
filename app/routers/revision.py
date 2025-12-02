from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.revision import RevisionRequest, RevisionResponse, RevisionProcessRequest
from app.schemas.auth import TokenData
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from datetime import datetime
from app.core.billing_middleware import check_billing_limit, log_billing_usage
from app.models.usage_log import FeatureType
import httpx
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/process", response_model=RevisionResponse)
async def process_revision(
    request: RevisionProcessRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Process a clause revision using the external revision agent.
    
    This endpoint acts as a pass-through to the revision agent API,
    forwarding the request and returning the response.
    """
    try:
        # Log the incoming request
        logger.info(f"🔄 REVISION process request from user {current_user.user_id}")
        logger.info(f"   User instruction: {request.user_instruction}")
        logger.info(f"   Clause length: {len(request.clause)} characters")
        logger.info(f"   Has precedent: {bool(request.precedent)}")
        logger.info(f"   Has custom system prompt: {bool(getattr(request, 'revision_prompt', None))}")
        logger.info(f"   Revision model: {getattr(request, 'revision_model', 'default')}")
        logger.info(f"   Has use_reflection: {bool(getattr(request, 'use_reflection', None))}")
        logger.info(f"   Has evaluation_prompt: {bool(getattr(request, 'evaluation_prompt', None))}")
        
        # Billing check: Estimate tokens based on clause + instruction + precedent length
        estimated_tokens = (len(request.clause) + len(request.user_instruction)) // 4
        if request.precedent:
            estimated_tokens += len(request.precedent) // 4
        logger.info(f"   Estimated tokens: {estimated_tokens}")
        
        # Check subscription limit (handled by outer HTTPException catch)
        await check_billing_limit(
            db,
            current_user.user_id,
            FeatureType.REVISION,
            estimated_tokens
        )
        
        # Prepare the payload for the external API
        payload = {
            "clause": request.clause,
            "user_instruction": request.user_instruction
        }
        
        # Add optional fields if provided
        if request.precedent:
            payload["precedent"] = request.precedent
            
        # Only add revision_prompt if it's provided (user enabled custom system prompt)
        logger.info(f"   🔍 Checking revision_prompt: hasattr={hasattr(request, 'revision_prompt')}, value={getattr(request, 'revision_prompt', 'NOT_FOUND')}")
        
        if hasattr(request, 'revision_prompt') and request.revision_prompt:
            payload["revision_prompt"] = request.revision_prompt
            logger.info(f"   📝 Custom system prompt: {request.revision_prompt[:10]}...")
            logger.info(f"   ✅ Added revision_prompt to payload")
        else:
            logger.info(f"   ❌ No revision_prompt provided - using external API default")
            
        # Add revision_model if provided
        if hasattr(request, 'revision_model') and request.revision_model:
            payload["revision_model"] = request.revision_model
            logger.info(f"   ✅ Added revision_model to payload: {request.revision_model}")
        
        # Add use_reflection if provided
        if hasattr(request, 'use_reflection') and request.use_reflection is not None:
            payload["use_reflection"] = request.use_reflection
            logger.info(f"   ✅ Added use_reflection to payload: {request.use_reflection}")

        if hasattr(request, 'evaluation_prompt') and request.evaluation_prompt:
            payload["evaluation_prompt"] = request.evaluation_prompt
            logger.info(f"   ✅ Added evaluation_prompt to payload: {request.evaluation_prompt}")
        else:
            logger.info(f"   ❌ No evaluation_prompt provided - using external API default")
        
        # Log final payload before sending
        logger.info(f"   📋 Final payload keys: {list(payload.keys())}")
        logger.info(f"   📋 Final payload: {payload}")
        
        # Make the external API call
        start_time = datetime.utcnow()
        async with httpx.AsyncClient(timeout=settings.revision_api_timeout) as client:
            response = await client.post(
                f"{settings.revision_api_url}/revision/process",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"✅ Revision API successful")
                logger.info(f"   Response keys: {list(response_data.keys())}")
                logger.info(f"   Response: {response_data}")
                latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                # Log usage using actual tokens from revision service (no estimates)
                token_usage = response_data.get('token_usage') or {}
                actual_tokens = token_usage.get('total_tokens')
                if actual_tokens is None:
                    actual_tokens = 0
                    logger.warning("Revision token usage missing; stored 0. Keys present: %s", list(response_data.keys()))
                await log_billing_usage(
                    db,
                    current_user.user_id,
                    FeatureType.REVISION,
                    int(actual_tokens),
                    request_id=None,
                    meta_data=json.dumps({
                        "instruction_preview": request.user_instruction[:100],
                        "has_precedent": bool(request.precedent)
                    }),
                    latency_ms=latency_ms,
                    model_used=getattr(request, 'revision_model', None) or 'UNKNOWN',
                    prompt_tokens=token_usage.get('prompt_tokens'),
                    completion_tokens=token_usage.get('completion_tokens'),
                    status='SUCCESS',
                    project_id=getattr(request, 'project_id', None),
                    file_id=getattr(request, 'file_id', None)
                )
                
                # Return the response using our schema
                return RevisionResponse(**response_data)
            else:
                # Log the error and raise HTTPException
                error_detail = f"Revision API failed with status {response.status_code}: {response.text}"
                logger.error(f"❌ {error_detail}")
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
                
    except httpx.TimeoutException:
        error_msg = "Revision API request timed out"
        logger.error(f"❌ {error_msg}")
        # Log timeout with status='TIMEOUT'
        try:
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000) if 'start_time' in locals() else None
            await log_billing_usage(
                db,
                current_user.user_id,
                FeatureType.REVISION,
                0,
                request_id=None,
                meta_data=json.dumps({"error": "timeout"}),
                latency_ms=latency_ms,
                status='TIMEOUT',
                project_id=getattr(request, 'project_id', None),
                file_id=getattr(request, 'file_id', None)
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
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/health")
async def revision_health_check(
    current_user: TokenData = Depends(get_current_user)
):
    """
    Check the health of the revision agent API.
    """
    try:
        logger.info(f"🔍 REVISION health check from user {current_user.user_id}")
        
        async with httpx.AsyncClient(timeout=10) as client:
            # Try to reach the revision agent (assuming it has a health endpoint)
            response = await client.get(f"{settings.revision_api_url}/health")
            
            if response.status_code == 200:
                logger.info("✅ Revision API is healthy")
                return {
                    "status": "healthy",
                    "revision_api_url": settings.revision_api_url,
                    "timeout": settings.revision_api_timeout,
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            else:
                logger.warning(f"⚠️ Revision API returned status {response.status_code}")
                return {
                    "status": "unhealthy",
                    "revision_api_url": settings.revision_api_url,
                    "error": f"API returned status {response.status_code}"
                }
                
    except httpx.TimeoutException:
        logger.error("❌ Revision API health check timed out")
        return {
            "status": "timeout",
            "revision_api_url": settings.revision_api_url,
            "error": "Health check timed out"
        }
    except Exception as e:
        logger.error(f"❌ Revision API health check failed: {str(e)}")
        return {
            "status": "error",
            "revision_api_url": settings.revision_api_url,
            "error": str(e)
        } 