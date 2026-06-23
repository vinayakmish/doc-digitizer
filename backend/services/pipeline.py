"""
Master processing pipeline orchestrator.

Chains format detection → parsing/preprocessing → OCR/AI extraction →
output generation into a single end-to-end pipeline. Tracks job status
and handles errors at each stage with graceful degradation.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from config import settings
from models.schemas import (
    DocumentCategory,
    DocumentEntity,
    ExtractionResult,
    KeyValuePair,
    ProcessingStage,
    ProcessingStatus,
    TableData,
)
from services.ai_extractor import AIExtractor
from services.document_parser import DocumentParser
from services.format_detector import FormatDetector
from services.image_preprocessor import ImagePreprocessor
from services.ocr_engine import OCREngine
from services.output_generator import OutputGenerator
from services.text_analyzer import TextAnalyzer
from utils.helpers import get_timestamp

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """End-to-end document processing pipeline."""

    # Class-level status store (shared across requests)
    _job_statuses: dict[str, ProcessingStatus] = {}
    _job_results: dict[str, ExtractionResult] = {}

    def __init__(self) -> None:
        self.format_detector = FormatDetector()
        self.document_parser = DocumentParser()
        self.image_preprocessor = ImagePreprocessor()
        self.ocr_engine = OCREngine()
        self.ai_extractor = AIExtractor()
        self.output_generator = OutputGenerator()
        self.text_analyzer = TextAnalyzer()
        logger.info("ProcessingPipeline initialised.")

    def process(
        self, file_path: Path, original_filename: str, job_id: str
    ) -> ExtractionResult:
        """Execute the full processing pipeline.

        Args:
            file_path: Path to the uploaded file on disk.
            original_filename: Original name of the uploaded file.
            job_id: Unique job identifier.

        Returns:
            An ExtractionResult containing all extracted data.
        """
        start_time = time.time()
        self._update_status(job_id, ProcessingStage.QUEUED, 0, "Job queued.")

        raw_text = ""
        tables: list[dict[str, Any]] = []
        key_value_pairs: list[dict[str, Any]] = []
        entities: list[dict[str, Any]] = []
        document_type: str | None = None
        summary: str | None = None
        metadata: dict[str, Any] = {}
        pages_processed = 1

        try:
            # -----------------------------------------------------------
            # Stage 1: Format Detection
            # -----------------------------------------------------------
            self._update_status(job_id, ProcessingStage.FORMAT_DETECTION, 10, "Detecting file format…")
            fmt = self.format_detector.detect(file_path, original_filename)
            category = fmt["category"]
            needs_ocr = fmt["needs_ocr"]
            metadata["mime_type"] = fmt["mime_type"]
            metadata["extension"] = fmt["extension"]

            if not fmt["is_supported"]:
                raise ValueError(f"Unsupported file format: {fmt['extension']}")

            # -----------------------------------------------------------
            # Stage 2: Preprocessing / Parsing
            # -----------------------------------------------------------
            self._update_status(job_id, ProcessingStage.PREPROCESSING, 25, "Preprocessing document…")

            if category == DocumentCategory.IMAGE:
                # Image → preprocess for OCR/AI
                _, preprocessed_path = self.image_preprocessor.preprocess(file_path)
                pages_processed = 1

            elif category == DocumentCategory.PDF and needs_ocr:
                # Scanned PDF → render pages to images
                image_paths = self.image_preprocessor.render_pdf_pages(file_path)
                pages_processed = len(image_paths)

            else:
                # Digital document → parse directly
                parsed = self.document_parser.parse(file_path, category)
                raw_text = parsed.get("text", "")
                tables = parsed.get("tables", [])
                metadata.update(parsed.get("metadata", {}))
                pages_processed = parsed.get("pages", 1)

                # For spreadsheets/CSV: convert table data into key-value pairs
                # so each column header → key, cell value → value.
                if category == DocumentCategory.SPREADSHEET and tables:
                    for tbl in tables:
                        headers = tbl.get("headers", [])
                        rows = tbl.get("rows", [])
                        for row_idx, row in enumerate(rows):
                            for col_idx, header in enumerate(headers):
                                value = row[col_idx] if col_idx < len(row) else ""
                                if header.strip() and str(value).strip():
                                    key_value_pairs.append({
                                        "key": str(header).strip(),
                                        "value": str(value).strip(),
                                    })
                    logger.debug(
                        "Converted spreadsheet tables to %d key-value pairs.",
                        len(key_value_pairs),
                    )

            # -----------------------------------------------------------
            # Stage 3: Text Extraction / OCR
            # -----------------------------------------------------------
            self._update_status(job_id, ProcessingStage.TEXT_EXTRACTION, 45, "Extracting text…")

            if category == DocumentCategory.IMAGE or (category == DocumentCategory.PDF and needs_ocr):
                # Use AI extraction on images/scanned PDFs
                pass  # Handled in Stage 4

            # -----------------------------------------------------------
            # Stage 4: AI Analysis
            # -----------------------------------------------------------
            self._update_status(job_id, ProcessingStage.AI_ANALYSIS, 60, "Running AI analysis…")

            ai_result: dict[str, Any] | None = None

            if self.ai_extractor.is_available():
                try:
                    if category == DocumentCategory.IMAGE:
                        # Send original image to Gemini (better quality than preprocessed)
                        ai_result = self.ai_extractor.extract_from_image(file_path)

                    elif category == DocumentCategory.PDF and needs_ocr:
                        # Send PDF directly to Gemini
                        ai_result = self.ai_extractor.extract_from_pdf(file_path)

                    elif category == DocumentCategory.PDF:
                        # Digital PDF — send directly for best extraction
                        ai_result = self.ai_extractor.extract_from_pdf(file_path)

                    elif raw_text.strip():
                        # Digital doc with extracted text — send text for structuring
                        ai_result = self.ai_extractor.extract_from_text(raw_text)

                except Exception as exc:
                    logger.error("AI extraction failed: %s", exc)

            elif (category == DocumentCategory.IMAGE) or (category == DocumentCategory.PDF and needs_ocr):
                # No AI available — fall back to Tesseract OCR
                if self.ocr_engine.is_available():
                    logger.info("Falling back to Tesseract OCR.")
                    if category == DocumentCategory.IMAGE:
                        ocr_result = self.ocr_engine.ocr_image(file_path)
                        raw_text = ocr_result.get("text", "")
                    else:
                        image_paths_for_ocr = self.image_preprocessor.render_pdf_pages(file_path)
                        ocr_result = self.ocr_engine.ocr_images(image_paths_for_ocr)
                        raw_text = ocr_result.get("text", "")
                        pages_processed = ocr_result.get("pages", pages_processed)
                else:
                    logger.warning("Neither Gemini nor Tesseract available for OCR.")

            # Merge AI results if available
            if ai_result:
                if ai_result.get("raw_text"):
                    raw_text = ai_result["raw_text"]
                document_type = ai_result.get("document_type")
                summary = ai_result.get("summary")
                key_value_pairs = ai_result.get("key_value_pairs", [])
                entities = ai_result.get("entities", [])
                # For spreadsheets/CSV, the document parser already produces
                # authoritative tabular data — prefer it over AI reconstruction.
                # Only use AI tables when the parser didn't find any.
                if ai_result.get("tables"):
                    if category == DocumentCategory.SPREADSHEET and tables:
                        logger.debug("Keeping parser tables for spreadsheet (parser=%d, AI=%d).",
                                     len(tables), len(ai_result["tables"]))
                    else:
                        tables = ai_result["tables"]
                ai_metadata = ai_result.get("metadata", {})
                metadata.update(ai_metadata)

            # ---------------------------------------------------------
            # Fallback: local text analysis when AI returned nothing
            # ---------------------------------------------------------
            if not key_value_pairs and not entities and raw_text.strip():
                logger.info("AI returned no structured data — using local text analyzer.")
                local_result = self.text_analyzer.analyze(raw_text)
                if local_result.get("key_value_pairs"):
                    key_value_pairs = local_result["key_value_pairs"]
                if local_result.get("entities"):
                    entities = local_result["entities"]
                if local_result.get("document_type") and local_result["document_type"] != "other":
                    document_type = local_result["document_type"]
                if local_result.get("summary"):
                    summary = local_result["summary"]
                metadata.update(local_result.get("metadata", {}))

            # -----------------------------------------------------------
            # Stage 5: Output Generation
            # -----------------------------------------------------------
            self._update_status(job_id, ProcessingStage.OUTPUT_GENERATION, 85, "Generating outputs…")

            processing_time = round(time.time() - start_time, 3)

            # Build the result
            result = ExtractionResult(
                job_id=job_id,
                filename=original_filename,
                document_type=document_type,
                category=category.value if isinstance(category, DocumentCategory) else str(category),
                pages_processed=pages_processed,
                processing_time_seconds=processing_time,
                raw_text=raw_text,
                key_value_pairs=[
                    KeyValuePair(**kv) if isinstance(kv, dict) else kv
                    for kv in key_value_pairs
                ],
                entities=[
                    DocumentEntity(**e) if isinstance(e, dict) else e
                    for e in entities
                ],
                tables=[
                    TableData(**t) if isinstance(t, dict) else t
                    for t in tables
                ],
                metadata=metadata,
                summary=summary,
            )

            # Generate output files
            output_dir = settings.output_dir_path / job_id
            try:
                self.output_generator.generate_json(result, output_dir)
                self.output_generator.generate_csv(result, output_dir)
            except Exception as exc:
                logger.warning("Output file generation failed: %s", exc)

            # Store result
            ProcessingPipeline._job_results[job_id] = result

            self._update_status(job_id, ProcessingStage.COMPLETED, 100, "Processing complete.")
            logger.info(
                "Job %s completed in %.2fs: type=%s, %d pages, %d KV pairs, %d entities, %d tables",
                job_id,
                processing_time,
                document_type,
                pages_processed,
                len(key_value_pairs),
                len(entities),
                len(tables),
            )
            return result

        except Exception as exc:
            processing_time = round(time.time() - start_time, 3)
            logger.error("Pipeline failed for job %s: %s", job_id, exc)
            self._update_status(job_id, ProcessingStage.FAILED, 0, f"Error: {exc}")

            # Return partial result on failure
            return ExtractionResult(
                job_id=job_id,
                filename=original_filename,
                document_type=document_type,
                category="unknown",
                pages_processed=pages_processed,
                processing_time_seconds=processing_time,
                raw_text=raw_text,
                key_value_pairs=[
                    KeyValuePair(**kv) if isinstance(kv, dict) else kv
                    for kv in key_value_pairs
                ],
                entities=[
                    DocumentEntity(**e) if isinstance(e, dict) else e
                    for e in entities
                ],
                tables=[
                    TableData(**t) if isinstance(t, dict) else t
                    for t in tables
                ],
                metadata={"error": str(exc), **metadata},
                summary=summary,
            )

    # ------------------------------------------------------------------
    # Status tracking
    # ------------------------------------------------------------------

    def _update_status(
        self, job_id: str, stage: ProcessingStage, progress: int, message: str
    ) -> None:
        """Update the processing status for a job."""
        status = ProcessingStatus(
            job_id=job_id,
            stage=stage,
            progress=progress,
            message=message,
            started_at=ProcessingPipeline._job_statuses.get(job_id, ProcessingStatus(
                job_id=job_id, stage=stage, progress=0, message=""
            )).started_at or get_timestamp(),
            completed_at=get_timestamp() if stage in (ProcessingStage.COMPLETED, ProcessingStage.FAILED) else None,
        )
        ProcessingPipeline._job_statuses[job_id] = status
        logger.debug("Job %s: stage=%s progress=%d%% — %s", job_id, stage.value, progress, message)

    def get_status(self, job_id: str) -> ProcessingStatus | None:
        """Retrieve the current processing status for a job."""
        return ProcessingPipeline._job_statuses.get(job_id)

    def get_result(self, job_id: str) -> ExtractionResult | None:
        """Retrieve the stored result for a completed job."""
        return ProcessingPipeline._job_results.get(job_id)
