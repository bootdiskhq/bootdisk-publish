"""Project published image assets into a small frontend-facing contract.

This projection deliberately contains publication facts only. Catalog owns semantic
software identity; Publish owns web-ready objects and derivatives. A frontend may
join both projections by the stable ingest entry source id.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FrontendProjectionError(Exception):
    """Raised when a publish manifest cannot be projected safely."""


def load_publish_manifest(path: str | Path) -> dict[str, Any]:
    path = Path(path).expanduser()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrontendProjectionError(f"cannot read publish manifest {path}: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("assets"), list):
        raise FrontendProjectionError("publish manifest must contain an assets array")
    return document


def _public_path(object_key: str) -> str:
    """Return a deployment-neutral URL path rooted at the published bundle store."""

    return f"/store/{object_key.lstrip('/')}"


def frontend_assets(document: dict[str, Any], entry_id: str | None = None) -> list[dict[str, Any]]:
    """Return deterministic web-asset metadata, optionally for one ingest entry."""

    projected = []
    for asset in document["assets"]:
        source_id = asset.get("entry_source_id")
        if entry_id is not None and source_id != entry_id:
            continue

        original = asset.get("original") or {}
        derivatives = []
        for derivative in asset.get("derivatives") or []:
            object_key = derivative.get("object_key")
            derivatives.append(
                {
                    "kind": derivative.get("kind"),
                    "media_type": derivative.get("media_type"),
                    "width": derivative.get("width"),
                    "height": derivative.get("height"),
                    "sha256": derivative.get("sha256"),
                    "object_key": object_key,
                    "public_path": _public_path(object_key) if object_key else None,
                }
            )

        object_key = original.get("object_key")
        projected.append(
            {
                "entry": source_id,
                "editorial_title": asset.get("entry_title"),
                "kind": asset.get("kind"),
                "source_path": asset.get("source_path"),
                "original": {
                    "sha256": original.get("sha256"),
                    "size": original.get("size"),
                    "object_key": object_key,
                    "public_path": _public_path(object_key) if object_key else None,
                },
                "derivatives": derivatives,
            }
        )

    # Manifest order remains provenance context. Sorting only the derivative list keeps
    # repeated runs deterministic without inventing a new editorial entry ordering.
    for asset in projected:
        asset["derivatives"].sort(key=lambda item: (item["kind"] or "", item["object_key"] or ""))
    return projected
