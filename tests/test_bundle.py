import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from bootdisk_publish.bundle import publish_image_bundle
from bootdisk_publish.manifest import ManifestError


class ImageBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.extraction = self.root / "extraction"
        self.extraction.mkdir()
        self.output = self.root / "published"

        source = self.root / "source-fixtures"
        source.mkdir()
        self.screenshot = source / "Shot.bmp"
        self.icon = source / "Icon.ico"
        Image.new("RGB", (640, 480), (40, 80, 120)).save(self.screenshot, format="BMP")
        Image.new("RGBA", (64, 64), (220, 120, 20, 255)).save(self.icon, format="ICO")

        self.screenshot_bytes = self.screenshot.read_bytes()
        self.icon_bytes = self.icon.read_bytes()
        self.screenshot_hash = hashlib.sha256(self.screenshot_bytes).hexdigest()
        self.icon_hash = hashlib.sha256(self.icon_bytes).hexdigest()

    def write_manifest(self):
        document = {
            "schema_version": "0.9",
            "source": {"format": "future-unrelated-source"},
            "entries": [
                {
                    "source_id": "ENTRY1",
                    "normalized": {"title": "Example program"},
                    "files": {
                        "discovered": {
                            "screenshot": {
                                "exists": True,
                                "is_file": True,
                                "path": "Example/Shot.bmp",
                                "size": len(self.screenshot_bytes),
                                "sha256": self.screenshot_hash,
                            },
                            "icon": {
                                "exists": True,
                                "is_file": True,
                                "path": "Example/Icon.ico",
                                "size": len(self.icon_bytes),
                                "sha256": self.icon_hash,
                            },
                        }
                    },
                }
            ],
            "file_inventory": [],
        }
        path = self.root / "ingest-manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def write_extraction(self, *, corrupt_screenshot=False):
        document = {
            "schema_version": "bootdisk-extraction-1",
            "entries": [
                {
                    "directory": "0001",
                    "source_id": "ENTRY1",
                    "copied_files": [
                        {
                            "path": "Example/Shot.bmp",
                            "size": len(self.screenshot_bytes),
                            "sha256": self.screenshot_hash,
                        },
                        {
                            "path": "Example/Icon.ico",
                            "size": len(self.icon_bytes),
                            "sha256": self.icon_hash,
                        },
                    ],
                }
            ],
        }
        (self.extraction / "extraction.json").write_text(
            json.dumps(document), encoding="utf-8"
        )
        files = self.extraction / "0001" / "files" / "Example"
        files.mkdir(parents=True)
        (files / "Shot.bmp").write_bytes(
            b"not the preserved screenshot" if corrupt_screenshot else self.screenshot_bytes
        )
        (files / "Icon.ico").write_bytes(self.icon_bytes)
        return self.extraction

    def test_bundle_creates_originals_webp_thumbnails_and_publish_manifest(self):
        manifest = self.write_manifest()
        extraction = self.write_extraction()

        result = publish_image_bundle(manifest, extraction, self.output)

        self.assertEqual(result.originals.total, 2)
        self.assertEqual(len(result.thumbnails), 2)
        self.assertTrue(result.manifest_path.is_file())
        for thumbnail in result.thumbnails:
            self.assertTrue(thumbnail.path.is_file())
            self.assertLessEqual(thumbnail.width, 320)
            self.assertLessEqual(thumbnail.height, 240)
            with Image.open(thumbnail.path) as image:
                self.assertEqual(image.format, "WEBP")
                self.assertEqual(image.size, (thumbnail.width, thumbnail.height))

    def test_publish_manifest_contains_stable_keys_and_no_machine_local_paths(self):
        manifest = self.write_manifest()
        extraction = self.write_extraction()

        result = publish_image_bundle(manifest, extraction, self.output)
        document = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        serialized = result.manifest_path.read_text(encoding="utf-8")

        self.assertEqual(document["schema_version"], "bootdisk-publish-1")
        self.assertEqual(document["ingest"]["source_format"], "future-unrelated-source")
        self.assertEqual(len(document["assets"]), 2)
        self.assertNotIn(str(self.root), serialized)

        for asset in document["assets"]:
            original = asset["original"]
            self.assertFalse(original["object_key"].startswith("/"))
            self.assertTrue(original["object_key"].startswith("assets/sha256/"))
            self.assertEqual(len(asset["derivatives"]), 1)
            thumbnail = asset["derivatives"][0]
            self.assertEqual(thumbnail["kind"], "thumbnail")
            self.assertEqual(thumbnail["media_type"], "image/webp")
            self.assertEqual(thumbnail["source_sha256"], original["sha256"])
            self.assertTrue(
                thumbnail["object_key"].startswith("derivatives/thumbnails/webp/sha256/")
            )
            self.assertEqual(thumbnail["generator"]["name"], "Pillow")

    def test_second_bundle_pass_reuses_originals_and_thumbnails(self):
        manifest = self.write_manifest()
        extraction = self.write_extraction()

        first = publish_image_bundle(manifest, extraction, self.output)
        second = publish_image_bundle(manifest, extraction, self.output)

        self.assertEqual(first.originals.created, 2)
        self.assertEqual(second.originals.created, 0)
        self.assertEqual(sum(item.created for item in first.thumbnails), 2)
        self.assertEqual(sum(item.created for item in second.thumbnails), 0)
        self.assertEqual(
            {item.object_key for item in first.thumbnails},
            {item.object_key for item in second.thumbnails},
        )

    def test_ingest_manifest_identity_is_exact_file_sha256(self):
        manifest = self.write_manifest()
        extraction = self.write_extraction()
        expected = hashlib.sha256(manifest.read_bytes()).hexdigest()

        result = publish_image_bundle(manifest, extraction, self.output)
        document = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(document["ingest"]["manifest_sha256"], expected)

    def test_corrupt_preservation_bytes_fail_before_thumbnail_generation(self):
        manifest = self.write_manifest()
        extraction = self.write_extraction(corrupt_screenshot=True)

        with self.assertRaisesRegex(ManifestError, "changed since extraction"):
            publish_image_bundle(manifest, extraction, self.output)


if __name__ == "__main__":
    unittest.main()
