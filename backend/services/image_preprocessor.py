"""
OpenCV image preprocessing pipeline for document images.

Applies grayscale conversion, denoising, contrast enhancement, binarization,
deskewing, orientation correction, and border removal to improve OCR accuracy.
Also provides PDF page rendering via PyMuPDF.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Default pipeline configuration — all steps enabled
DEFAULT_OPTIONS: dict[str, bool] = {
    "grayscale": True,
    "denoise": True,
    "enhance_contrast": True,
    "binarize": True,
    "deskew": True,
    "correct_orientation": False,  # requires Tesseract
    "remove_borders": False,
}


class ImagePreprocessor:
    """Configurable image preprocessing pipeline for document OCR."""

    def preprocess(
        self,
        image_path: Path,
        options: dict[str, bool] | None = None,
    ) -> tuple[np.ndarray, Path]:
        """Run the full preprocessing pipeline on *image_path*.

        Args:
            image_path: Path to the input image.
            options: Dict to enable/disable individual steps. Uses
                DEFAULT_OPTIONS for any missing keys.

        Returns:
            Tuple of (processed image array, path to saved processed image).
        """
        opts = {**DEFAULT_OPTIONS, **(options or {})}
        img = self._load_image(image_path)

        steps: list[tuple[str, Any]] = [
            ("grayscale", self._to_grayscale),
            ("denoise", self._denoise),
            ("enhance_contrast", self._enhance_contrast),
            ("binarize", self._binarize),
            ("deskew", self._deskew),
            ("correct_orientation", self._correct_orientation),
            ("remove_borders", self._remove_borders),
        ]

        for step_name, step_fn in steps:
            if not opts.get(step_name, False):
                continue
            try:
                img = step_fn(img)
                logger.debug("Preprocessing step '%s' completed.", step_name)
            except Exception as exc:
                logger.warning("Preprocessing step '%s' failed: %s — skipping.", step_name, exc)

        # Save processed image
        out_dir = Path(tempfile.mkdtemp(prefix="docdigitizer_"))
        out_path = out_dir / f"preprocessed_{image_path.stem}.png"
        cv2.imwrite(str(out_path), img)
        logger.info("Preprocessed image saved to %s", out_path)
        return img, out_path

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    @staticmethod
    def _load_image(path: Path) -> np.ndarray:
        """Load image from disk using OpenCV."""
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Could not load image: {path}")
        return img

    @staticmethod
    def _to_grayscale(img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 2:
            return img
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _denoise(img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 2:
            return cv2.fastNlMeansDenoising(img, None, h=10, templateWindowSize=7, searchWindowSize=21)
        return cv2.fastNlMeansDenoisingColored(img, None, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21)

    @staticmethod
    def _enhance_contrast(img: np.ndarray) -> np.ndarray:
        gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)

    @staticmethod
    def _binarize(img: np.ndarray) -> np.ndarray:
        gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

    @staticmethod
    def _deskew(img: np.ndarray) -> np.ndarray:
        """Detect and correct text skew using minAreaRect."""
        gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Invert so text pixels are white
        inverted = cv2.bitwise_not(gray)
        coords = np.column_stack(np.where(inverted > 0))
        if len(coords) < 100:
            return img  # not enough data

        rect = cv2.minAreaRect(coords)
        angle = rect[-1]

        # Normalise angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5:
            return img  # already straight

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
        logger.debug("Deskew: rotated by %.2f°", angle)
        return rotated

    @staticmethod
    def _correct_orientation(img: np.ndarray) -> np.ndarray:
        """Try to correct 90°/180°/270° rotations using Tesseract OSD."""
        try:
            import pytesseract
            from PIL import Image

            pil_img = Image.fromarray(
                img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            )
            osd = pytesseract.image_to_osd(pil_img, config="--psm 0")
            rotation = 0
            for line in osd.splitlines():
                if "Rotate:" in line:
                    rotation = int(line.split(":")[-1].strip())
                    break

            if rotation == 0:
                return img

            h, w = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, -rotation, 1.0)
            cos_a = abs(M[0, 0])
            sin_a = abs(M[0, 1])
            new_w = int(h * sin_a + w * cos_a)
            new_h = int(h * cos_a + w * sin_a)
            M[0, 2] += (new_w - w) / 2
            M[1, 2] += (new_h - h) / 2
            rotated = cv2.warpAffine(img, M, (new_w, new_h), borderMode=cv2.BORDER_REPLICATE)
            logger.debug("Orientation corrected by %d°", rotation)
            return rotated
        except Exception as exc:
            logger.debug("Orientation correction skipped: %s", exc)
            return img

    @staticmethod
    def _remove_borders(img: np.ndarray) -> np.ndarray:
        """Remove dark borders using contour detection."""
        gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img

        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)

        # Only crop if the detected region is reasonably large
        img_h, img_w = img.shape[:2]
        if w > img_w * 0.5 and h > img_h * 0.5:
            return img[y : y + h, x : x + w]
        return img

    # ------------------------------------------------------------------
    # PDF rendering
    # ------------------------------------------------------------------

    @staticmethod
    def render_pdf_pages(pdf_path: Path, dpi: int = 300) -> list[Path]:
        """Render each page of a PDF to a PNG image using PyMuPDF.

        Returns:
            List of paths to the rendered page images.
        """
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        out_dir = Path(tempfile.mkdtemp(prefix="docdigitizer_pdf_"))
        image_paths: list[Path] = []

        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            out_path = out_dir / f"page_{i + 1:04d}.png"
            pix.save(str(out_path))
            image_paths.append(out_path)
            logger.debug("Rendered PDF page %d → %s", i + 1, out_path)

        doc.close()
        logger.info("Rendered %d PDF pages to images in %s", len(image_paths), out_dir)
        return image_paths
