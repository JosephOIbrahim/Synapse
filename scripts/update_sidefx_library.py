"""Snapshot, resume/update and connect a complete local SideFX library.

Run from any working directory; all generated documentation stays outside Git.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from rag.ingest.sidefx_download import Downloader
from rag.ingest.sidefx_library import atomic_json, build_library, snapshot_installed, writer_lock


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--hfs', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--refresh', action='store_true', help='Revalidate cached web pages with ETag/Last-Modified')
    parser.add_argument('--installed-only', action='store_true', help='Explicit offline mode; retain installed wiki source fidelity labels')
    parser.add_argument('--allow-incomplete-web', action='store_true', help='Publish available pages with visible coverage gaps')
    parser.add_argument('--connect', action='store_true', help='Write this checkout local Scout source configuration')
    args = parser.parse_args(argv)
    args.root = args.root.resolve()
    with writer_lock(args.root):
        installed = snapshot_installed(args.root, args.hfs.resolve())
        if not args.installed_only:
            web = Downloader(args.root, workers=args.workers).run(resume=not args.refresh, refresh=args.refresh)
            if not web.get('fetch_complete') and not args.allow_incomplete_web:
                print(json.dumps({'status': 'web_incomplete', 'counts': web['counts'],
                                  'manifest': str(args.root / 'web_manifest.json'),
                                  'active_index_unchanged': True}, sort_keys=True, indent=2))
                return 2
        result = build_library(args.root, include_web=not args.installed_only,
                               allow_incomplete_web=args.allow_incomplete_web,
                               runtime_build=installed['docs_build'])
    if args.connect:
        atomic_json(REPO / '.synapse/sidefx_library.json',
                    {'schema': 'synapse_sidefx_library/v1', 'root': str(args.root)})
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
