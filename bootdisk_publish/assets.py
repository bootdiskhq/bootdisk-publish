"""Project explicit asset observations from an ingest manifest."""

from dataclasses import dataclass
from pathlib import PurePosixPath

from .manifest import IngestManifest, ManifestError


@dataclass(slots=True, frozen=True)
class AssetObservation:
    """An asset explicitly observed by ingest and eligible for later processing.

    This is still evidence, not a publication decision. No bytes are copied and
    no redistribution permission is implied by creating this object.
    """

    entry_source_id: str
    entry_title: str
    kind: str
    path: str
    size: int
    sha256: str


def _safe_manifest_path(value, context):
    # Validate now because a later stage will join these paths to a preservation
    # extraction. Publish must never let manifest data escape that boundary.
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


def _asset_from_observation(entry_source_id, entry_title, kind, observation):
    if not isinstance(observation, dict):
        return None
    if observation.get("exists") is not True:
        return None
    if observation.get("is_file") is False:
        raise ManifestError(f"{entry_source_id}.{kind} exists but is not a file")

    path = _safe_manifest_path(
        observation.get("path"),
        f"{entry_source_id}.{kind}.path",
    )
    size = observation.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ManifestError(f"{entry_source_id}.{kind}.size must be non-negative")

    return AssetObservation(
        entry_source_id=entry_source_id,
        entry_title=entry_title,
        kind=kind,
        path=path,
        size=size,
        sha256=_sha256(
            observation.get("sha256"),
            f"{entry_source_id}.{kind}.sha256",
        ),
    )


def iter_image_assets(manifest: IngestManifest):
    """Return only image assets explicitly identified by ingest.

    This is a compatibility projection for the current 0.9 manifest contract.
    It deliberately does not scan file_inventory for image-looking filenames:
    source-media discovery belongs in ingest, never publish.
    """

    assets = []
    for index, entry in enumerate(manifest.entries):
        if not isinstance(entry, dict):
            raise ManifestError(f"manifest.entries[{index}] must be an object")

        source_id = entry.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ManifestError(
                f"manifest.entries[{index}].source_id must be a non-empty string"
            )

        normalized = entry.get("normalized")
        title = normalized.get("title", "") if isinstance(normalized, dict) else ""
        if not isinstance(title, str):
            title = ""

        files = entry.get("files")
        discovered = files.get("discovered") if isinstance(files, dict) else None
        if not isinstance(discovered, dict):
            continue

        # Documents such as description_rtf are intentionally not promoted yet.
        # Add new asset classes explicitly so publication behavior stays reviewable.
        for kind in ("screenshot", "icon"):
            asset = _asset_from_observation(
                source_id,
                title,
                kind,
                discovered.get(kind),
            )
            if asset is not None:
                assets.append(asset)

    return assets
