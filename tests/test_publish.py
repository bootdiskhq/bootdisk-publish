import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from bootdisk_publish.manifest import ManifestError
from bootdisk_publish.publish import publish_image_originals


class PublishImageOriginalsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.extraction = self.root / "extraction"
        self.extraction.mkdir()
        self.store = self.root / "store"

        self.screenshot_bytes = b"screenshot bytes"
        self.icon_bytes = b"icon bytes"
        self.screenshot_hash = hashlib.sha256(self.screenshot_bytes).hexdigest()
        self.icon_hash = hashlib.sha256(self.icon_bytes).hexdigest()

    def write_manifest(self, *, include_icon=True):
        discovered = {
            "screenshot": {
                "exists": True,
                "is_file": True,
                "path": "Example/Shot.bmp",
                "size": len(self.screenshot_bytes),
                "sha256": self.screenshot_hash,
            },
            "description_rtf": {
                "exists": True,
                "is_file": True,
                "path": "Example/Description.rtf",
                "size": 10,
                "sha256": "1" * 64,
            },
        }
        if include_icon:
            discovered["icon"] = {
                "exists": True,
                "is_file": True,
                "path": "Example/Icon.ico",
                "size": len(self.icon_bytes),
                "sha256": self.icon_hash,
            }

        document = {
            "schema_version": "0.9",
            "source": {"format": "totally-unrelated-source-v9"},
            "entries": [{
                "source_id": "ENTRY1",
                "normalized": {"title": "Example program"},
                "files": {"discovered": discovered},
            }],
            "file_inventory": [],
        }
        path = self.root / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def write_extraction(self, *, include_icon=True):
        copied = [{
            "path": "Example/Shot.bmp",
            "size": len(self.screenshot_bytes),
            "sha256": self.screenshot_hash,
        }]
        if include_icon:
            copied.append({
                "path": "Example/Icon.ico",
                "size": len(self.icon_bytes),
                "sha256": self.icon_hash,
            })

        document = {
            "schema_version": "bootdisk-extraction-1",
            "source": {"format": "totally-unrelated-source-v9"},
            "entries": [{
                "directory": "0001",
                "source_id": "ENTRY1",
                "copied_files": copied,
            }],
        }
        (self.extraction / "extraction.json").write_text(
            json.dumps(document), encoding="utf-8"
        )

        files = self.extraction / "0001" / "files" / "Example"
        files.mkdir(parents=True)
        (files / "Shot.bmp").write_bytes(self.screenshot_bytes)
        if include_icon:
            (files / "Icon.ico").write_bytes(self.icon_bytes)
        # Publish must never discover this file merely because it is nearby.
        (files / "Neighbor.png").write_bytes(b"undeclared")
        return self.extraction

    def test_publishes_all_and_only_explicit_image_originals(self):
        manifest = self.write_manifest()
        extraction = self.write_extraction()

        result = publish_image_originals(manifest, extraction, self.store)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.created, 2)
        self.assertEqual(result.reused, 0)
        self.assertEqual({asset.kind for asset in result.assets}, {"screenshot", "icon"})
        self.assertEqual(
            {Path(asset.object_path).read_bytes() for asset in result.assets},
            {self.screenshot_bytes, self.icon_bytes},
        )
        self.assertFalse(any(path.name == "Neighbor.png" for path in self.store.rglob("*")))
        self.assertFalse(any("Description" in str(path) for path in self.store.rglob("*")))

    def test_second_pass_reuses_existing_content_objects(self):
        manifest = self.write_manifest()
        extraction = self.write_extraction()

        first = publish_image_originals(manifest, extraction, self.store)
        second = publish_image_originals(manifest, extraction, self.store)

        self.assertEqual(first.created, 2)
        self.assertEqual(second.created, 0)
        self.assertEqual(second.reused, 2)
        self.assertEqual(
            {asset.object_path for asset in first.assets},
            {asset.object_path for asset in second.assets},
        )

    def test_missing_preserved_asset_fails_without_source_media_fallback(self):
        manifest = self.write_manifest()
        extraction = self.write_extraction(include_icon=False)

        with self.assertRaisesRegex(ManifestError, "absent from preservation extraction"):
            publish_image_originals(manifest, extraction, self.store)

    def test_source_format_remains_irrelevant_to_publication(self):
        manifest = self.write_manifest(include_icon=False)
        extraction = self.write_extraction(include_icon=False)

        result = publish_image_originals(manifest, extraction, self.store)

        self.assertEqual(result.total, 1)
        self.assertEqual(result.assets[0].entry_source_id, "ENTRY1")
        self.assertEqual(result.assets[0].kind, "screenshot")


if __name__ == "__main__":
    unittest.main()
