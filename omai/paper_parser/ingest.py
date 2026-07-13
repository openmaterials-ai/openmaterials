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
    broken_pages: tuple[int, ...] = ()  # 1-indexed pages whose text extraction
                                        # failed (malformed streams); quotes
                                        # citing only these pages cannot be
                                        # verified and will be quote-killed


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
    import pypdf.filters as _f

    # pypdf guards zlib decompression at 75MB per stream; real arXiv papers
    # exceed it with giant vector figures (page 6 of a 55-page paper wanted
    # ~76MB, live 2026-07-12). Quadruple the guard; the per-page isolation
    # below remains the fallback for genuinely malformed streams.
    _f.ZLIB_MAX_OUTPUT_LENGTH = max(_f.ZLIB_MAX_OUTPUT_LENGTH, 300_000_000)

    reader = PdfReader(str(path))
    pages_l: list[str] = []
    broken: list[int] = []
    # Per-page isolation: one malformed compressed stream (pypdf
    # LimitReachedError, live on a 55-page arXiv PDF 2026-07-12) must not
    # take down the whole corpus. A broken page contributes empty text and
    # is recorded; claims citing only broken pages die at the quote gate,
    # which is the honest outcome (unverifiable is unusable).
    for i, page in enumerate(reader.pages):
        try:
            pages_l.append(page.extract_text() or "")
        except Exception:
            pages_l.append("")
            broken.append(i + 1)
    pages = tuple(pages_l)
    if not pages:
        raise ValueError(f"PDF has no pages: {path}")
    if broken and len(broken) > len(pages) // 2:
        raise ValueError(
            f"PDF text extraction failed on {len(broken)}/{len(pages)} pages: "
            f"the quote gate would kill everything; treat as unparseable: {path}")
    full_text = "\n".join(pages)
    return Ingested(pdf_b64=pdf_b64, pages=pages, full_text=full_text,
                    broken_pages=tuple(broken))


# The API rejects requests whose document block exceeds the request-size cap
# (a 26MB figure-heavy PDF 413'd live, 2026-07-12). Above this many base64
# chars, the pipeline detects on page-range parts instead (the corpus and all
# later stages still see the whole paper).
MAX_DOC_B64_CHARS = 24_000_000


def page_part(pdf_path: str | Path, ingested: Ingested,
              lo: int, hi: int) -> tuple[Ingested, int]:
    """A real sub-PDF for the page range [lo, hi), with its own extracted text
    and broken-page bookkeeping; the offset converts part pages back to
    whole-document numbering. Used by split_for_api and by the pipeline's
    adaptive re-chunking when a dense part overflows the detect output."""
    import base64
    import io

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    w = PdfWriter()
    for i in range(lo, hi):
        w.add_page(reader.pages[i])
    buf = io.BytesIO()
    w.write(buf)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    pages = ingested.pages[lo:hi]
    return Ingested(pdf_b64=b64, pages=pages, full_text="\n".join(pages),
                    broken_pages=tuple(p - lo for p in ingested.broken_pages
                                       if lo < p <= hi)), lo


def split_for_api(pdf_path: str | Path, ingested: Ingested,
                  max_b64: int = MAX_DOC_B64_CHARS,
                  max_pages: int | None = None) -> list[tuple[Ingested, int]]:
    """Return [(part, page_offset)] parts each under the API size cap.

    A part is a real sub-PDF (contiguous page range) with its OWN extracted
    text so the detect citations stay meaningful; page_offset converts a
    part's 1-indexed pages back to whole-document pages. A single part means
    no split was needed. Parts are halved recursively until they fit (a part
    that cannot fit even as one page raises: such a page is unparseable)."""
    if len(ingested.pdf_b64) <= max_b64 and max_pages is None:
        return [(ingested, 0)]

    def _part(lo: int, hi: int) -> tuple[Ingested, int]:
        return page_part(pdf_path, ingested, lo, hi)

    def _split(lo: int, hi: int) -> list[tuple[Ingested, int]]:
        if hi - lo < 1:
            raise ValueError(f"empty page range {lo}:{hi}")
        # a max_pages force (dense papers whose DETECT OUTPUT overflows even
        # when the document itself fits the request cap) splits by page count
        # before the size check ever passes a long range through
        if max_pages is not None and hi - lo > max_pages:
            mid = (lo + hi) // 2
            return _split(lo, mid) + _split(mid, hi)
        part, off = _part(lo, hi)
        if len(part.pdf_b64) <= max_b64:
            return [(part, off)]
        if hi - lo == 1:
            raise ValueError(
                f"page {lo + 1} alone exceeds the API size cap; unparseable")
        mid = (lo + hi) // 2
        return _split(lo, mid) + _split(mid, hi)

    return _split(0, len(ingested.pages))
