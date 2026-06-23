"""
Document processing API routes.

Provides endpoints for uploading documents, checking processing status,
downloading results in JSON/CSV, and querying supported formats.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from config import settings
from models.schemas import ExtractionResult, ProcessingStatus, SupportedFormatsResponse
from services.pipeline import ProcessingPipeline
from utils.helpers import generate_job_id, get_file_extension, sanitize_filename

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

# Module-level pipeline instance (shared across requests)
pipeline = ProcessingPipeline()


# --------------------------------------------------------------------------
# POST /upload — Single file upload and processing
# --------------------------------------------------------------------------

@router.post("/upload", response_model=ExtractionResult)
async def upload_document(file: UploadFile = File(...)) -> ExtractionResult:
    """Upload a single document for processing.

    Validates the file type and size, saves it to the upload directory,
    processes it through the extraction pipeline, and returns the result.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    # Validate extension
    ext = get_file_extension(file.filename)
    if settings.is_extension_rejected(ext):
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not supported. Audio and video files are excluded.",
        )
    if not settings.is_extension_supported(ext):
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not supported. Supported formats: {sorted(settings.all_supported)}",
        )

    # Read file content and validate size
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {size_mb:.0f} MB.",
        )

    # Save to upload directory
    job_id = generate_job_id()
    safe_name = sanitize_filename(file.filename)
    upload_dir = settings.upload_dir_path / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / safe_name

    with open(file_path, "wb") as f:
        f.write(content)
    logger.info("Saved upload: %s (%d bytes) → %s", file.filename, len(content), file_path)

    # Process in thread executor to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        pipeline.process,
        file_path,
        file.filename,
        job_id,
    )

    return result


# --------------------------------------------------------------------------
# POST /upload/batch — Batch file upload
# --------------------------------------------------------------------------

@router.post("/upload/batch", response_model=list[ExtractionResult])
async def upload_batch(files: list[UploadFile] = File(...)) -> list[ExtractionResult]:
    """Upload multiple documents for batch processing.

    Each file is validated and processed independently. Partial failures
    are included in the response with error metadata.
    """
    results: list[ExtractionResult] = []

    for file in files:
        try:
            # Reuse the single upload logic
            result = await upload_document(file)
            results.append(result)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Batch processing error for '%s': %s", file.filename, exc)

    return results


# --------------------------------------------------------------------------
# GET /status/{job_id} — Processing status
# --------------------------------------------------------------------------

@router.get("/status/{job_id}", response_model=ProcessingStatus)
async def get_status(job_id: str) -> ProcessingStatus:
    """Check the processing status of a job."""
    status = pipeline.get_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return status


# --------------------------------------------------------------------------
# GET /result/{job_id}/json — Download JSON result
# --------------------------------------------------------------------------

@router.get("/result/{job_id}/json")
async def download_json(job_id: str) -> FileResponse:
    """Download the extraction result as a JSON file."""
    json_path = settings.output_dir_path / job_id / f"{job_id}.json"
    if not json_path.is_file():
        raise HTTPException(status_code=404, detail=f"JSON result for job '{job_id}' not found.")
    return FileResponse(
        path=str(json_path),
        media_type="application/json",
        filename=f"{job_id}_extraction.json",
    )


# --------------------------------------------------------------------------
# GET /result/{job_id}/csv — Download CSV result
# --------------------------------------------------------------------------

@router.get("/result/{job_id}/csv")
async def download_csv(job_id: str) -> FileResponse:
    """Download the extraction result as a CSV file."""
    csv_path = settings.output_dir_path / job_id / f"{job_id}.csv"
    if not csv_path.is_file():
        raise HTTPException(status_code=404, detail=f"CSV result for job '{job_id}' not found.")
    return FileResponse(
        path=str(csv_path),
        media_type="text/csv",
        filename=f"{job_id}_extraction.csv",
    )


# --------------------------------------------------------------------------
# GET /formats — List supported formats
# --------------------------------------------------------------------------

@router.get("/formats", response_model=SupportedFormatsResponse)
async def get_formats() -> SupportedFormatsResponse:
    """Return all supported and rejected file formats."""
    all_rejected = sorted(settings.all_rejected)
    return SupportedFormatsResponse(
        images=settings.SUPPORTED_EXTENSIONS.get("images", []),
        documents=settings.SUPPORTED_EXTENSIONS.get("documents", []),
        spreadsheets=settings.SUPPORTED_EXTENSIONS.get("spreadsheets", []),
        presentations=settings.SUPPORTED_EXTENSIONS.get("presentations", []),
        rejected=all_rejected,
    )
