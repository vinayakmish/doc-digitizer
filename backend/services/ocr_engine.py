"""
Tesseract OCR fallback engine.

Wraps pytesseract to provide text extraction and confidence scoring.
Handles the case where Tesseract is not installed gracefully.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


class OCREngine:
    """Tesseract-based OCR engine used as a fallback when Gemini API is unavailable."""

    def __init__(self) -> None:
        self._available: bool = False
        try:
            import pytesseract

            tesseract_path = Path(settings.TESSERACT_CMD)
            if tesseract_path.is_file():
                pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)
                self._available = True
                logger.info("Tesseract OCR initialised at %s", tesseract_path)
            else:
                # Try system PATH
                try:
                    pytesseract.get_tesseract_version()
                    self._available = True
                    logger.info("Tesseract OCR found on system PATH.")
                except Exception:
                    logger.warning(
                        "Tesseract binary not found at '%s' and not on PATH. "
                        "OCR fallback will be unavailable.",
                        tesseract_path,
                    )
        except ImportError:
            logger.warning("pytesseract package not installed. OCR fallback unavailable.")

    def is_available(self) -> bool:
        """Return True if Tesseract is installed and accessible."""
        return self._available

    def ocr_image(self, image_path: Path, lang: str = "eng") -> dict[str, Any]:
        """OCR a single image file.

        Returns:
            Dict with keys: text, confidence, words.
        """
        if not self._available:
            return {"text": "", "confidence": 0.0, "words": 0}

        import pytesseract
        from PIL import Image

        img = Image.open(str(image_path))
        text = pytesseract.image_to_string(img, lang=lang)
        confidence = self._get_confidence(img, lang)
        word_count = len(text.split()) if text.strip() else 0

        logger.debug(
            "OCR result for '%s': %d words, %.1f%% confidence",
            image_path.name,
            word_count,
            confidence,
        )
        return {"text": text.strip(), "confidence": confidence, "words": word_count}

    def ocr_images(self, image_paths: list[Path], lang: str = "eng") -> dict[str, Any]:
        """OCR multiple images (e.g. rendered PDF pages) and merge results.

        Returns:
            Dict with keys: text, confidence, words, pages.
        """
        all_text: list[str] = []
        total_confidence = 0.0
        total_words = 0

        for path in image_paths:
            result = self.ocr_image(path, lang)
            all_text.append(result["text"])
            total_confidence += result["confidence"]
            total_words += result["words"]

        avg_confidence = total_confidence / len(image_paths) if image_paths else 0.0

        return {
            "text": "\n\n".join(all_text),
            "confidence": round(avg_confidence, 2),
            "words": total_words,
            "pages": len(image_paths),
        }

    def get_text(self, image_path: Path) -> str:
        """Simple text extraction from an image."""
        return self.ocr_image(image_path).get("text", "")

    def get_confidence(self, image_path: Path) -> float:
        """Return the average OCR confidence for an image."""
        return self.ocr_image(image_path).get("confidence", 0.0)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _get_confidence(pil_image: Any, lang: str = "eng") -> float:
        """Compute mean confidence from pytesseract word-level data."""
        try:
            import pytesseract
            import pandas as pd

            data = pytesseract.image_to_data(pil_image, lang=lang, output_type=pytesseract.Output.DATAFRAME)
            # Filter to actual words (conf != -1)
            valid = data[data["conf"] != -1]
            if valid.empty:
                return 0.0
            return round(float(valid["conf"].mean()), 2)
        except Exception:
            return 0.0
