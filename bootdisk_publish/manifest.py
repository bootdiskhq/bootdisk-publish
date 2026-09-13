"""Validation of the source-agnostic ingest manifest contract."""

from dataclasses import dataclass
import json
from pathlib import Path


class ManifestError(ValueError):
    """The ingest manifest cannot safely be consumed by publication tooling."""


@dataclass(slots=True, frozen=True)
class IngestManifest:
    """A validated ingest manifest.

    Keep this wrapper source-format agnostic. Publish consumes observations
    expressed by the manifest; it must not learn how K.DTX, Director, or future
    source formats are parsed.
    """

    path: Path
    document: dict

    @property
    def schema_version(self):
        return self.document["schema_version"]

    @property
    def source(self):
        return self.document["source"]

    @property
    def entries(self):
        return self.document["entries"]

    @property
    def file_inventory(self):
        return self.document["file_inventory"]


def _require_mapping(value, context):
    if not isinstance(value, dict):
        raise ManifestError(f"{context} must be an object")
    return value


def _require_list(value, context):
    if not isinstance(value, list):
        raise ManifestError(f"{context} must be an array")
    return value


def _validate_sha256(value, context):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdefABCDEF" for ch in value)
    ):
        raise ManifestError(f"{context} must be a 64-character hexadecimal SHA-256")


def load_ingest_manifest(path):
    """Load the minimum stable contract needed by bootdisk-publish."""

    path = Path(path).expanduser()
    if not path.is_file():
        raise ManifestError(f"Ingest manifest does not exist: {path}")

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Could not read ingest manifest: {exc}") from exc

    _require_mapping(document, "manifest")

    schema_version = document.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version:
        raise ManifestError("manifest.schema_version must be a non-empty string")

    _require_mapping(document.get("source"), "manifest.source")
    _require_list(document.get("entries"), "manifest.entries")
    inventory = _require_list(document.get("file_inventory"), "manifest.file_inventory")

    for index, record in enumerate(inventory):
        record = _require_mapping(record, f"manifest.file_inventory[{index}]")
        path_value = record.get("path")
        if not isinstance(path_value, str) or not path_value:
            raise ManifestError(
                f"manifest.file_inventory[{index}].path must be a non-empty string"
            )
        size = record.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ManifestError(
                f"manifest.file_inventory[{index}].size must be a non-negative integer"
            )
        _validate_sha256(
            record.get("sha256"),
            f"manifest.file_inventory[{index}].sha256",
        )

    return IngestManifest(path=path.resolve(), document=document)
