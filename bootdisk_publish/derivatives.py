"""Derived web assets built only from verified stored originals."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile

from PIL import Image, ImageOps, __version__ as pillow_version

from .manifest import ManifestError
from .publish import PublishedOriginal


@dataclass(slots=True, frozen=True)
class ThumbnailDerivative:
    """One immutable thumbnail derived from a verified original asset."""

    original_sha256: str
    sha256: str
    size: int
    width: int
    height: int
    media_type: str
    object_key: str
    path: Path
    created: bool
    generator: str
    generator_version: str


def _hash_file(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return size, digest.hexdigest()


def _thumbnail_key(sha256):
    return (
        PurePosixPath("derivatives")
        / "thumbnails"
        / "webp"
        / "sha256"
        / sha256[:2]
        / sha256[2:4]
        / f"{sha256}.webp"
    )


def create_thumbnail(store_root, original: PublishedOriginal, *, max_size=(320, 240)):
    """Create a content-addressed WebP thumbnail from a stored original.

    The original is revalidated before decoding so a derivative can never hide
    mutation of the immutable original store. Derivatives get their own content
    identity; the source SHA-256 remains explicit provenance rather than being
    overloaded as the derivative identity.
    """

    source = Path(original.object_path)
    if source.is_symlink() or not source.is_file():
        raise ManifestError(f"stored original is missing or symbolic link: {source}")

    source_size, source_sha256 = _hash_file(source)
    if source_size != original.size or source_sha256 != original.sha256.lower():
        raise ManifestError(f"stored original changed before thumbnail generation: {source}")

    if (
        not isinstance(max_size, tuple)
        or len(max_size) != 2
        or any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in max_size)
    ):
        raise ManifestError("thumbnail max_size must contain two positive integers")

    store_root = Path(store_root).expanduser()
    scratch = store_root / ".tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="xb",
            dir=scratch,
            prefix="thumbnail.",
            suffix=".webp.tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

        try:
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened)
                image.load()
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                width, height = image.size
                image.save(temp_path, format="WEBP", lossless=True, method=6)
        except (OSError, ValueError) as exc:
            raise ManifestError(f"could not derive thumbnail from {source}: {exc}") from exc

        size, sha256 = _hash_file(temp_path)
        object_key = _thumbnail_key(sha256)
        target = store_root / object_key
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file():
                raise ManifestError(f"thumbnail object is not a regular file: {target}")
            existing_size, existing_sha256 = _hash_file(target)
            if existing_size != size or existing_sha256 != sha256:
                raise ManifestError(f"thumbnail object conflicts with SHA-256 identity: {target}")
            created = False
        else:
            try:
                os.link(temp_path, target)
                created = True
            except FileExistsError:
                existing_size, existing_sha256 = _hash_file(target)
                if existing_size != size or existing_sha256 != sha256:
                    raise ManifestError(
                        f"thumbnail object conflicts with SHA-256 identity: {target}"
                    )
                created = False

        return ThumbnailDerivative(
            original_sha256=original.sha256.lower(),
            sha256=sha256,
            size=size,
            width=width,
            height=height,
            media_type="image/webp",
            object_key=object_key.as_posix(),
            path=target.resolve(),
            created=created,
            generator="Pillow",
            generator_version=pillow_version,
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
