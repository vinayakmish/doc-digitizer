"""
Utility helper functions for the DocDigitizer backend.

Provides common operations such as unique ID generation, filename
sanitization, file-size formatting, directory management, and
timestamp creation used across the application.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_job_id() -> str:
    """Generate a unique job identifier based on UUID4.

    Returns:
        A lowercase hex UUID4 string (e.g. '550e8400e29b41d4a716446655440000').
    """
    return uuid.uuid4().hex


def get_file_extension(filename: str) -> str:
    """Extract the file extension from a filename in lowercase.

    Args:
        filename: The original filename (e.g. 'Report.PDF').

    Returns:
        The lowercase extension including the leading dot (e.g. '.pdf').
        Returns an empty string if there is no extension.
    """
    return Path(filename).suffix.lower()


def get_file_size_display(size_bytes: int) -> str:
    """Convert a byte count to a human-readable string.

    Args:
        size_bytes: File size in bytes.

    Returns:
        A formatted string such as '1.50 MB', '256.00 KB', or '512 B'.
    """
    if size_bytes < 0:
        return "0 B"

    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to make it safe for filesystem storage.

    Removes directory separators and special characters, keeping only
    alphanumeric characters, hyphens, underscores, and dots. Leading/
    trailing whitespace and dots are stripped to prevent hidden files.

    Args:
        filename: The original, potentially unsafe filename.

    Returns:
        A sanitized filename safe for use on most filesystems.
        Falls back to 'unnamed_file' if sanitization produces an
        empty string.
    """
    # Remove any directory components
    filename = Path(filename).name

    # Replace path separators and null bytes
    filename = filename.replace("\x00", "")

    # Keep only safe characters: alphanumeric, hyphen, underscore, dot, space
    filename = re.sub(r"[^\w\-. ]", "_", filename)

    # Collapse consecutive underscores / spaces
    filename = re.sub(r"[_ ]{2,}", "_", filename)

    # Strip leading/trailing whitespace and dots
    filename = filename.strip(" .")

    if not filename:
        filename = "unnamed_file"

    return filename


def ensure_directory(path: Path) -> None:
    """Create a directory (and parents) if it does not already exist.

    Args:
        path: The directory path to ensure exists.

    Raises:
        OSError: If directory creation fails for reasons other than
            the directory already existing.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directory exists: %s", path)
    except OSError:
        logger.exception("Failed to create directory: %s", path)
        raise


def cleanup_file(path: Path) -> None:
    """Safely delete a file, logging but not raising on failure.

    If the file does not exist, this is treated as a no-op.

    Args:
        path: The file path to delete.
    """
    try:
        if path.exists():
            path.unlink()
            logger.info("Cleaned up file: %s", path)
        else:
            logger.debug("File not found for cleanup (already removed): %s", path)
    except OSError:
        logger.exception("Failed to clean up file: %s", path)


def get_timestamp() -> str:
    """Return the current UTC time as an ISO 8601 formatted string.

    Returns:
        An ISO-format timestamp string (e.g. '2024-06-15T14:30:00+00:00').
    """
    return datetime.now(timezone.utc).isoformat()
