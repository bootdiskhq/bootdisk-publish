import json
from pathlib import Path
import tempfile
import unittest

from bootdisk_publish.manifest import ManifestError, load_ingest_manifest


class ManifestTests(unittest.TestCase):
    def write_manifest(self, document):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def minimum(self):
        return {
            "schema_version": "0.9",
            "source": {"format": "future-unrelated-source-v7"},
            "entries": [],
            "file_inventory": [
                {"path": "file.bin", "size": 1, "sha256": "a" * 64}
            ],
        }

    def test_loads_minimum_publish_contract(self):
        manifest = load_ingest_manifest(self.write_manifest(self.minimum()))
        self.assertEqual(manifest.schema_version, "0.9")
        self.assertEqual(len(manifest.file_inventory), 1)

    def test_source_format_is_not_constrained(self):
        manifest = load_ingest_manifest(self.write_manifest(self.minimum()))
        self.assertEqual(manifest.source["format"], "future-unrelated-source-v7")

    def test_rejects_missing_inventory(self):
        doc = self.minimum()
        del doc["file_inventory"]
        with self.assertRaises(ManifestError):
            load_ingest_manifest(self.write_manifest(doc))

    def test_rejects_invalid_inventory_hash(self):
        doc = self.minimum()
        doc["file_inventory"][0]["sha256"] = "not-a-hash"
        with self.assertRaises(ManifestError):
            load_ingest_manifest(self.write_manifest(doc))

    def test_rejects_invalid_json(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "manifest.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ManifestError):
            load_ingest_manifest(path)
