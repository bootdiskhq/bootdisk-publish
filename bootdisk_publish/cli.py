"""Command-line interface for bootdisk-publish."""

import argparse
import json
import sys

from . import __version__
from .assets import iter_image_assets
from .bundle import publish_image_bundle
from .manifest import ManifestError, load_ingest_manifest


def _inspection_summary(manifest):
    assets = iter_image_assets(manifest)
    return {
        "schema_version": manifest.schema_version,
        "source_format": manifest.source.get("format"),
        "entries": len(manifest.entries),
        "inventory_files": len(manifest.file_inventory),
        "image_assets": len(assets),
        "assets": [
            {
                "entry_source_id": asset.entry_source_id,
                "entry_title": asset.entry_title,
                "kind": asset.kind,
                "path": asset.path,
                "size": asset.size,
                "sha256": asset.sha256,
            }
            for asset in assets
        ],
    }


def build_parser():
    parser = argparse.ArgumentParser(prog="bootdisk-publish")
    parser.add_argument("manifest", nargs="?", help="Path to an ingest manifest")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Validate the manifest and print a source-agnostic summary",
    )
    parser.add_argument(
        "--publish-images",
        action="store_true",
        help="Publish explicit image originals, WebP thumbnails, and publish-manifest.json",
    )
    parser.add_argument(
        "--extraction",
        help="Path to the preservation extraction used as the only asset byte source",
    )
    parser.add_argument(
        "--output",
        help="Output directory for the publication bundle",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if not args.manifest:
        print("error: an ingest manifest is required", file=sys.stderr)
        return 2

    try:
        manifest = load_ingest_manifest(args.manifest)
        if args.inspect:
            print(json.dumps(_inspection_summary(manifest), ensure_ascii=False, indent=2))
            return 0

        if args.publish_images:
            if not args.extraction or not args.output:
                print(
                    "error: --publish-images requires --extraction and --output",
                    file=sys.stderr,
                )
                return 2
            result = publish_image_bundle(
                args.manifest,
                args.extraction,
                args.output,
            )
            print(
                json.dumps(
                    {
                        "publish_manifest": str(result.manifest_path),
                        "originals": result.originals.total,
                        "originals_created": result.originals.created,
                        "originals_reused": result.originals.reused,
                        "thumbnails": len(result.thumbnails),
                        "thumbnails_created": sum(item.created for item in result.thumbnails),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        "Manifest is valid. Use --inspect or --publish-images.",
        file=sys.stderr,
    )
    return 0
