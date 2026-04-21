from __future__ import annotations

import argparse
import json

from shared import SqlitePaymentStore

from .payment_store_tools import backup_sqlite_database, export_payment_snapshot, import_payment_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export, import, or back up AimiPay payment snapshots.")
    parser.add_argument("mode", choices=["export", "import", "backup"])
    parser.add_argument("--sqlite-path", required=True)
    parser.add_argument("--snapshot-path")
    parser.add_argument("--backup-dir")
    args = parser.parse_args(argv)

    store = SqlitePaymentStore(args.sqlite_path)
    if args.mode == "export":
        if not args.snapshot_path:
            parser.error("--snapshot-path is required for export")
        payload = export_payment_snapshot(store, args.snapshot_path)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.mode == "import":
        if not args.snapshot_path:
            parser.error("--snapshot-path is required for import")
        payload = import_payment_snapshot(store, args.snapshot_path)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if not args.backup_dir:
        parser.error("--backup-dir is required for backup")
    destination = backup_sqlite_database(args.sqlite_path, backup_dir=args.backup_dir)
    print(json.dumps({"backup_path": str(destination)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
