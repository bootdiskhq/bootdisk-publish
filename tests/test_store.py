import hashlib
from pathlib import Path
import tempfile
import unittest

from bootdisk_publish.assets import AssetObservation
from bootdisk_publish.manifest import ManifestError
from bootdisk_publish.preservation import MaterializedAsset
from bootdisk_publish.store import original_object_path, store_original


class OriginalStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source" / "Shot.bmp"
        self.source.parent.mkdir()
        self.bytes = b"preserved original image bytes"
        self.source.write_bytes(self.bytes)
        self.sha256 = hashlib.sha256(self.bytes).hexdigest()
        observation = AssetObservation(
            entry_source_id="ENTRY1",
            entry_title="Example",
            kind="screenshot",
            path="Example/Shot.bmp",
            size=len(self.bytes),
            sha256=self.sha256,
        )
        self.materialized = MaterializedAsset(
            observation=observation,
            path=self.source,
        )
        self.store = self.root / "publish-store"

    def test_object_path_is_deterministic_and_content_addressed(self):
        path = original_object_path(self.store, self.sha256)
        self.assertEqual(
            path,
            self.store / "assets" / "sha256" / self.sha256[:2] / self.sha256[2:4] / self.sha256,
        )

    def test_stores_verified_original_bytes(self):
        stored = store_original(self.store, self.materialized)
        self.assertTrue(stored.created)
        self.assertEqual(stored.sha256, self.sha256)
        self.assertEqual(stored.size, len(self.bytes))
        self.assertEqual(stored.path.read_bytes(), self.bytes)

    def test_identical_bytes_are_deduplicated(self):
        first = store_original(self.store, self.materialized)
        second = store_original(self.store, self.materialized)
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.path, second.path)

    def test_same_bytes_with_different_source_name_share_one_object(self):
        other = self.root / "source" / "renamed.dat"
        other.write_bytes(self.bytes)
        observation = AssetObservation(
            entry_source_id="ENTRY2",
            entry_title="Another source",
            kind="icon",
            path="Other/renamed.dat",
            size=len(self.bytes),
            sha256=self.sha256,
        )
        materialized = MaterializedAsset(observation=observation, path=other)
        first = store_original(self.store, self.materialized)
        second = store_original(self.store, materialized)
        self.assertEqual(first.path, second.path)
        self.assertFalse(second.created)

    def test_existing_conflicting_object_is_never_overwritten(self):
        target = original_object_path(self.store, self.sha256)
        target.parent.mkdir(parents=True)
        target.write_bytes(b"corrupt object")
        with self.assertRaisesRegex(ManifestError, "conflicts with SHA-256 identity"):
            store_original(self.store, self.materialized)
        self.assertEqual(target.read_bytes(), b"corrupt object")

    def test_source_changed_after_materialization_is_rejected(self):
        self.source.write_bytes(b"changed after verification")
        with self.assertRaisesRegex(ManifestError, "changed before original-store copy"):
            store_original(self.store, self.materialized)
        self.assertFalse(original_object_path(self.store, self.sha256).exists())

    def test_symlink_source_is_rejected(self):
        real = self.root / "real.bin"
        real.write_bytes(self.bytes)
        link = self.root / "source" / "link.bin"
        link.symlink_to(real)
        materialized = MaterializedAsset(
            observation=self.materialized.observation,
            path=link,
        )
        with self.assertRaisesRegex(ManifestError, "symbolic link"):
            store_original(self.store, materialized)

    def test_invalid_digest_is_rejected_before_path_creation(self):
        with self.assertRaises(ManifestError):
            original_object_path(self.store, "not-a-hash")
