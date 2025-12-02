from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.exceptions import handle_database_errors
from app.schemas.auth import TokenData
from app.schemas.comparison import HTMLComparisonRequest, VersionComparisonRequest
from app.services.comparison_service import comparison_service
from app.services.blob_storage_service import blob_storage_service
from app.crud.file import file_crud
from app.crud.file_version import file_version_crud

router = APIRouter()

# --- Endpoints ---

@router.post(
    "/html",
    summary="Compare two HTML strings",
    description="Accepts two HTML content strings and returns a diff in HTML or JSON format."
)
@handle_database_errors
async def compare_html_strings(
    request: HTMLComparisonRequest,
    format: str = Query("html", enum=["html", "json"], description="Response format: 'html' or 'json' (default: html)"),
    current_user: TokenData = Depends(get_current_user)
):
    try:
        if format == "json":
            diff = comparison_service.generate_json_diff(request.html_content_1, request.html_content_2)
            return JSONResponse(content=diff)
        else:
            diff_html = comparison_service.compare_html(request.html_content_1, request.html_content_2)
            return HTMLResponse(content=diff_html)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post(
    "/versions",
    summary="Compare two file versions",
    description="Accepts two version IDs, fetches their content from cloud storage, and returns a diff in HTML or JSON format."
)
@handle_database_errors
async def compare_file_versions(
    request: VersionComparisonRequest,
    format: str = Query("html", enum=["html", "json"], description="Response format: 'html' or 'json' (default: html)"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    version_1 = await file_version_crud.get_by_user_id(db, id=request.version_id_1, user_id=current_user.user_id)
    version_2 = await file_version_crud.get_by_user_id(db, id=request.version_id_2, user_id=current_user.user_id)

    if version_1.file_id != version_2.file_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Both versions must belong to the same file."
        )

    html_content_1_bytes = await blob_storage_service.download_file(version_1.blob_path)
    html_content_2_bytes = await blob_storage_service.download_file(version_2.blob_path)

    if html_content_1_bytes is None or html_content_2_bytes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Could not retrieve one or both file versions from storage.")

    html_content_1 = html_content_1_bytes.decode('utf-8')
    html_content_2 = html_content_2_bytes.decode('utf-8')

    try:
        if format == "json":
            diff = comparison_service.generate_json_diff(html_content_1, html_content_2)
            return JSONResponse(content=diff)
        else:
            diff_html = comparison_service.compare_html(html_content_1, html_content_2)
            return HTMLResponse(content=diff_html)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 