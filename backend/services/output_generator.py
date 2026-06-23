"""
Structured output generator.

Converts ExtractionResult objects into downloadable JSON and CSV files.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from models.schemas import ExtractionResult, KeyValuePair, DocumentEntity, TableData

logger = logging.getLogger(__name__)


class OutputGenerator:
    """Generates JSON and CSV output files from extraction results."""

    def generate_json(self, result: ExtractionResult, output_dir: Path) -> Path:
        """Save the extraction result as a formatted JSON file.

        Args:
            result: The extraction result to serialise.
            output_dir: Directory to write the file into.

        Returns:
            Path to the generated JSON file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        data = self.to_json_dict(result)
        out_path = output_dir / f"{result.job_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info("JSON output written to %s", out_path)
        return out_path

    def generate_csv(self, result: ExtractionResult, output_dir: Path) -> Path:
        """Generate CSV file(s) from the extraction result.

        Creates a combined CSV with separate sections for key-value pairs,
        entities, and tables.

        Args:
            result: The extraction result.
            output_dir: Directory to write files into.

        Returns:
            Path to the main CSV file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{result.job_id}.csv"

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Primary output: clean key,value pairs
            if result.key_value_pairs:
                writer.writerow(["key", "value"])
                for kv in result.key_value_pairs:
                    writer.writerow([kv.key, kv.value])

            # If there are also entities, append them
            elif result.entities:
                writer.writerow(["key", "value"])
                for ent in result.entities:
                    writer.writerow([ent.entity_type, ent.value])

            # If there are tables but no KV pairs, output table data as key,value
            elif result.tables:
                writer.writerow(["key", "value"])
                for table in result.tables:
                    headers = table.headers or []
                    for row in table.rows:
                        cells = list(row) if isinstance(row, (list, tuple)) else [row]
                        for col_idx, header in enumerate(headers):
                            value = cells[col_idx] if col_idx < len(cells) else ""
                            if str(header).strip() and str(value).strip():
                                writer.writerow([header, value])

        logger.info("CSV output written to %s", out_path)
        return out_path

    def to_json_dict(self, result: ExtractionResult) -> dict[str, Any]:
        """Convert an ExtractionResult to a JSON-serialisable dict."""
        return {
            "job_id": result.job_id,
            "filename": result.filename,
            "document_type": result.document_type,
            "category": result.category,
            "pages_processed": result.pages_processed,
            "processing_time_seconds": round(result.processing_time_seconds, 3),
            "summary": result.summary,
            "raw_text": result.raw_text,
            "key_value_pairs": [
                {"key": kv.key, "value": kv.value, "confidence": kv.confidence}
                for kv in result.key_value_pairs
            ],
            "entities": [
                {"entity_type": e.entity_type, "value": e.value, "confidence": e.confidence}
                for e in result.entities
            ],
            "tables": [
                {
                    "title": t.title,
                    "headers": t.headers,
                    "rows": t.rows,
                    "page": t.page,
                }
                for t in result.tables
            ],
            "metadata": result.metadata,
        }
