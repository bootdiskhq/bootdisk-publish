"""High-level publication orchestration for manifest-declared assets."""

from dataclasses import dataclass

from .assets import iter_image_assets
from .manifest import load_ingest_manifest
from .preservation import load_preservation_extraction, materialize_asset
from .store import store_original


@dataclass(slots=True, frozen=True)
class PublishedOriginal:
    """One manifest asset bound to its stored immutable original object."""

    entry_source_id: str
    entry_title: str
    kind: str
    source_path: str
    sha256: str
    size: int
    object_path: str
    created: bool


@dataclass(slots=True, frozen=True)
class PublishOriginalsResult:
    """Summary of one deterministic original-asset publication pass."""

    assets: tuple[PublishedOriginal, ...]

    @property
    def total(self):
        return len(self.assets)

    @property
    def created(self):
        return sum(asset.created for asset in self.assets)

    @property
    def reused(self):
        return self.total - self.created


def publish_image_originals(manifest_path, extraction_path, store_root):
    """Store every explicit image original declared by an ingest manifest.

    The manifest decides which assets exist. The preservation extraction is the
    only byte source. The content store decides how verified originals are laid
    out and deduplicated. This orchestration layer deliberately performs no
    source-format parsing, directory crawling, rights inference, or derivation.
    """

    manifest = load_ingest_manifest(manifest_path)
    extraction = load_preservation_extraction(extraction_path)

    published = []
    for observation in iter_image_assets(manifest):
        materialized = materialize_asset(extraction, observation)
        stored = store_original(store_root, materialized)
        published.append(
            PublishedOriginal(
                entry_source_id=observation.entry_source_id,
                entry_title=observation.entry_title,
                kind=observation.kind,
                source_path=observation.path,
                sha256=stored.sha256,
                size=stored.size,
                object_path=str(stored.path),
                created=stored.created,
            )
        )

    return PublishOriginalsResult(assets=tuple(published))
