import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from bootdisk_publish.assets import AssetObservation
from bootdisk_publish.manifest import ManifestError
from bootdisk_publish.preservation import load_preservation_extraction, materialize_asset


class PreservationBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "extraction"
        self.root.mkdir()

        self.asset_bytes = b"explicit screenshot bytes"
        self.asset_hash = hashlib.sha256(self.asset_bytes).hexdigest()
        self.observation = AssetObservation(
            entry_source_id="ENTRY1",
            entry_title="Example program",
            kind="screenshot",
            path="Example/Shot.jpg",
            size=len(self.asset_bytes),
            sha256=self.asset_hash,
        )

    def write_extraction(self, *, copied_files=None, entries=None):
        if copied_files is None:
            copied_files = [{
                "path": "Example/Shot.jpg",
                "size": len(self.asset_bytes),
                "sha256": self.asset_hash,
            }]
        if entries is None:
            entries = [{
                "directory": "0001",
                "source_id": "ENTRY1",
                "title": "Example program",
                "copied_files": copied_files,
                "issues": [],
            }]

        document = {
            "schema_version": "bootdisk-extraction-1",
            "scope": "Explicit inventory references; not a complete software-package claim",
            "disc": {},
            "source": {"format": "totally-unrelated-source-v9"},
            "entries": entries,
        }
        (self.root / "extraction.json").write_text(json.dumps(document), encoding="utf-8")
        return self.root

    def write_asset_bytes(self, data=None):
        target = self.root / "0001" / "files" / "Example" / "Shot.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.asset_bytes if data is None else data)
        return target

    def test_resolves_explicit_asset_from_preservation_extraction(self):
        self.write_extraction()
        target = self.write_asset_bytes()
        extraction = load_preservation_extraction(self.root)
        materialized = materialize_asset(extraction, self.observation)
        self.assertEqual(materialized.path, target.resolve())
        self.assertEqual(materialized.observation, self.observation)

    def test_changed_bytes_are_rejected(self):
        self.write_extraction()
        self.write_asset_bytes(b"changed after extraction")
        extraction = load_preservation_extraction(self.root)
        with self.assertRaisesRegex(ManifestError, "bytes do not match"):
            materialize_asset(extraction, self.observation)

    def test_missing_asset_is_rejected_without_source_media_fallback(self):
        self.write_extraction()
        extraction = load_preservation_extraction(self.root)
        with self.assertRaisesRegex(ManifestError, "missing or symbolic link"):
            materialize_asset(extraction, self.observation)

    def test_symlink_is_rejected(self):
        self.write_extraction()
        outside = Path(self.tmp.name) / "outside.jpg"
        outside.write_bytes(self.asset_bytes)
        target = self.root / "0001" / "files" / "Example" / "Shot.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(outside)
        extraction = load_preservation_extraction(self.root)
        with self.assertRaisesRegex(ManifestError, "symbolic link"):
            materialize_asset(extraction, self.observation)

    def test_duplicate_source_id_is_rejected(self):
        entries = [
            {"directory": "0001", "source_id": "ENTRY1", "copied_files": []},
            {"directory": "0002", "source_id": "ENTRY1", "copied_files": []},
        ]
        self.write_extraction(entries=entries)
        with self.assertRaisesRegex(ManifestError, "duplicate extraction source_id"):
            load_preservation_extraction(self.root)

    def test_manifest_and_extraction_identity_must_agree(self):
        copied_files = [{
            "path": "Example/Shot.jpg",
            "size": len(self.asset_bytes),
            "sha256": "0" * 64,
        }]
        self.write_extraction(copied_files=copied_files)
        self.write_asset_bytes()
        extraction = load_preservation_extraction(self.root)
        with self.assertRaisesRegex(ManifestError, "disagree"):
            materialize_asset(extraction, self.observation)

    def test_neighboring_undeclared_file_is_irrelevant(self):
        self.write_extraction()
        self.write_asset_bytes()
        neighbor = self.root / "0001" / "files" / "Example" / "Secret.jpg"
        neighbor.write_bytes(b"not declared by ingest")
        extraction = load_preservation_extraction(self.root)
        materialized = materialize_asset(extraction, self.observation)
        self.assertEqual(materialized.path.name, "Shot.jpg")
        self.assertTrue(neighbor.exists())
