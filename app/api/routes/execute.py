"""
Code execution routes — run Python code snippets.
Placeholder for Phase 1; real Jupyter kernel integration in Phase 3.
"""

import time
import uuid

from fastapi import APIRouter, HTTPException

from app.models.schemas import ExecuteRequest, ExecutionOutput
from app.services.file_service import file_service

router = APIRouter()


@router.post("/execute", response_model=ExecutionOutput)
async def execute_code(request: ExecuteRequest):
    """
    Execute a Python code snippet in a sandboxed environment.

    Phase 1: Returns a placeholder response.
    Phase 3: Will execute in a Jupyter kernel via Kernel Gateway.
    """
    # Verify the file exists
    metadata = file_service.get_metadata(request.file_id)
    if metadata is None:
        raise HTTPException(
            status_code=404, detail=f"File '{request.file_id}' not found"
        )

    cell_id = request.cell_id or str(uuid.uuid4())
    
    # Execute via local code runner since Docker/Jupyter isn't available
    from app.agent.tools.code_runner import run_python_code
    
    start_time = time.time()
    result = run_python_code(request.file_id, request.code)
    exec_time_ms = int((time.time() - start_time) * 1000)

    return ExecutionOutput(
        cell_id=cell_id,
        stdout=result.get("stdout", ""),
        stderr=result.get("stderr", ""),
        result=None,
        visualizations=result.get("visualizations", []),
        execution_time_ms=exec_time_ms,
        success=result.get("success", False),
        error=result.get("error")
    )
