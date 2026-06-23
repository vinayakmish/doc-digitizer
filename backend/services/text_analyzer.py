"""
Local text analysis fallback.

Extracts key-value pairs, entities, and section data from raw text
using regex patterns. Used when the Gemini API is unavailable or
rate-limited.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for entity extraction
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[\s-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}")
URL_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}(?:/[^\s,|]*)?")
DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"           # DD/MM/YYYY or MM-DD-YYYY
    r"|\d{4}[/-]\d{1,2}[/-]\d{1,2}"             # YYYY-MM-DD
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"  # Month DD, YYYY
    r"|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"    # DD Month YYYY
    r"|\d{4}\s*[-–]\s*(?:\d{4}|[Pp]resent|[Pp]ursuing|[Cc]urrent)"  # 2023 - 2027
    r"|\b(?:19|20)\d{2}\b"                       # standalone year
    r")\b",
    re.IGNORECASE,
)
AMOUNT_PATTERN = re.compile(
    r"(?:[\$€£₹¥]|(?:Rs\.?|INR|USD|EUR)\s*)"
    r"\s*\d[\d,]*(?:\.\d{1,2})?",
    re.IGNORECASE,
)
PERCENTAGE_PATTERN = re.compile(r"\d+(?:\.\d+)?%")
KV_COLON_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9 _/&-]{1,40})\s*[:–—]\s*(.+)$", re.MULTILINE)
KV_PIPE_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9 _/&-]{1,40})\s*\|\s*(.+)$", re.MULTILINE)
CGPA_PATTERN = re.compile(r"(?:CGPA|GPA|CPI)\s*[:=]?\s*(\d+\.?\d*)\s*/?\s*(\d+\.?\d*)?", re.IGNORECASE)
SCORE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")

# Section headers commonly found in resumes/documents
SECTION_HEADERS = [
    "SUMMARY", "PROFESSIONAL SUMMARY", "PROFILE", "OBJECTIVE",
    "EDUCATION", "ACADEMIC", "QUALIFICATIONS",
    "EXPERIENCE", "WORK EXPERIENCE", "EMPLOYMENT",
    "SKILLS", "TECHNICAL SKILLS", "COMPETENCIES",
    "PROJECTS", "ACHIEVEMENTS", "CERTIFICATIONS", "CERTIFICATES",
    "ACTIVITIES", "EXTRACURRICULAR", "INTERESTS", "HOBBIES",
    "REFERENCES", "PUBLICATIONS", "AWARDS",
    "PERSONAL INFORMATION", "PERSONAL DETAILS",
    "CONTACT", "CONTACT INFORMATION",
    "LANGUAGES", "TOOLS", "PLATFORMS",
]


class TextAnalyzer:
    """Extracts structured data from raw text using regex patterns."""

    def analyze(self, text: str) -> dict[str, Any]:
        """Analyse raw text and extract structured information.

        Args:
            text: The raw text to analyse.

        Returns:
            Dict with keys: document_type, summary, key_value_pairs,
            entities, tables, metadata.
        """
        if not text or not text.strip():
            return self._empty_result()

        key_value_pairs = self._extract_kv_pairs(text)
        entities = self._extract_entities(text)
        doc_type = self._detect_document_type(text)
        summary = self._generate_summary(text)

        logger.info(
            "Local text analysis: type=%s, %d KV pairs, %d entities",
            doc_type, len(key_value_pairs), len(entities),
        )

        return {
            "document_type": doc_type,
            "summary": summary,
            "raw_text": "",  # don't override — caller already has it
            "key_value_pairs": key_value_pairs,
            "entities": entities,
            "tables": [],
            "metadata": {"extraction_method": "local_regex"},
        }

    # ------------------------------------------------------------------
    # Key-Value pair extraction
    # ------------------------------------------------------------------

    def _extract_kv_pairs(self, text: str) -> list[dict[str, str]]:
        """Extract key-value pairs from text using multiple patterns."""
        pairs: list[dict[str, str]] = []
        seen_keys: set[str] = set()

        # Pattern 1: "Key: Value" or "Key – Value" lines
        for match in KV_COLON_PATTERN.finditer(text):
            key = match.group(1).strip()
            value = match.group(2).strip()
            if self._is_valid_kv(key, value) and key.lower() not in seen_keys:
                pairs.append({"key": key, "value": value})
                seen_keys.add(key.lower())

        # Pattern 2: "Key | Value" lines
        for match in KV_PIPE_PATTERN.finditer(text):
            key = match.group(1).strip()
            value = match.group(2).strip()
            if self._is_valid_kv(key, value) and key.lower() not in seen_keys:
                pairs.append({"key": key, "value": value})
                seen_keys.add(key.lower())

        # Pattern 3: CGPA/GPA patterns
        for match in CGPA_PATTERN.finditer(text):
            key = "CGPA"
            value = match.group(1)
            if match.group(2):
                value += f" / {match.group(2)}"
            if key.lower() not in seen_keys:
                pairs.append({"key": key, "value": value})
                seen_keys.add(key.lower())

        # Pattern 4: Extract name from first line (common in resumes)
        first_line = text.strip().split("\n")[0].strip()
        if first_line and len(first_line) < 60 and first_line.isupper() or (
            len(first_line.split()) <= 4 and not any(c in first_line for c in ":@|")
        ):
            if "name" not in seen_keys:
                pairs.insert(0, {"key": "Name", "value": first_line})
                seen_keys.add("name")

        # Pattern 5: Extract email, phone, LinkedIn etc. as KV pairs
        emails = EMAIL_PATTERN.findall(text)
        if emails and "email" not in seen_keys:
            pairs.append({"key": "Email", "value": emails[0]})
            seen_keys.add("email")

        phones = PHONE_PATTERN.findall(text)
        if phones and "phone" not in seen_keys:
            # Clean up phone number
            phone = phones[0].strip()
            if len(phone) >= 10:
                pairs.append({"key": "Phone", "value": phone})
                seen_keys.add("phone")

        # LinkedIn / GitHub URLs
        for url in URL_PATTERN.findall(text):
            url_lower = url.lower()
            if "linkedin" in url_lower and "linkedin" not in seen_keys:
                pairs.append({"key": "LinkedIn", "value": url})
                seen_keys.add("linkedin")
            elif "github" in url_lower and "github" not in seen_keys:
                pairs.append({"key": "GitHub", "value": url})
                seen_keys.add("github")

        # Pattern 6: Section-based extraction
        sections = self._extract_sections(text)
        for section_name, section_text in sections.items():
            clean_name = section_name.strip().title()
            clean_text = section_text.strip()
            if clean_text and len(clean_text) < 500 and clean_name.lower() not in seen_keys:
                pairs.append({"key": clean_name, "value": clean_text})
                seen_keys.add(clean_name.lower())

        return pairs

    # ------------------------------------------------------------------
    # Entity extraction
    # ------------------------------------------------------------------

    def _extract_entities(self, text: str) -> list[dict[str, str]]:
        """Extract named entities from text using regex."""
        entities: list[dict[str, str]] = []
        seen: set[str] = set()

        # Emails
        for email in EMAIL_PATTERN.findall(text):
            if email not in seen:
                entities.append({"entity_type": "EMAIL", "value": email})
                seen.add(email)

        # Phones
        for phone in PHONE_PATTERN.findall(text):
            phone = phone.strip()
            if len(phone) >= 10 and phone not in seen:
                entities.append({"entity_type": "PHONE", "value": phone})
                seen.add(phone)

        # URLs (filter out false positives like React.js, Node.js, email domains)
        false_urls = {"react.js", "node.js", "vue.js", "next.js", "express.js",
                      "angular.js", "three.js", "d3.js", "p5.js", "chart.js",
                      "gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}
        for url in URL_PATTERN.findall(text):
            if url not in seen and not url.endswith("."):
                url_lower = url.lower()
                if url_lower in false_urls:
                    continue
                if "linkedin" in url_lower:
                    entities.append({"entity_type": "URL", "value": url})
                elif "github" in url_lower:
                    entities.append({"entity_type": "URL", "value": url})
                elif "." in url and len(url) > 10:
                    entities.append({"entity_type": "URL", "value": url})
                seen.add(url)

        # Dates / date ranges
        for match in DATE_PATTERN.finditer(text):
            date_str = match.group().strip()
            if date_str not in seen and len(date_str) > 3:
                entities.append({"entity_type": "DATE", "value": date_str})
                seen.add(date_str)

        # Money / amounts
        for match in AMOUNT_PATTERN.finditer(text):
            amount = match.group().strip()
            if amount not in seen:
                entities.append({"entity_type": "AMOUNT", "value": amount})
                seen.add(amount)

        # Percentages
        for match in PERCENTAGE_PATTERN.finditer(text):
            pct = match.group().strip()
            if pct not in seen:
                entities.append({"entity_type": "PERCENTAGE", "value": pct})
                seen.add(pct)

        # Name from first line
        first_line = text.strip().split("\n")[0].strip()
        if first_line and len(first_line.split()) <= 4 and len(first_line) < 50:
            if not any(c in first_line for c in ":@|.0123456789"):
                entities.insert(0, {"entity_type": "PERSON", "value": first_line})

        # Organizations — look for common patterns
        org_patterns = [
            re.compile(r"(?:Institute|University|College|School|Academy|Lab)\s+(?:of\s+)?[\w\s&]+", re.IGNORECASE),
        ]
        for pat in org_patterns:
            for match in pat.finditer(text):
                org = match.group().strip()
                if org not in seen and len(org) > 5:
                    entities.append({"entity_type": "ORGANIZATION", "value": org})
                    seen.add(org)

        return entities

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_sections(self, text: str) -> dict[str, str]:
        """Split text into sections based on common document headers."""
        sections: dict[str, str] = {}
        lines = text.split("\n")
        current_section: str | None = None
        current_content: list[str] = []

        for line in lines:
            stripped = line.strip().upper()
            # Check if this line is a section header
            matched_header = None
            for header in SECTION_HEADERS:
                if stripped == header or stripped.startswith(header + " ") or stripped.startswith(header + ":"):
                    matched_header = header
                    break

            if matched_header:
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = matched_header
                current_content = []
            elif current_section:
                current_content.append(line.strip())

        # Save last section
        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _detect_document_type(self, text: str) -> str:
        """Detect document type from text content."""
        text_lower = text.lower()

        type_signals = {
            "resume": ["experience", "education", "skills", "objective", "summary", "cgpa", "gpa"],
            "invoice": ["invoice", "bill to", "due date", "total amount", "payment"],
            "receipt": ["receipt", "paid", "transaction", "total", "change"],
            "letter": ["dear", "sincerely", "regards", "yours truly"],
            "report": ["abstract", "introduction", "conclusion", "methodology", "references"],
            "form": ["please fill", "applicant", "signature", "date of birth"],
            "certificate": ["certificate", "certify", "awarded", "completion"],
            "contract": ["agreement", "parties", "terms and conditions", "hereby"],
        }

        best_type = "other"
        best_score = 0
        for doc_type, keywords in type_signals.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_type = doc_type

        return best_type if best_score >= 2 else "other"

    def _generate_summary(self, text: str) -> str:
        """Generate a basic summary from the first few meaningful lines."""
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        # Take first 3 non-empty lines as a crude summary
        summary_lines = lines[:3]
        summary = " ".join(summary_lines)
        if len(summary) > 300:
            summary = summary[:297] + "..."
        return summary

    @staticmethod
    def _is_valid_kv(key: str, value: str) -> bool:
        """Check if a key-value pair is meaningful."""
        if not key or not value:
            return False
        if len(key) < 2 or len(key) > 50:
            return False
        if len(value) < 1 or len(value) > 500:
            return False
        # Skip section headers used as keys with long values
        if key.upper() in SECTION_HEADERS and len(value) > 200:
            return False
        return True

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "document_type": "other",
            "summary": "",
            "raw_text": "",
            "key_value_pairs": [],
            "entities": [],
            "tables": [],
            "metadata": {},
        }
