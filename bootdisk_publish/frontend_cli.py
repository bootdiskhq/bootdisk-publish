"""Command-line access to the disposable frontend asset projection."""

import argparse
import json
import sys

from .frontend import FrontendProjectionError, frontend_assets, load_publish_manifest


def build_parser():
    parser = argparse.ArgumentParser(prog="python -m bootdisk_publish.frontend_cli")
    parser.add_argument("publish_manifest", help="Path to publish-manifest.json")
    parser.add_argument(
        "--entry",
        help="Limit output to one stable ingest entry source id, for example K37",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        document = load_publish_manifest(args.publish_manifest)
        projected = frontend_assets(document, args.entry)
    except FrontendProjectionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(projected, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
