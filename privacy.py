"""Privacy helpers for ANPR output and exported reports."""

from __future__ import annotations

import hashlib
import os
import re

PLATE_PATTERN = re.compile(r"[^A-Z0-9]")


def normalize_plate(text: str) -> str:
    return PLATE_PATTERN.sub("", str(text).upper())


def anonymize_plate(text: str, salt: str | None = None) -> str:
    """Return a stable non-reversible identifier instead of a raw plate."""
    normalized = normalize_plate(text)
    secret = salt or os.getenv("CITYPULSE_PLATE_SALT", "citypulse-development-salt")
    digest = hashlib.sha256(f"{secret}:{normalized}".encode("utf-8")).hexdigest()
    return f"plate_{digest[:12]}"


def redact_plate_results(results: list, salt: str | None = None) -> list[dict]:
    redacted = []
    for result in results:
        if len(result) < 3:
            continue
        redacted.append({
            "plate_id": anonymize_plate(result[1], salt),
            "confidence": round(float(result[2]), 3),
        })
    return redacted
