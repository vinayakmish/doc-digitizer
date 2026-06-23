"""
Google Gemini AI extraction engine.

Uses the google-genai SDK to send documents (text, images, PDFs) to
Gemini for intelligent structured data extraction including key-value
pairs, entities, tables, and document classification.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import time
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

# The structured extraction prompt sent to Gemini
_EXTRACTION_PROMPT = """\
You are an expert document analysis AI. Analyse the provided document and extract ALL information into a structured JSON object.

Your response MUST be a valid JSON object with exactly these keys:

{{
  "document_type": "One of: invoice, receipt, form, report, letter, certificate, spreadsheet, presentation, id_card, contract, resume, other",
  "summary": "A concise 2-3 sentence summary of the document's content and purpose.",
  "raw_text": "The complete text content extracted from the document, preserving paragraph structure.",
  "key_value_pairs": [
    {{"key": "Field Name", "value": "Field Value"}}
  ],
  "entities": [
    {{"entity_type": "PERSON|DATE|ADDRESS|ID|ORGANIZATION|PHONE|EMAIL|AMOUNT|CURRENCY|URL", "value": "extracted value"}}
  ],
  "tables": [
    {{"title": "Table description or null", "headers": ["col1", "col2"], "rows": [["val1", "val2"]]}}
  ],
  "metadata": {{
    "language": "detected language code (e.g. en, es, fr)",
    "page_count": 1
  }}
}}

RULES:
1. Extract ALL key-value pairs visible in the document (labels and their values).
2. Identify ALL named entities: people, dates, addresses, IDs, organisations, phone numbers, emails, monetary amounts.
3. Extract ALL tables completely — do not skip rows or columns. If no tables exist, return an empty array.
4. The raw_text should contain the full text content, preserving structure.
5. Be thorough — extract every piece of information. Missing data is worse than extra data.
6. For confidence: do your best to be accurate. If uncertain about a value, still include it.
"""

_TEXT_ANALYSIS_PROMPT = """\
You are an expert document analysis AI. The following text was extracted from a document. Analyse it and extract ALL structured information.

--- DOCUMENT TEXT ---
{text}
--- END DOCUMENT TEXT ---

Your response MUST be a valid JSON object with exactly these keys:

{{
  "document_type": "One of: invoice, receipt, form, report, letter, certificate, spreadsheet, presentation, id_card, contract, resume, other",
  "summary": "A concise 2-3 sentence summary of the document.",
  "key_value_pairs": [
    {{"key": "Field Name", "value": "Field Value"}}
  ],
  "entities": [
    {{"entity_type": "PERSON|DATE|ADDRESS|ID|ORGANIZATION|PHONE|EMAIL|AMOUNT|CURRENCY|URL", "value": "extracted value"}}
  ],
  "tables": [
    {{"title": "Table description or null", "headers": ["col1", "col2"], "rows": [["val1", "val2"]]}}
  ],
  "metadata": {{
    "language": "detected language code",
    "page_count": 1
  }}
}}

Extract ALL key-value pairs, entities, and tables. Be thorough.
"""


class AIExtractor:
    """Gemini-powered document extraction engine."""

    def __init__(self) -> None:
        self._client: Any = None
        self._model: str = settings.GEMINI_MODEL or "gemini-2.5-flash"

        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Gemini AI extractor initialised (model: %s).", self._model)
            except Exception as exc:
                logger.error("Failed to initialise Gemini client: %s", exc)
        else:
            logger.warning("GEMINI_API_KEY not set — AI extraction unavailable.")

    def is_available(self) -> bool:
        """Return True if the Gemini client is initialised."""
        return self._client is not None

    # ------------------------------------------------------------------
    # Public extraction methods
    # ------------------------------------------------------------------

    def extract_from_text(self, text: str, document_type: str | None = None) -> dict[str, Any]:
        """Send pre-extracted text to Gemini for intelligent structuring.

        Args:
            text: The raw text extracted from a document.
            document_type: Optional hint about the document type.

        Returns:
            Parsed extraction dict.
        """
        if not self.is_available():
            return self._empty_result()

        prompt = _TEXT_ANALYSIS_PROMPT.format(text=text[:50000])  # cap at ~50k chars
        response_text = self._call_gemini([prompt])
        return self._parse_response(response_text)

    def extract_from_image(self, image_path: Path) -> dict[str, Any]:
        """Send an image to Gemini for OCR + structured extraction.

        Args:
            image_path: Path to the image file.

        Returns:
            Parsed extraction dict.
        """
        if not self.is_available():
            return self._empty_result()

        from google.genai import types

        mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
        image_bytes = image_path.read_bytes()
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime)

        response_text = self._call_gemini([image_part, _EXTRACTION_PROMPT])
        return self._parse_response(response_text)

    def extract_from_pdf(self, pdf_path: Path) -> dict[str, Any]:
        """Send a PDF directly to Gemini for extraction.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Parsed extraction dict.
        """
        if not self.is_available():
            return self._empty_result()

        from google.genai import types

        pdf_bytes = pdf_path.read_bytes()
        pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")

        response_text = self._call_gemini([pdf_part, _EXTRACTION_PROMPT])
        return self._parse_response(response_text)

    def extract_from_images(self, image_paths: list[Path]) -> dict[str, Any]:
        """Send multiple images (e.g. multi-page document) to Gemini.

        Args:
            image_paths: List of image file paths.

        Returns:
            Parsed extraction dict.
        """
        if not self.is_available():
            return self._empty_result()

        from google.genai import types

        contents: list[Any] = []
        for path in image_paths:
            mime = mimetypes.guess_type(str(path))[0] or "image/png"
            contents.append(types.Part.from_bytes(data=path.read_bytes(), mime_type=mime))

        contents.append(
            _EXTRACTION_PROMPT
            + f"\n\nThis document has {len(image_paths)} pages. "
            "Analyse all pages together as a single document."
        )

        response_text = self._call_gemini(contents)
        result = self._parse_response(response_text)
        result.setdefault("metadata", {})["page_count"] = len(image_paths)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_gemini(self, contents: list[Any], retries: int = 4) -> str:
        """Call the Gemini API with retry logic and model fallback.

        Args:
            contents: List of content parts to send.
            retries: Number of retry attempts per model.

        Returns:
            The response text from Gemini.
        """
        from google.genai import types

        # Try primary model first, then fallback
        models_to_try = [self._model]
        fallback = "gemini-2.0-flash"
        if self._model != fallback:
            models_to_try.append(fallback)

        last_error: Exception | None = None
        for model in models_to_try:
            for attempt in range(1, retries + 1):
                try:
                    response = self._client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.0,
                        ),
                    )
                    if model != self._model:
                        logger.info("Succeeded with fallback model: %s", model)
                    return response.text or ""
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Gemini API call (model=%s) attempt %d/%d failed: %s",
                        model, attempt, retries, exc,
                    )
                    # If 503/overloaded, try fallback model sooner
                    if "503" in str(exc) or "UNAVAILABLE" in str(exc):
                        if attempt >= 2 and model == self._model and len(models_to_try) > 1:
                            logger.info("Switching to fallback model: %s", fallback)
                            break
                    if attempt < retries:
                        time.sleep(2 ** attempt)  # exponential backoff

        logger.error("Gemini API call failed after all retries: %s", last_error)
        return ""

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        """Parse the JSON response from Gemini into our schema format.

        Handles malformed JSON gracefully by attempting cleanup.
        """
        if not response_text:
            return self._empty_result()

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse Gemini response as JSON: %s", exc)
                return {
                    "document_type": "other",
                    "summary": "",
                    "raw_text": response_text,
                    "key_value_pairs": [],
                    "entities": [],
                    "tables": [],
                    "metadata": {},
                }

        # Normalise structure
        result: dict[str, Any] = {
            "document_type": data.get("document_type", "other"),
            "summary": data.get("summary", ""),
            "raw_text": data.get("raw_text", ""),
            "key_value_pairs": [],
            "entities": [],
            "tables": [],
            "metadata": data.get("metadata", {}),
        }

        # Key-value pairs
        for kv in data.get("key_value_pairs", []):
            if isinstance(kv, dict) and "key" in kv and "value" in kv:
                result["key_value_pairs"].append({
                    "key": str(kv["key"]),
                    "value": str(kv["value"]),
                    "confidence": kv.get("confidence"),
                })

        # Entities
        for ent in data.get("entities", []):
            if isinstance(ent, dict) and "entity_type" in ent and "value" in ent:
                result["entities"].append({
                    "entity_type": str(ent["entity_type"]).upper(),
                    "value": str(ent["value"]),
                    "confidence": ent.get("confidence"),
                })

        # Tables
        for tbl in data.get("tables", []):
            if isinstance(tbl, dict) and "headers" in tbl and "rows" in tbl:
                result["tables"].append({
                    "title": tbl.get("title"),
                    "headers": [str(h) for h in tbl["headers"]],
                    "rows": [[str(c) for c in row] for row in tbl["rows"]],
                })

        logger.info(
            "Parsed Gemini response: type=%s, %d KV pairs, %d entities, %d tables",
            result["document_type"],
            len(result["key_value_pairs"]),
            len(result["entities"]),
            len(result["tables"]),
        )
        return result

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        """Return an empty extraction result dict."""
        return {
            "document_type": "other",
            "summary": "",
            "raw_text": "",
            "key_value_pairs": [],
            "entities": [],
            "tables": [],
            "metadata": {},
        }
