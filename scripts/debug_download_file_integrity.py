#!/usr/bin/env python3
"""
Diagnose download file integrity issues.

Reads recent tasks from task_store and checks:
- Completed tasks: final file size == total_bytes
- Failed tasks: no final file (only .part)
- Paused tasks: no final file (only .part)
- Empty error messages
- Size mismatches

Usage:
    python scripts/debug_download_file_integrity.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.downloader.task_store import list_tasks
from app.downloader.base import PART_SUFFIX


def check():
    tasks = list_tasks()
    recent = tasks[-10:] if len(tasks) > 10 else tasks

    print("=" * 72)
    print("Download File Integrity Diagnostic")
    print("=" * 72)

    bad_count = 0
    for t in recent:
        print()
        print(f"--- Task: {t.task_id[:12]}... ---")
        print(f"  Title:        {t.title or '(none)'}")
        print(f"  Status:       {t.status}")
        print(f"  Total (DB):   {t.total_bytes or '?'}")
        print(f"  Downloaded:   {t.downloaded_bytes or '?'}")
        print(f"  Save path:    {t.save_path or '(none)'}")
        print(f"  Temp path:    {t.temp_path or '(none)'}")
        print(f"  Error msg:    {t.error_message or '(empty)'}")

        actual_final = (
            os.path.getsize(t.save_path) if t.save_path and os.path.exists(t.save_path) else None
        )
        part_path = t.temp_path
        if not part_path and t.save_path:
            part_path = t.save_path + PART_SUFFIX
        actual_part = (
            os.path.getsize(part_path) if part_path and os.path.exists(part_path) else None
        )

        print(f"  Final size:   {actual_final or '(none)'}")
        print(f"  Part size:    {actual_part or '(none)'}")

        # --- Rule checks ---
        issues = []

        if t.status == "completed":
            if actual_final is None:
                issues.append("BAD: completed but final file does not exist")
            elif t.total_bytes and t.total_bytes > 0 and actual_final != t.total_bytes:
                issues.append(
                    f"BAD: completed but final size {actual_final} != expected {t.total_bytes}"
                )
            if actual_part is not None:
                issues.append("WARN: .part file still exists after completed")

        elif t.status == "failed":
            if actual_final is not None:
                issues.append(f"BAD: failed but final file exists ({actual_final} bytes)")
            if not t.error_message or t.error_message.strip() == "":
                issues.append("BAD: failed but error_message is empty")

        elif t.status == "paused":
            if actual_final is not None:
                issues.append("BAD: paused but final file exists")
            if actual_part is None:
                issues.append("WARN: paused but no .part file")

        elif t.status == "cancelled":
            if actual_final is not None:
                issues.append("BAD: cancelled but final file exists")

        if t.error_message and "size mismatch" in t.error_message.lower():
            issues.append(f"NOTE: Error mentions size mismatch")

        for issue in issues:
            print(f"  >>> {issue}")
            bad_count += 1

    print()
    print("=" * 72)
    if bad_count:
        print(f"Found {bad_count} issue(s).")
    else:
        print("No issues found.")
    print("=" * 72)


if __name__ == "__main__":
    check()