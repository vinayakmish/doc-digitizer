"""
Format detection and validation service.

Detects file formats via extension and MIME type, classifies documents
into categories, rejects unsupported media types, and determines whether
OCR processing is required.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

from models.schemas import DocumentCategory
from config import settings

logger = logging.getLogger(__name__)

# Extension → category mapping
_EXT_CATEGORY_MAP: dict[str, DocumentCategory] = {}
for ext in settings.SUPPORTED_EXTENSIONS.get("images", []):
    _EXT_CATEGORY_MAP[ext] = DocumentCategory.IMAGE
for ext in settings.SUPPORTED_EXTENSIONS.get("documents", []):
    if ext == ".pdf":
        _EXT_CATEGORY_MAP[ext] = DocumentCategory.PDF
    elif ext == ".txt":
        _EXT_CATEGORY_MAP[ext] = DocumentCategory.TEXT
    else:
        _EXT_CATEGORY_MAP[ext] = DocumentCategory.DOCUMENT
for ext in settings.SUPPORTED_EXTENSIONS.get("spreadsheets", []):
    _EXT_CATEGORY_MAP[ext] = DocumentCategory.SPREADSHEET
for ext in settings.SUPPORTED_EXTENSIONS.get("presentations", []):
    _EXT_CATEGORY_MAP[ext] = DocumentCategory.PRESENTATION


class FormatDetector:
    """Detects and validates document file formats."""

    def detect(self, file_path: Path, original_filename: str) -> dict[str, Any]:
        """Analyse a file and return format metadata.

        Args:
            file_path: Path to the saved file on disk.
            original_filename: The original filename provided by the user.

        Returns:
            Dict with keys: extension, category, mime_type, is_supported,
            needs_ocr.
        """
        extension = self._get_extension(original_filename)
        mime_type = self._detect_mime(file_path, extension)
        category = self.get_category(extension)
        supported = self.is_supported(original_filename)
        ocr_needed = False
        if supported and category is not None:
            ocr_needed = self.needs_ocr(file_path, category)

        result = {
            "extension": extension,
            "category": category,
            "mime_type": mime_type,
            "is_supported": supported,
            "needs_ocr": ocr_needed,
        }
        logger.info("Format detection result for '%s': %s", original_filename, result)
        return result

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def is_supported(self, filename: str) -> bool:
        """Return True if the file extension is in the supported set."""
        ext = self._get_extension(filename)
        return ext in settings.all_supported

    def is_rejected(self, filename: str) -> bool:
        """Return True if the file extension is an audio/video format."""
        ext = self._get_extension(filename)
        return ext in settings.all_rejected

    def get_category(self, extension: str) -> DocumentCategory | None:
        """Map a lowercase extension to a DocumentCategory."""
        return _EXT_CATEGORY_MAP.get(extension.lower())

    def needs_ocr(self, file_path: Path, category: DocumentCategory) -> bool:
        """Determine whether the file requires OCR processing.

        * Images always need OCR.
        * PDFs are checked for embedded text – if the average character
          count per page is below a threshold the PDF is assumed to be
          scanned.
        * All other digital formats do not require OCR.
        """
        if category == DocumentCategory.IMAGE:
            return True

        if category == DocumentCategory.PDF:
            return self._is_scanned_pdf(file_path)

        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_extension(filename: str) -> str:
        return Path(filename).suffix.lower()

    @staticmethod
    def _detect_mime(file_path: Path, extension: str) -> str:
        """Detect MIME type using python-magic with extension fallback."""
        try:
            import magic  # python-magic-bin
            mime = magic.from_file(str(file_path), mime=True)
            if mime:
                return mime
        except Exception:
            logger.debug("python-magic unavailable or failed, falling back to mimetypes.")

        guessed, _ = mimetypes.guess_type(str(file_path))
        return guessed or "application/octet-stream"

    @staticmethod
    def _is_scanned_pdf(file_path: Path, threshold: int = 50) -> bool:
        """Check whether a PDF is scanned (image-based) by examining text density.

        If the average characters per page is below *threshold* the PDF is
        considered scanned.
        """
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(file_path))
            total_chars = 0
            page_count = len(doc)
            if page_count == 0:
                doc.close()
                return True

            for page in doc:
                total_chars += len(page.get_text())
            doc.close()

            avg_chars = total_chars / page_count
            is_scanned = avg_chars < threshold
            logger.debug(
                "PDF text density check: %d avg chars/page → scanned=%s",
                avg_chars,
                is_scanned,
            )
            return is_scanned
        except Exception as exc:
            logger.warning("Could not analyse PDF text density: %s", exc)
            return True  # err on the side of OCR
