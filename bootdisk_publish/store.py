"""Content-addressed storage for verified original publication assets."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile

from .manifest import ManifestError
from .preservation import MaterializedAsset


@dataclass(slots=True, frozen=True)
class StoredOriginal:
    """One immutable original stored under its SHA-256 identity."""

    sha256: str
    size: int
    path: Path
    created: bool


def _normalized_sha256(sha256):
    if (
        not isinstance(sha256, str)
        or len(sha256) != 64
        or any(ch not in "0123456789abcdefABCDEF" for ch in sha256)
    ):
        raise ManifestError("original-store SHA-256 must be 64 hexadecimal characters")
    return sha256.lower()


def original_object_key(sha256):
    """Return the stable store-relative key for one original object."""

    digest = _normalized_sha256(sha256)
    return PurePosixPath("assets") / "sha256" / digest[:2] / digest[2:4] / digest


def original_object_path(store_root, sha256):
    """Return the deterministic local object path for one SHA-256 digest."""

    root = Path(store_root).expanduser()
    return root / original_object_key(sha256)


def _hash_file(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return size, digest.hexdigest()


def _validate_existing(target, expected_size, expected_sha256):
    # Existing objects are trusted only after revalidation. A matching path is
    # not enough because content-addressing is useful only while the namespace
    # remains an exact statement about the bytes stored beneath it.
    if target.is_symlink() or not target.is_file():
        raise ManifestError(f"original-store object is not a regular file: {target}")
    size, sha256 = _hash_file(target)
    if size != expected_size or sha256 != expected_sha256:
        raise ManifestError(f"original-store object conflicts with SHA-256 identity: {target}")


def store_original(store_root, materialized: MaterializedAsset):
    """Store one verified original without ever overwriting an existing object.

    The source is hashed again while copying because bytes may change after the
    preservation binding was verified. A sibling temporary file is linked into
    the content-addressed namespace atomically; an existing object is retained
    and validated instead of being replaced.
    """

    observation = materialized.observation
    expected_sha256 = observation.sha256.lower()
    expected_size = observation.size
    source = Path(materialized.path)

    if source.is_symlink() or not source.is_file():
        raise ManifestError(f"materialized asset is missing or symbolic link: {source}")

    target = original_object_path(store_root, expected_sha256)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() or target.is_symlink():
        _validate_existing(target, expected_size, expected_sha256)
        return StoredOriginal(
            sha256=expected_sha256,
            size=expected_size,
            path=target.resolve(),
            created=False,
        )

    temp_path = None
    try:
        digest = hashlib.sha256()
        size = 0
        with tempfile.NamedTemporaryFile(
            mode="xb",
            dir=target.parent,
            prefix=f".{expected_sha256}.",
            suffix=".tmp",
            delete=False,
        ) as destination, source.open("rb") as src:
            temp_path = Path(destination.name)
            while block := src.read(1024 * 1024):
                destination.write(block)
                digest.update(block)
                size += len(block)
            destination.flush()
            os.fsync(destination.fileno())

        if size != expected_size or digest.hexdigest() != expected_sha256:
            raise ManifestError(
                f"materialized asset changed before original-store copy: {source}"
            )

        try:
            # Hard-linking a completed sibling temp file gives us no-clobber
            # publication into the object namespace. If another writer won the
            # race, validate that object and discard our temporary copy.
            os.link(temp_path, target)
            created = True
        except FileExistsError:
            _validate_existing(target, expected_size, expected_sha256)
            created = False

        return StoredOriginal(
            sha256=expected_sha256,
            size=expected_size,
            path=target.resolve(),
            created=created,
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
