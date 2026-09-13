"""Stable publication manifest written without machine-local paths."""

import hashlib
import json
import os
from pathlib import Path
import tempfile

from .manifest import load_ingest_manifest
from .store import original_object_key


PUBLISH_SCHEMA_VERSION = "bootdisk-publish-1"


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def build_publish_manifest(manifest_path, originals, thumbnails):
    """Build a source-agnostic publication record from verified outputs.

    Local absolute paths are intentionally excluded. Consumers receive stable
    store-relative object keys plus content hashes and provenance linking each
    derivative back to the exact original bytes from which it was generated.
    """

    ingest = load_ingest_manifest(manifest_path)
    by_original_sha = {item.original_sha256: item for item in thumbnails}

    assets = []
    for original in originals.assets:
        thumbnail = by_original_sha.get(original.sha256.lower())
        derivatives = []
        if thumbnail is not None:
            derivatives.append(
                {
                    "kind": "thumbnail",
                    "media_type": thumbnail.media_type,
                    "sha256": thumbnail.sha256,
                    "size": thumbnail.size,
                    "width": thumbnail.width,
                    "height": thumbnail.height,
                    "object_key": thumbnail.object_key,
                    "source_sha256": thumbnail.original_sha256,
                    "generator": {
                        "name": thumbnail.generator,
                        "version": thumbnail.generator_version,
                    },
                }
            )

        assets.append(
            {
                "entry_source_id": original.entry_source_id,
                "entry_title": original.entry_title,
                "kind": original.kind,
                "source_path": original.source_path,
                "original": {
                    "sha256": original.sha256.lower(),
                    "size": original.size,
                    "object_key": original_object_key(original.sha256).as_posix(),
                },
                "derivatives": derivatives,
            }
        )

    return {
        "schema_version": PUBLISH_SCHEMA_VERSION,
        "ingest": {
            "schema_version": ingest.schema_version,
            "manifest_sha256": _sha256_file(ingest.path),
            "source_format": ingest.source.get("format"),
        },
        "assets": assets,
    }


def write_publish_manifest(document, path):
    """Atomically replace the publication manifest with deterministic JSON."""

    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return path.resolve()
