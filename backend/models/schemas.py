"""
Pydantic schema models for the DocDigitizer API.

Defines request/response schemas, enumerations, and data transfer objects
used throughout the application for validation, serialization, and
API documentation.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ProcessingStage(str, Enum):
    """Represents the current stage of document processing."""

    QUEUED = "queued"
    FORMAT_DETECTION = "format_detection"
    PREPROCESSING = "preprocessing"
    TEXT_EXTRACTION = "text_extraction"
    AI_ANALYSIS = "ai_analysis"
    OUTPUT_GENERATION = "output_generation"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCategory(str, Enum):
    """High-level category for an uploaded document."""

    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    TEXT = "text"


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    """Response returned after a successful file upload.

    Attributes:
        job_id: Unique identifier assigned to the processing job.
        filename: Original name of the uploaded file.
        file_size: Size of the uploaded file in bytes.
        category: Detected document category (e.g. 'image', 'pdf').
        message: Human-readable status message.
    """

    job_id: str
    filename: str
    file_size: int
    category: str
    message: str


class ProcessingStatus(BaseModel):
    """Represents the current status of a document processing job.

    Attributes:
        job_id: Unique identifier of the processing job.
        stage: Current processing stage.
        progress: Percentage progress (0-100).
        message: Human-readable description of the current stage.
        started_at: ISO-format timestamp when processing began.
        completed_at: ISO-format timestamp when processing finished.
    """

    job_id: str
    stage: ProcessingStage
    progress: int = Field(ge=0, le=100)
    message: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Extraction Data Models
# ---------------------------------------------------------------------------


class DocumentEntity(BaseModel):
    """A named entity extracted from a document.

    Attributes:
        entity_type: Category of the entity (e.g. PERSON, DATE, ADDRESS,
            ID, ORGANIZATION).
        value: The extracted entity text.
        confidence: Optional confidence score between 0.0 and 1.0.
    """

    entity_type: str
    value: str
    confidence: Optional[float] = None


class TableData(BaseModel):
    """Represents a table extracted from a document.

    Attributes:
        title: Optional descriptive title for the table.
        headers: List of column header strings.
        rows: List of rows, where each row is a list of cell values.
        page: Optional page number the table was found on.
    """

    title: Optional[str] = None
    headers: list[str]
    rows: list[list[Any]]
    page: Optional[int] = None


class KeyValuePair(BaseModel):
    """A key-value pair extracted from a form or document.

    Attributes:
        key: The field label or key.
        value: The corresponding value.
        confidence: Optional confidence score between 0.0 and 1.0.
    """

    key: str
    value: str
    confidence: Optional[float] = None


class ExtractionResult(BaseModel):
    """Complete result of document extraction and analysis.

    Attributes:
        job_id: Unique identifier of the processing job.
        filename: Original filename that was processed.
        document_type: AI-detected document type (e.g. 'invoice', 'receipt').
        category: High-level document category.
        pages_processed: Number of pages processed.
        processing_time_seconds: Total processing time in seconds.
        raw_text: Full raw text extracted from the document.
        key_value_pairs: Structured key-value pairs found in the document.
        entities: Named entities extracted from the document.
        tables: Tables extracted from the document.
        metadata: Additional metadata about the document or processing run.
        summary: AI-generated summary of the document content.
    """

    job_id: str
    filename: str
    document_type: Optional[str] = None
    category: str
    pages_processed: int = 1
    processing_time_seconds: float
    raw_text: str
    key_value_pairs: list[KeyValuePair] = []
    entities: list[DocumentEntity] = []
    tables: list[TableData] = []
    metadata: dict[str, Any] = {}
    summary: Optional[str] = None


# ---------------------------------------------------------------------------
# Error & Informational Models
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Standard error response returned by the API.

    Attributes:
        error: Short error title.
        detail: Detailed error description.
        code: HTTP status code.
    """

    error: str
    detail: str
    code: int


class SupportedFormatsResponse(BaseModel):
    """Lists all file formats the system accepts or rejects.

    Attributes:
        images: Supported image extensions.
        documents: Supported document extensions.
        spreadsheets: Supported spreadsheet extensions.
        presentations: Supported presentation extensions.
        rejected: Explicitly rejected extensions (audio/video).
    """

    images: list[str]
    documents: list[str]
    spreadsheets: list[str]
    presentations: list[str]
    rejected: list[str]
