import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from bootdisk_publish.cli import main


class CliTests(unittest.TestCase):
    def test_inspect_prints_source_agnostic_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.9",
                        "source": {"format": "future-source"},
                        "entries": [],
                        "file_inventory": [],
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main([str(path), "--inspect"])

        self.assertEqual(status, 0)
        summary = json.loads(output.getvalue())
        self.assertEqual(summary["source_format"], "future-source")
        self.assertEqual(summary["entries"], 0)
        self.assertEqual(summary["inventory_files"], 0)
        self.assertEqual(summary["image_assets"], 0)
        self.assertEqual(summary["assets"], [])
