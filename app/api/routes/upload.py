"""
File upload routes — handles CSV/Excel file uploads and preview.
"""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.models.schemas import FilePreviewResponse, UploadResponse
from app.services.file_service import file_service

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a CSV or Excel file for analysis.

    - Validates file type and size
    - Parses into a pandas DataFrame
    - Extracts column metadata (types, nulls, uniques)
    - Returns a preview of the first 20 rows
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    try:
        content = await file.read()

        file_id, metadata, df = await file_service.process_upload(
            filename=file.filename,
            content=content,
        )

        # Return first 20 rows as preview
        preview = file_service.get_preview(file_id, page=1, page_size=20) or []

        return UploadResponse(
            file_id=file_id,
            filename=metadata.filename,
            file_type=metadata.file_type,
            row_count=metadata.row_count,
            column_count=metadata.column_count,
            columns=metadata.columns,
            preview=preview,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}",
        )


@router.get("/files/{file_id}/preview", response_model=FilePreviewResponse)
async def get_file_preview(
    file_id: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Rows per page"),
):
    """
    Get a paginated preview of an uploaded file's data.
    """
    metadata = file_service.get_metadata(file_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found")

    preview = file_service.get_preview(file_id, page=page, page_size=page_size)
    if preview is None:
        raise HTTPException(status_code=404, detail="Preview data not available")

    return FilePreviewResponse(
        file_id=file_id,
        filename=metadata.filename,
        row_count=metadata.row_count,
        column_count=metadata.column_count,
        columns=metadata.columns,
        preview=preview,
        page=page,
        page_size=page_size,
    )
