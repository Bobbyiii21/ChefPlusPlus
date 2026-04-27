"""
Extract plain text from uploaded .txt, .pdf, or .json files for summarization.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

ALLOWED_SUFFIXES = {".txt", ".pdf", ".json"}


def extract_text_from_upload(upload: Any) -> tuple[str, str]:
    """
    Read an uploaded file (anything with ``.name`` and ``.read()``) and return ``(text, error)``.

    *error* is empty on success.
    """
    name = (upload.name or "").lower()
    ext = ""
    if "." in name:
        ext = name[name.rfind(".") :]
    if ext not in ALLOWED_SUFFIXES:
        label = ext or "unknown"
        return "", f'Unsupported file type "{label}". Use .txt, .pdf, or .json.'

    raw = upload.read()

    if ext == ".txt":
        try:
            return raw.decode("utf-8").strip(), ""
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace").strip(), ""

    if ext == ".json":
        try:
            s = raw.decode("utf-8")
        except UnicodeDecodeError:
            s = raw.decode("utf-8", errors="replace")
        s = s.strip()
        if not s:
            return "", "JSON file is empty."
        try:
            obj = json.loads(s)
        except json.JSONDecodeError as exc:
            return "", f"Invalid JSON: {exc}"
        try:
            pretty = json.dumps(obj, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as exc:
            return "", f"Could not format JSON for summarization: {exc}"
        return pretty.strip(), ""

    # .pdf
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "PDF support is not available (pypdf missing)."

    try:
        reader = PdfReader(BytesIO(raw))
    except Exception as exc:
        return "", f"Could not read PDF: {exc}"

    parts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text()
        except Exception:
            t = ""
        if t:
            parts.append(t)
    text = "\n".join(parts).strip()
    if not text:
        return "", "No extractable text was found in this PDF."
    return text, ""
