"""
Document Reader Tool for Intelligent Software Requirement Analyst.
Extracts clean plain text from PDF, DOCX, and TXT files.
"""

import io
import os
import logging
from typing import Optional

logger = logging.getLogger("RequirementAnalyst.DocumentReader")


def clean_extracted_text(raw_text: str) -> str:
    """Normalize whitespace and remove non-printable characters."""
    if not raw_text:
        return ""
    lines = [line.strip() for line in raw_text.splitlines()]
    # Remove consecutive empty lines
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                cleaned_lines.append("")
                prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False
    return "\n".join(cleaned_lines).strip()


def read_text_from_file_bytes(content: bytes, filename: str) -> str:
    """
    Read text from raw bytes based on file extension.
    Supported extensions: .txt, .pdf, .docx
    """
    if not content:
        raise ValueError(f"File '{filename}' is completely empty (0 bytes).")

    ext = os.path.splitext(filename)[1].lower()
    logger.info("Reading document '%s' with extension '%s' (%d bytes)", filename, ext, len(content))

    if ext == ".txt":
        # Try UTF-8 first, fallback to Latin-1
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except Exception as e:
                raise ValueError(f"Failed to decode text file '{filename}': {e}") from e
        cleaned = clean_extracted_text(text)
        if not cleaned:
            raise ValueError(f"Text file '{filename}' contains only whitespace or is empty.")
        return cleaned

    elif ext == ".pdf":
        try:
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(content))
            if len(pdf_reader.pages) == 0:
                raise ValueError(f"PDF file '{filename}' has 0 pages.")
            extracted_pages = []
            for i, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    extracted_pages.append(page_text)
            full_text = "\n\n".join(extracted_pages)
            cleaned = clean_extracted_text(full_text)
            if not cleaned:
                raise ValueError(f"PDF file '{filename}' did not yield any readable text (may be image-only scan).")
            return cleaned
        except Exception as e:
            if "did not yield" in str(e) or "0 pages" in str(e):
                raise
            raise ValueError(f"Failed to extract text from PDF '{filename}': {e}") from e

    elif ext == ".docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        paragraphs.append(row_text)
            full_text = "\n".join(paragraphs)
            cleaned = clean_extracted_text(full_text)
            if not cleaned:
                raise ValueError(f"DOCX file '{filename}' contains no readable paragraph or table text.")
            return cleaned
        except Exception as e:
            if "contains no readable" in str(e):
                raise
            raise ValueError(f"Failed to extract text from DOCX '{filename}': {e}") from e

    else:
        raise ValueError(
            f"Unsupported file format '{ext}'. Supported formats are .pdf, .docx, and .txt."
        )


def read_text_from_path(file_path: str) -> str:
    """Read and extract text from a local file path."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at path: {file_path}")
    
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        content = f.read()
    return read_text_from_file_bytes(content, filename)
