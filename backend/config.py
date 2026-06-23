"""
Configuration module for the DocDigitizer backend.

Loads settings from environment variables and .env file using Pydantic BaseSettings.
Provides centralized access to all application configuration values including
API keys, directory paths, file size limits, and supported file format mappings.
"""

import logging
from pathlib import Path
from typing import Optional

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Base directory for the backend application
BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file.

    Attributes:
        GEMINI_API_KEY: API key for Google Gemini AI services.
        UPLOAD_DIR: Directory path for uploaded files.
        OUTPUT_DIR: Directory path for generated output files.
        MAX_FILE_SIZE: Maximum allowed file size in bytes (default 50MB).
        GEMINI_MODEL: Gemini model identifier to use for AI analysis.
        TESSERACT_CMD: Absolute path to the Tesseract OCR executable.
        SUPPORTED_EXTENSIONS: Mapping of document categories to their supported file extensions.
        REJECTED_EXTENSIONS: Mapping of media categories to their rejected file extensions.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API Keys ---
    GEMINI_API_KEY: Optional[str] = None

    # --- Directory Paths ---
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"

    # --- File Constraints ---
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50 MB

    # --- AI Model ---
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # --- OCR ---
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # --- Supported File Extensions ---
    SUPPORTED_EXTENSIONS: dict[str, list[str]] = {
        "images": [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"],
        "documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"],
        "spreadsheets": [".xls", ".xlsx", ".csv"],
        "presentations": [".ppt", ".pptx"],
    }

    # --- Rejected File Extensions ---
    REJECTED_EXTENSIONS: dict[str, list[str]] = {
        "audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".wma", ".m4a"],
        "video": [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"],
    }

    @property
    def upload_dir_path(self) -> Path:
        """Resolve UPLOAD_DIR to an absolute path relative to the backend base directory."""
        path = Path(self.UPLOAD_DIR)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path.resolve()

    @property
    def output_dir_path(self) -> Path:
        """Resolve OUTPUT_DIR to an absolute path relative to the backend base directory."""
        path = Path(self.OUTPUT_DIR)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path.resolve()

    @property
    def all_supported(self) -> set[str]:
        """Flattened set of all supported file extensions."""
        return {
            ext
            for extensions in self.SUPPORTED_EXTENSIONS.values()
            for ext in extensions
        }

    @property
    def all_rejected(self) -> set[str]:
        """Flattened set of all rejected file extensions."""
        return {
            ext
            for extensions in self.REJECTED_EXTENSIONS.values()
            for ext in extensions
        }

    def is_extension_supported(self, extension: str) -> bool:
        """Check whether a file extension is supported.

        Args:
            extension: The file extension to check (e.g. '.pdf').

        Returns:
            True if the extension is in the supported set.
        """
        return extension.lower() in self.all_supported

    def is_extension_rejected(self, extension: str) -> bool:
        """Check whether a file extension is explicitly rejected.

        Args:
            extension: The file extension to check (e.g. '.mp4').

        Returns:
            True if the extension is in the rejected set.
        """
        return extension.lower() in self.all_rejected

    def get_category_for_extension(self, extension: str) -> Optional[str]:
        """Return the category name for a given supported extension.

        Args:
            extension: The file extension to look up (e.g. '.docx').

        Returns:
            The category name (e.g. 'documents') or None if not found.
        """
        ext_lower = extension.lower()
        for category, extensions in self.SUPPORTED_EXTENSIONS.items():
            if ext_lower in extensions:
                return category
        return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
# We intentionally catch validation errors so the application can still start
# even if GEMINI_API_KEY is not set (it will be required at processing time).
# ---------------------------------------------------------------------------

try:
    settings = Settings()  # type: ignore[call-arg]
    logger.info("Settings loaded successfully.")
except ValidationError as exc:
    logger.warning(
        "Settings validation failed – falling back to defaults. Details: %s",
        exc,
    )
    # Create settings with all defaults (API key will be None)
    settings = Settings.model_construct()  # type: ignore[call-arg]
except Exception as exc:  # pragma: no cover – defensive
    logger.warning(
        "Unexpected error while loading settings – falling back to defaults. Details: %s",
        exc,
    )
    settings = Settings.model_construct()  # type: ignore[call-arg]
