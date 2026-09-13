"""Bind manifest asset observations to verified preservation-extraction bytes."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath

from .assets import AssetObservation
from .manifest import ManifestError


@dataclass(slots=True, frozen=True)
class ExtractionEntry:
    """One entry exported by bootdisk-ingest's preservation extraction."""

    source_id: str
    directory: str
    copied_files: dict


@dataclass(slots=True, frozen=True)
class PreservationExtraction:
    """A validated preservation extraction produced by bootdisk-ingest."""

    root: Path
    document: dict
    entries_by_source_id: dict


@dataclass(slots=True, frozen=True)
class MaterializedAsset:
    """Verified local bytes for one explicit manifest asset observation."""

    observation: AssetObservation
    path: Path


def _safe_relative(value, context):
    # Extraction metadata becomes filesystem input later. Reject path syntax
    # that could escape the extraction root before joining it to local paths.
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ManifestError(f"{context} must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise ManifestError(f"{context} must be a safe relative POSIX path")
    return value


def _sha256(value, context):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdefABCDEF" for ch in value)
    ):
        raise ManifestError(f"{context} must be a 64-character hexadecimal SHA-256")
    return value.lower()


def load_preservation_extraction(path):
    """Load and validate the stable subset of bootdisk-extraction-1 we consume."""

    path = Path(path).expanduser()
    if path.is_dir():
        path = path / "extraction.json"
    if not path.is_file():
        raise ManifestError(f"Preservation extraction does not exist: {path}")

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Could not read preservation extraction: {exc}") from exc

    if not isinstance(document, dict):
        raise ManifestError("extraction root must be an object")
    if document.get("schema_version") != "bootdisk-extraction-1":
        raise ManifestError("unsupported preservation extraction schema")

    entries = document.get("entries")
    if not isinstance(entries, list):
        raise ManifestError("extraction.entries must be an array")

    by_source_id = {}
    for index, entry in enumerate(entries):
        context = f"extraction.entries[{index}]"
        if not isinstance(entry, dict):
            raise ManifestError(f"{context} must be an object")

        source_id = entry.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ManifestError(f"{context}.source_id must be a non-empty string")
        if source_id in by_source_id:
            raise ManifestError(f"duplicate extraction source_id: {source_id}")

        directory = _safe_relative(entry.get("directory"), f"{context}.directory")
        copied_files = entry.get("copied_files")
        if not isinstance(copied_files, list):
            raise ManifestError(f"{context}.copied_files must be an array")

        copied_by_path = {}
        for file_index, record in enumerate(copied_files):
            file_context = f"{context}.copied_files[{file_index}]"
            if not isinstance(record, dict):
                raise ManifestError(f"{file_context} must be an object")

            relative = _safe_relative(record.get("path"), f"{file_context}.path")
            if relative in copied_by_path:
                raise ManifestError(f"duplicate copied file path for {source_id}: {relative}")

            size = record.get("size")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ManifestError(f"{file_context}.size must be non-negative")

            copied_by_path[relative] = {
                "path": relative,
                "size": size,
                "sha256": _sha256(record.get("sha256"), f"{file_context}.sha256"),
            }

        by_source_id[source_id] = ExtractionEntry(
            source_id=source_id,
            directory=directory,
            copied_files=copied_by_path,
        )

    return PreservationExtraction(
        root=path.parent.resolve(),
        document=document,
        entries_by_source_id=by_source_id,
    )


def _hash_file(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return size, digest.hexdigest()


def materialize_asset(extraction, observation):
    """Resolve and verify bytes for one explicit manifest asset.

    Publish never falls back to the original source medium. If ingest did not
    preserve the asset in the extraction, publication stops here.
    """

    entry = extraction.entries_by_source_id.get(observation.entry_source_id)
    if entry is None:
        raise ManifestError(
            f"asset source_id absent from preservation extraction: {observation.entry_source_id}"
        )

    copied = entry.copied_files.get(observation.path)
    if copied is None:
        raise ManifestError(f"asset absent from preservation extraction: {observation.path}")

    # The ingest manifest and extraction independently describe the same bytes.
    # Require agreement before touching the preserved file.
    if copied["size"] != observation.size or copied["sha256"] != observation.sha256:
        raise ManifestError(
            f"manifest and preservation extraction disagree for: {observation.path}"
        )

    files_root = extraction.root / entry.directory / "files"
    target = files_root.joinpath(*PurePosixPath(observation.path).parts)

    # Reject indirection even when a symlink currently resolves inside the tree.
    if target.is_symlink() or not target.is_file():
        raise ManifestError(
            f"preserved asset is missing or symbolic link: {observation.path}"
        )

    resolved_files_root = files_root.resolve()
    resolved_target = target.resolve()
    try:
        resolved_target.relative_to(resolved_files_root)
    except ValueError as exc:
        raise ManifestError(
            f"preserved asset escapes extraction boundary: {observation.path}"
        ) from exc

    size, sha256 = _hash_file(target)
    if size != observation.size or sha256 != observation.sha256:
        raise ManifestError(
            f"preserved asset bytes do not match manifest: {observation.path}"
        )

    return MaterializedAsset(observation=observation, path=resolved_target)
