"""Command line entry point for guarded multichannel migrations."""

import argparse
import json
from pathlib import Path

from . import database_path, migrate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["migrate"])
    parser.add_argument("--profile", required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--root", type=Path, default=Path("/app/multicanal-data"))
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = migrate(
        args.profile,
        database_path(args.database_url),
        args.root,
        args.deployment_id,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
