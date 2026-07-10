"""PDF ingest: raw bytes for the API document block, plain text for the
deterministic quote-verification corpus.

The text is extracted per page with pypdf (importable in the miniconda base
env). The verification corpus is the concatenation of the per-page text with a
normalization applied at match time (see validate.normalize_quote), NOT here:
the raw extracted text is kept verbatim so page offsets stay meaningful.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Ingested:
    """The two views of a PDF the pipeline needs."""
    pdf_b64: str          # base64 with no newlines, for the API document block
    pages: tuple[str, ...]  # per-page extracted text (1-indexed by position+1)
    full_text: str        # all pages joined by newlines: the quote corpus


def read_pdf(pdf_path: str | Path) -> Ingested:
    """Read a PDF into base64 bytes and per-page extracted text.

    Raises FileNotFoundError if the path does not exist, and ValueError if the
    file is empty (an unreadable or zero-page PDF is a hard input error, not a
    silent empty corpus).
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    data = path.read_bytes()
    if not data:
        raise ValueError(f"PDF is empty: {path}")

    # base64 without newlines (the API rejects wrapped base64).
    pdf_b64 = base64.standard_b64encode(data).decode("ascii")

    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = tuple((page.extract_text() or "") for page in reader.pages)
    if not pages:
        raise ValueError(f"PDF has no pages: {path}")
    full_text = "\n".join(pages)
    return Ingested(pdf_b64=pdf_b64, pages=pages, full_text=full_text)
