"""
Pydantic schemas for API request/response validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────


class FileType(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    XLS = "xls"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CellType(str, Enum):
    CODE = "code"
    MARKDOWN = "markdown"


# ── File Upload ──────────────────────────────────────────


class ColumnInfo(BaseModel):
    """Metadata for a single column in the dataset."""
    name: str
    dtype: str
    non_null_count: int
    null_count: int
    unique_count: int
    sample_values: list[Any] = Field(default_factory=list)


class FileMetadata(BaseModel):
    """Metadata extracted from an uploaded file."""
    file_id: str
    filename: str
    file_type: FileType
    file_size_bytes: int
    row_count: int
    column_count: int
    columns: list[ColumnInfo]
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class UploadResponse(BaseModel):
    """Response after successful file upload."""
    file_id: str
    filename: str
    file_type: FileType
    row_count: int
    column_count: int
    columns: list[ColumnInfo]
    preview: list[dict[str, Any]]  # First N rows as list of dicts
    message: str = "File uploaded successfully"


class FilePreviewResponse(BaseModel):
    """Response for data preview requests."""
    file_id: str
    filename: str
    row_count: int
    column_count: int
    columns: list[ColumnInfo]
    preview: list[dict[str, Any]]
    page: int = 1
    page_size: int = 50


# ── Analysis ─────────────────────────────────────────────


class AnalysisRequest(BaseModel):
    """Request to start an AI analysis."""
    file_id: str
    user_query: Optional[str] = Field(
        default=None,
        description="Optional natural-language question about the data",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="WebSocket session ID for real-time updates",
    )


class VisualizationSpec(BaseModel):
    """A Plotly visualization specification."""
    title: str
    chart_type: str  # bar, line, scatter, histogram, etc.
    plotly_json: dict[str, Any]  # Full Plotly figure JSON


class CodeSnippet(BaseModel):
    """A generated code snippet that the user can run."""
    cell_id: str
    title: str
    description: str
    code: str
    language: str = "python"


class AnalysisResult(BaseModel):
    """Complete result from an AI analysis run."""
    task_id: str
    file_id: str
    status: AnalysisStatus
    summary: Optional[str] = None
    key_findings: list[str] = Field(default_factory=list)
    visualizations: list[VisualizationSpec] = Field(default_factory=list)
    code_snippets: list[CodeSnippet] = Field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AnalysisStatusResponse(BaseModel):
    """Status update for a running analysis."""
    task_id: str
    status: AnalysisStatus
    progress_percent: int = 0
    current_step: Optional[str] = None
    message: Optional[str] = None


# ── Code Execution ───────────────────────────────────────


class ExecuteRequest(BaseModel):
    """Request to execute a code snippet."""
    file_id: str
    code: str
    cell_id: Optional[str] = None


class ExecutionOutput(BaseModel):
    """Output from a code execution."""
    cell_id: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    result: Optional[Any] = None  # Return value (e.g., DataFrame as dict)
    visualizations: list[VisualizationSpec] = Field(default_factory=list)
    execution_time_ms: int = 0
    success: bool = True
    error: Optional[str] = None


# ── WebSocket Messages ───────────────────────────────────


class WSMessage(BaseModel):
    """WebSocket message envelope."""
    event: str  # analysis:progress, analysis:result, execution:output, chat:message
    data: dict[str, Any]
