"""
Dependency injection helpers for FastAPI routes.
"""

from app.services.file_service import file_service, FileService


def get_file_service() -> FileService:
    """Provide the file service singleton."""
    return file_service
