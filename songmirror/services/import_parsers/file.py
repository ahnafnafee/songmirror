"""Dispatch uploaded playlist files to the right parser."""

from __future__ import annotations

from pathlib import Path

from .base import ParseResult
from .csv_parser import parse_csv
from .m3u import parse_m3u
from .text import parse_text


def _decode_bytes(content: bytes) -> str:
    if content is None:
        raise ValueError("file content is required")
    raw = bytes(content)
    if not raw:
        raise ValueError("file content is empty")

    # Prefer utf-8 / utf-8-sig; fall back to latin-1 rather than failing hard on
    # casual exports. charset-normalizer is available transitively but optional.
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    try:
        from charset_normalizer import from_bytes

        guess = from_bytes(raw).best()
        if guess is not None:
            return str(guess)
    except Exception:
        pass
    return raw.decode("latin-1")


def parse_file(content: str | bytes, filename: str | None = None) -> ParseResult:
    """Parse an uploaded playlist file by extension / content sniffing."""
    text = _decode_bytes(content) if isinstance(content, (bytes, bytearray)) else str(content)
    if not text.strip():
        raise ValueError("file content is empty")

    suffix = Path(filename or "").suffix.casefold()
    name_hint = Path(filename).stem if filename else None

    if suffix in {".m3u", ".m3u8"}:
        result = parse_m3u(text)
    elif suffix in {".csv", ".tsv"}:
        result = parse_csv(text)
    elif suffix in {".txt", ".text", ""}:
        # Prefer CSV when the file clearly looks columnar; otherwise treat as text.
        sample = text.lstrip()[:2048]
        looks_columnar = (
            ("\n" in sample or "\r" in sample)
            and any(delimiter in sample for delimiter in (",", ";", "\t"))
            and sample.count(",") + sample.count(";") + sample.count("\t") >= 2
        )
        if looks_columnar:
            try:
                result = parse_csv(text)
            except ValueError:
                result = parse_text(text)
        else:
            result = parse_text(text)
    else:
        raise ValueError(
            f"unsupported file type '{suffix or filename}'. "
            "Upload a .txt, .csv, .tsv, .m3u, or .m3u8 file."
        )

    if result.name is None and name_hint:
        result.name = name_hint
    return result
