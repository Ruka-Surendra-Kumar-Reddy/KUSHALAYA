"""Normalize catalog product image id lists (supports legacy single image_id)."""

from __future__ import annotations


def parse_image_document_ids_cell(text: str) -> list[int]:
    """Parse comma/semicolon-separated document IDs from spreadsheet cell."""
    if not text or not str(text).strip():
        return []
    ids: list[int] = []
    seen: set[int] = set()
    for part in str(text).replace(";", ",").split(","):
        token = part.strip()
        if not token:
            continue
        try:
            doc_id = int(float(token)) if "." in token else int(token)
        except (TypeError, ValueError):
            continue
        if doc_id not in seen:
            ids.append(doc_id)
            seen.add(doc_id)
    return ids


def format_image_document_ids_cell(image_ids: list[int] | None) -> str:
    return ",".join(str(i) for i in (image_ids or []))


def normalize_image_ids(raw: dict) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for value in raw.get("image_ids") or []:
        try:
            image_id = int(value)
        except (TypeError, ValueError):
            continue
        if image_id not in seen:
            ids.append(image_id)
            seen.add(image_id)

    legacy = raw.get("image_id")
    if legacy is not None:
        try:
            image_id = int(legacy)
            if image_id not in seen:
                ids.insert(0, image_id)
        except (TypeError, ValueError):
            pass
    return ids


def image_url_for(document_id: int) -> str:
    return f"/api/v1/home-safety/catalog/public/images/{document_id}"
