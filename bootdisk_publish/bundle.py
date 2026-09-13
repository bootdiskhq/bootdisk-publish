"""End-to-end publication bundle for manifest-declared image assets."""

from dataclasses import dataclass
from pathlib import Path

from .derivatives import create_thumbnail
from .publish import publish_image_originals
from .publish_manifest import build_publish_manifest, write_publish_manifest


@dataclass(slots=True, frozen=True)
class ImageBundleResult:
    """Result of one image publication pass."""

    output_root: Path
    store_root: Path
    manifest_path: Path
    originals: object
    thumbnails: tuple


def publish_image_bundle(manifest_path, extraction_path, output_root, *, thumbnail_size=(320, 240)):
    """Publish originals, thumbnails, and a stable manifest into one bundle."""

    output_root = Path(output_root).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)
    store_root = output_root / "store"

    originals = publish_image_originals(manifest_path, extraction_path, store_root)

    # Identical original bytes need only one derivative object even when the same
    # asset appears in several entries. Each manifest asset can point at it.
    thumbnails_by_sha = {}
    for original in originals.assets:
        if original.sha256 not in thumbnails_by_sha:
            thumbnails_by_sha[original.sha256] = create_thumbnail(
                store_root,
                original,
                max_size=thumbnail_size,
            )

    thumbnails = tuple(thumbnails_by_sha.values())
    document = build_publish_manifest(manifest_path, originals, thumbnails)
    manifest_path_out = write_publish_manifest(
        document,
        output_root / "publish-manifest.json",
    )

    return ImageBundleResult(
        output_root=output_root.resolve(),
        store_root=store_root.resolve(),
        manifest_path=manifest_path_out,
        originals=originals,
        thumbnails=thumbnails,
    )
