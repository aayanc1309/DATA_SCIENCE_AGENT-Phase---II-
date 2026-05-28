"""
Analysis routes — trigger and monitor AI analysis on uploaded files.
"""

import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header

from app.models.schemas import (
    AnalysisRequest,
    AnalysisResult,
    AnalysisStatus,
    AnalysisStatusResponse,
)
from app.services.file_service import file_service
from app.services.analysis_service import analysis_service

router = APIRouter()

@router.post("/analysis/start", response_model=AnalysisStatusResponse)
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    Trigger an AI analysis on an uploaded file.
    Runs the LangGraph agent in the background.
    """
    metadata = file_service.get_metadata(request.file_id)
    if metadata is None:
        raise HTTPException(
            status_code=404, detail=f"File '{request.file_id}' not found"
        )

    task_id = str(uuid.uuid4())
    
    # Use the session_id from the request, fallback to 'default_session' if not provided
    session_id = request.session_id or "default_session"

    task = analysis_service.create_task(task_id, request.file_id)
    
    # Queue the background Task
    background_tasks.add_task(
        analysis_service.run_analysis_simple,
        task_id=task_id,
        file_id=request.file_id,
        user_query=request.user_query,
        session_id=session_id
    )

    return AnalysisStatusResponse(
        task_id=task_id,
        status=AnalysisStatus.PENDING,
        progress_percent=0,
        current_step="Queued for analysis",
        message=f"Analysis started for '{metadata.filename}'."
    )

@router.get("/analysis/{task_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(task_id: str):
    """Get the current status of an analysis task."""
    task = analysis_service.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=404, detail=f"Analysis task '{task_id}' not found"
        )

    return AnalysisStatusResponse(
        task_id=task.task_id,
        status=task.status,
        progress_percent=100 if task.status == AnalysisStatus.COMPLETED else 0,
        current_step=task.status.value,
    )

@router.get("/analysis/{task_id}/result", response_model=AnalysisResult)
async def get_analysis_result(task_id: str):
    """Get the full result of a completed analysis."""
    task = analysis_service.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=404, detail=f"Analysis task '{task_id}' not found"
        )
    return task



