"""Migration tool for Codi persistent memory.

Usage:
  Export:  python utils/migrate.py export [--output backup.json]
  Import:  python utils/migrate.py import --input backup.json [--overwrite]
  Stats:   python utils/migrate.py stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_settings
from core.memory import MemoryStore


def cmd_export(args: argparse.Namespace) -> None:
    store = _open_store()
    data = store.export_all()
    store.close()

    out_path = Path(args.output)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    totals = {t: len(rows) for t, rows in data["tables"].items()}
    print(f"Exported to {out_path}")
    for table, count in totals.items():
        print(f"  {table}: {count} rows")


def cmd_import(args: argparse.Namespace) -> None:
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"File not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(in_path.read_text(encoding="utf-8"))
    version = data.get("version")
    if version != 1:
        print(f"Unsupported backup version: {version}", file=sys.stderr)
        sys.exit(1)

    store = _open_store()
    counts = store.import_all(data, overwrite=args.overwrite)
    store.close()

    print(f"Imported from {in_path} (overwrite={args.overwrite})")
    for table, count in counts.items():
        print(f"  {table}: {count} rows")


def cmd_stats(args: argparse.Namespace) -> None:
    store = _open_store()
    data = store.export_all()
    store.close()

    print(f"Memory DB: {_db_path()}")
    print(f"Exported at: {data['exported_at']}")
    for table, rows in data["tables"].items():
        print(f"  {table}: {len(rows)} rows")
        if table == "session_history" and rows:
            user_ids = {r["user_id"] for r in rows}
            print(f"    users: {sorted(user_ids)}")
        if table == "repo_knowledge" and rows:
            for r in rows:
                print(f"    {r['repo_path']} (updated {r['updated_at'][:10]})")


def _db_path() -> Path:
    try:
        settings = load_settings()
        return Path(settings.memory_db_path)
    except Exception:
        return Path("/home/odc/ai-agent-telegram/codi-memory.db")


def _open_store() -> MemoryStore:
    return MemoryStore(_db_path())


def main() -> None:
    parser = argparse.ArgumentParser(description="Codi memory migration tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="Export memory to JSON")
    p_export.add_argument("--output", default="codi-memory-backup.json", help="Output file path")
    p_export.set_defaults(func=cmd_export)

    p_import = sub.add_parser("import", help="Import memory from JSON")
    p_import.add_argument("--input", required=True, help="Input backup file path")
    p_import.add_argument("--overwrite", action="store_true", help="Overwrite existing rows")
    p_import.set_defaults(func=cmd_import)

    p_stats = sub.add_parser("stats", help="Show memory stats")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
