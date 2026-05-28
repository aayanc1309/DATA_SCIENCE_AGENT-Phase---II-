"""
File service — handles file upload, parsing, storage, and metadata extraction.
"""

import io
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.models.schemas import ColumnInfo, FileMetadata, FileType


class FileService:
    """Manages file uploads, parsing, and metadata extraction."""

    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        # In-memory store for MVP (replace with DB in Phase 5)
        self._metadata_store: dict[str, FileMetadata] = {}
        self._dataframe_cache: dict[str, pd.DataFrame] = {}

    def _detect_file_type(self, filename: str) -> FileType:
        """Detect file type from extension."""
        ext = Path(filename).suffix.lower()
        if ext == ".csv":
            return FileType.CSV
        elif ext == ".xlsx":
            return FileType.XLSX
        elif ext == ".xls":
            return FileType.XLS
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _validate_file(self, filename: str, file_size: int) -> None:
        """Validate file extension and size."""
        ext = Path(filename).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"File type '{ext}' not allowed. "
                f"Supported: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            raise ValueError(
                f"File too large ({file_size / 1024 / 1024:.1f} MB). "
                f"Maximum: {settings.MAX_FILE_SIZE_MB} MB"
            )

    def _parse_dataframe(self, content: bytes, file_type: FileType) -> pd.DataFrame:
        """Parse file content into a pandas DataFrame."""
        buffer = io.BytesIO(content)

        if file_type == FileType.CSV:
            # Try common encodings
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    buffer.seek(0)
                    return pd.read_csv(buffer, encoding=encoding)
                except UnicodeDecodeError:
                    continue
            raise ValueError("Could not decode CSV file. Please check the encoding.")

        elif file_type in (FileType.XLSX, FileType.XLS):
            return pd.read_excel(buffer)

        raise ValueError(f"Unsupported file type: {file_type}")

    def _extract_column_info(self, df: pd.DataFrame) -> list[ColumnInfo]:
        """Extract metadata for each column."""
        columns = []
        for col in df.columns:
            series = df[col]
            columns.append(
                ColumnInfo(
                    name=str(col),
                    dtype=str(series.dtype),
                    non_null_count=int(series.notna().sum()),
                    null_count=int(series.isna().sum()),
                    unique_count=int(series.nunique()),
                    sample_values=series.dropna().head(5).tolist(),
                )
            )
        return columns

    async def process_upload(
        self, filename: str, content: bytes
    ) -> tuple[str, FileMetadata, pd.DataFrame]:
        """
        Process an uploaded file: validate, parse, extract metadata, and store.

        Returns:
            Tuple of (file_id, metadata, dataframe)
        """
        file_size = len(content)
        self._validate_file(filename, file_size)

        file_type = self._detect_file_type(filename)
        file_id = str(uuid.uuid4())

        # Parse into DataFrame
        df = self._parse_dataframe(content, file_type)

        # Save raw file to disk
        safe_filename = f"{file_id}_{Path(filename).name}"
        file_path = self.upload_dir / safe_filename
        file_path.write_bytes(content)

        # Extract metadata
        columns = self._extract_column_info(df)
        metadata = FileMetadata(
            file_id=file_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=file_size,
            row_count=len(df),
            column_count=len(df.columns),
            columns=columns,
        )

        # Cache for quick access
        self._metadata_store[file_id] = metadata
        self._dataframe_cache[file_id] = df

        return file_id, metadata, df

    def get_metadata(self, file_id: str) -> FileMetadata | None:
        """Retrieve stored metadata for a file."""
        return self._metadata_store.get(file_id)

    def get_dataframe(self, file_id: str) -> pd.DataFrame | None:
        """Retrieve the cached DataFrame for a file."""
        return self._dataframe_cache.get(file_id)

    def get_preview(
        self, file_id: str, page: int = 1, page_size: int = 50
    ) -> list[dict[str, Any]] | None:
        """Get paginated preview rows as list of dicts."""
        df = self._dataframe_cache.get(file_id)
        if df is None:
            return None

        start = (page - 1) * page_size
        end = start + page_size
        preview_df = df.iloc[start:end]

        # Convert to JSON-safe dicts (handle NaN, datetime, etc.)
        return preview_df.where(preview_df.notna(), None).to_dict(orient="records")

    def get_schema_summary(self, file_id: str) -> str:
        """
        Generate a plain-text schema summary for the LLM agent.
        This is what gets sent to the Planner node.
        """
        metadata = self._metadata_store.get(file_id)
        if metadata is None:
            return ""

        df = self._dataframe_cache.get(file_id)
        lines = [
            f"Dataset: {metadata.filename}",
            f"Rows: {metadata.row_count:,} | Columns: {metadata.column_count}",
            "",
            "Columns:",
        ]
        for col in metadata.columns:
            lines.append(
                f"  - {col.name} ({col.dtype}): "
                f"{col.non_null_count:,} non-null, "
                f"{col.null_count:,} null, "
                f"{col.unique_count:,} unique"
            )

        # Add sample rows
        if df is not None:
            lines.append("")
            lines.append("Sample rows (first 5):")
            lines.append(df.head(5).to_string(index=False))

        # Add basic statistics for numeric columns
        if df is not None:
            numeric_df = df.select_dtypes(include=["number"])
            if not numeric_df.empty:
                lines.append("")
                lines.append("Numeric column statistics:")
                lines.append(numeric_df.describe().to_string())

        return "\n".join(lines)


# Singleton instance
file_service = FileService()
