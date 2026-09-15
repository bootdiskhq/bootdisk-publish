import unittest

from bootdisk_publish.frontend import frontend_assets


class FrontendAssetProjectionTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "schema_version": "bootdisk-publish-1",
            "assets": [
                {
                    "entry_source_id": "K37",
                    "entry_title": "WinAmp 2.76",
                    "kind": "icon",
                    "source_path": "WinAmp/Ikon.bmp",
                    "original": {
                        "sha256": "a" * 64,
                        "size": 3126,
                        "object_key": f"originals/{'a' * 64}",
                    },
                    "derivatives": [
                        {
                            "kind": "thumbnail",
                            "media_type": "image/webp",
                            "sha256": "b" * 64,
                            "width": 64,
                            "height": 64,
                            "object_key": f"derivatives/{'b' * 64}.webp",
                        }
                    ],
                },
                {
                    "entry_source_id": "K38",
                    "entry_title": "WinZip 8.0",
                    "kind": "screenshot",
                    "source_path": "WinZip/Shot.jpg",
                    "original": {
                        "sha256": "c" * 64,
                        "size": 100,
                        "object_key": f"originals/{'c' * 64}",
                    },
                    "derivatives": [],
                },
            ],
        }

    def test_projects_deployment_neutral_public_paths(self):
        result = frontend_assets(self.document, "K37")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["entry"], "K37")
        self.assertEqual(result[0]["kind"], "icon")
        self.assertEqual(
            result[0]["original"]["public_path"],
            f"/store/originals/{'a' * 64}",
        )
        self.assertEqual(
            result[0]["derivatives"][0]["public_path"],
            f"/store/derivatives/{'b' * 64}.webp",
        )

    def test_projection_does_not_invent_catalog_identity(self):
        result = frontend_assets(self.document, "K37")

        self.assertNotIn("software", result[0])
        self.assertNotIn("release", result[0])
        self.assertEqual(result[0]["editorial_title"], "WinAmp 2.76")


if __name__ == "__main__":
    unittest.main()
