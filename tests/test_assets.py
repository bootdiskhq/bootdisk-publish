import json
from pathlib import Path
import tempfile
import unittest

from bootdisk_publish.assets import iter_image_assets
from bootdisk_publish.manifest import ManifestError, load_ingest_manifest


class AssetTests(unittest.TestCase):
    def manifest_document(self):
        return {
            "schema_version": "0.9",
            "source": {"format": "unrelated-source-v1"},
            "entries": [
                {
                    "source_id": "ENTRY1",
                    "normalized": {"title": "Example program"},
                    "files": {
                        "discovered": {
                            "description_rtf": {
                                "path": "Example/No.rtf",
                                "exists": True,
                                "is_file": True,
                                "size": 100,
                                "sha256": "c" * 64,
                            },
                            "screenshot": {
                                "path": "Example/Shot.jpg",
                                "exists": True,
                                "is_file": True,
                                "size": 12345,
                                "sha256": "a" * 64,
                            },
                            "icon": {
                                "path": "Example/Ikon.bmp",
                                "exists": True,
                                "is_file": True,
                                "size": 3126,
                                "sha256": "b" * 64,
                            },
                        }
                    },
                }
            ],
            "file_inventory": [
                {"path": "Example/No.rtf", "size": 100, "sha256": "c" * 64},
                {"path": "Example/Shot.jpg", "size": 12345, "sha256": "a" * 64},
                {"path": "Example/Ikon.bmp", "size": 3126, "sha256": "b" * 64},
                {"path": "Example/Secret.jpg", "size": 999, "sha256": "d" * 64},
            ],
        }

    def load(self, document=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "manifest.json"
        path.write_text(json.dumps(document or self.manifest_document()), encoding="utf-8")
        return load_ingest_manifest(path)

    def test_projects_explicit_screenshot_and_icon(self):
        assets = iter_image_assets(self.load())
        self.assertEqual([a.kind for a in assets], ["screenshot", "icon"])
        self.assertEqual(
            [a.path for a in assets],
            ["Example/Shot.jpg", "Example/Ikon.bmp"],
        )

    def test_retains_entry_and_content_identity(self):
        asset = iter_image_assets(self.load())[0]
        self.assertEqual(asset.entry_source_id, "ENTRY1")
        self.assertEqual(asset.entry_title, "Example program")
        self.assertEqual(asset.size, 12345)
        self.assertEqual(asset.sha256, "a" * 64)

    def test_does_not_publish_neighboring_inventory_image(self):
        paths = [a.path for a in iter_image_assets(self.load())]
        self.assertNotIn("Example/Secret.jpg", paths)

    def test_does_not_promote_document_assets_yet(self):
        paths = [a.path for a in iter_image_assets(self.load())]
        self.assertNotIn("Example/No.rtf", paths)

    def test_skips_explicitly_missing_asset(self):
        doc = self.manifest_document()
        doc["entries"][0]["files"]["discovered"]["icon"]["exists"] = False
        self.assertEqual(
            [a.kind for a in iter_image_assets(self.load(doc))],
            ["screenshot"],
        )

    def test_rejects_traversal_path(self):
        doc = self.manifest_document()
        doc["entries"][0]["files"]["discovered"]["screenshot"]["path"] = "../Shot.jpg"
        with self.assertRaises(ManifestError):
            iter_image_assets(self.load(doc))

    def test_rejects_invalid_asset_hash(self):
        doc = self.manifest_document()
        doc["entries"][0]["files"]["discovered"]["screenshot"]["sha256"] = "bad"
        with self.assertRaises(ManifestError):
            iter_image_assets(self.load(doc))
