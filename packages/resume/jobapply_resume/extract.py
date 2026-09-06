"""Text extraction from uploaded resume files.

Extraction is deliberately deterministic and offline: no model is involved in reading
the user's document, so the text we store is exactly what the file contains.
"""

from __future__ import annotations

import io
import re
from typing import Protocol

from jobapply_shared.errors import ValidationError_

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"  # DOCX is a zip container

SUPPORTED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    "text/plain": "txt",
    "text/markdown": "txt",
}

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)


def detect_kind(data: bytes, filename: str | None = None, content_type: str | None = None) -> str:
    """Determine the file kind from magic bytes first, falling back to the declared
    content type and extension. Magic bytes win: a client can lie about both."""
    if data.startswith(PDF_MAGIC):
        return "pdf"
    if data.startswith(ZIP_MAGIC):
        return "docx"
    if content_type and content_type.split(";")[0].strip() in SUPPORTED_CONTENT_TYPES:
        return SUPPORTED_CONTENT_TYPES[content_type.split(";")[0].strip()]
    if filename:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix in {"pdf", "docx", "txt", "md"}:
            return "txt" if suffix in {"txt", "md"} else suffix
    # A resume that decodes cleanly as UTF-8 is treated as plain text.
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError_(
            "Unsupported file type. Upload a PDF, DOCX or plain-text resume.",
            code="unsupported_file_type",
        ) from exc
    return "txt"


class TextExtractor(Protocol):
    kind: str

    def extract(self, data: bytes) -> str: ...


class PdfTextExtractor:
    kind = "pdf"

    def extract(self, data: bytes) -> str:
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # pragma: no cover - depends on the uploaded file
            raise ValidationError_(
                "Could not read this PDF. If it is a scan, upload a text-based PDF or "
                "paste the resume text instead.",
                code="pdf_unreadable",
            ) from exc
        return "\n".join(pages)


class DocxTextExtractor:
    kind = "docx"

    def extract(self, data: bytes) -> str:
        import docx

        try:
            document = docx.Document(io.BytesIO(data))
        except Exception as exc:
            raise ValidationError_(
                "Could not read this DOCX file.", code="docx_unreadable"
            ) from exc
        lines = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)


class PlainTextExtractor:
    kind = "txt"

    def extract(self, data: bytes) -> str:
        return data.decode("utf-8", errors="replace")


_EXTRACTORS: dict[str, TextExtractor] = {
    "pdf": PdfTextExtractor(),
    "docx": DocxTextExtractor(),
    "txt": PlainTextExtractor(),
}


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_RE.sub("", text)
    text = text.replace("••", "•").replace("\xa0", " ")
    text = _TRAILING_WS_RE.sub("", text)
    return _MULTI_BLANK_RE.sub("\n\n", text).strip()


def extract_text(
    data: bytes, *, filename: str | None = None, content_type: str | None = None
) -> tuple[str, str]:
    """Return ``(text, kind)`` for an uploaded resume."""
    if not data:
        raise ValidationError_("The uploaded file is empty.", code="empty_file")
    kind = detect_kind(data, filename, content_type)
    text = clean_text(_EXTRACTORS[kind].extract(data))
    if not text.strip():
        raise ValidationError_(
            "No text could be extracted from this file. If it is a scanned image, "
            "paste the resume text instead.",
            code="no_text_extracted",
        )
    return text, kind
