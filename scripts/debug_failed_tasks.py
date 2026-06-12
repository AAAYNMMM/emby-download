"""
debug_failed_tasks.py - Diagnostic script for failed download tasks.
"""
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
import argparse
import sqlite3
from app.config.settings import get_app_dir
def main():
    parser = argparse.ArgumentParser(description="Debug failed download tasks")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    app_dir = get_app_dir()
    db_path = app_dir / "tasks.db"
    if not db_path.exists():
        print(f"tasks.db not found at {db_path}")
        return
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        failed_count = conn.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status='failed'").fetchone()["cnt"]
        all_count = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]
        print(f"Total: {all_count}, Failed: {failed_count}")
        if failed_count == 0:
            print("No failed tasks found.")
            return
        rows = conn.execute("SELECT * FROM tasks WHERE status='failed' ORDER BY updated_at DESC LIMIT ?", (args.limit,)).fetchall()
        for i, r in enumerate(rows, 1):
            d = dict(r)
            err = d.get("error_message") or "(empty)"
            sp = d.get("save_path") or "(empty)"
            msid = d.get("media_source_id") or "(empty)"
            title = (d.get("display_title") or d.get("title") or "")[:60]
            print(f"[{i}] {d['task_id']} status={d['status']}")
            print(f"    title={title}")
            print(f"    error={err}")
            print(f"    save_path={sp}")
            print(f"    media_source_id={msid}")
            print(f"    total_bytes={d['total_bytes']} downloaded={d['downloaded_bytes']}")
    finally:
        conn.close()
if __name__ == "__main__":
    main()