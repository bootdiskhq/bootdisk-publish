import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from bootdisk_publish.frontend_cli import main


class FrontendCliTests(unittest.TestCase):
    def test_filters_projection_by_entry(self):
        document = {
            "schema_version": "bootdisk-publish-1",
            "assets": [
                {
                    "entry_source_id": "K37",
                    "entry_title": "WinAmp 2.76",
                    "kind": "screenshot",
                    "source_path": "WinAmp/Shot.jpg",
                    "original": {
                        "sha256": "a" * 64,
                        "size": 10,
                        "object_key": f"originals/{'a' * 64}",
                    },
                    "derivatives": [],
                },
                {
                    "entry_source_id": "K38",
                    "entry_title": "WinZip 8.0",
                    "kind": "screenshot",
                    "source_path": "WinZip/Shot.jpg",
                    "original": {
                        "sha256": "b" * 64,
                        "size": 10,
                        "object_key": f"originals/{'b' * 64}",
                    },
                    "derivatives": [],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "publish-manifest.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                result = main([str(path), "--entry", "K37"])

        self.assertEqual(result, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual([item["entry"] for item in payload], ["K37"])

    def test_invalid_manifest_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "publish-manifest.json"
            path.write_text("{}", encoding="utf-8")
            errors = StringIO()
            with redirect_stderr(errors):
                result = main([str(path)])

        self.assertEqual(result, 2)
        self.assertIn("assets array", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
