#!/usr/bin/env python
"""
Diagnostic script: debug start pending task chain.

Usage:
    python scripts/debug_start_pending_task.py

This script tests the real backend start/resume API chain:
1. Reads local backend port from embyd_backend.port
2. Queries tasks list
3. Finds first pending task
4. Calls start endpoint
5. Polls status every 1 second for 10 seconds
6. Reports status flow: pending -> preparing -> downloading / failed

No sensitive data (token/password/server_url) is output.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
PORT_FILE = PROJECT_DIR / "embyd_backend.port"
PID_FILE = PROJECT_DIR / "embyd_backend.pid"


def read_backend_port():
    """Read backend port from port file."""
    if not PORT_FILE.exists():
        print("ERROR: Backend port file not found (embyd_backend.port)")
        print("       Is the backend running?")
        return None
    try:
        port = int(PORT_FILE.read_text().strip())
        return port
    except (ValueError, OSError) as e:
        print(f"ERROR: Failed to read port file: {e}")
        return None


def check_backend_pid():
    """Check if backend PID process is alive."""
    if not PID_FILE.exists():
        print("WARN: Backend PID file not found")
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        import os
        # Windows: use tasklist to check
        if sys.platform == "win32":
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True
            )
            return "python" in result.stdout.lower() or "embyd" in result.stdout.lower()
        else:
            # Unix: send signal 0
            os.kill(pid, 0)
            return True
    except (ValueError, OSError):
        return False


def api_request(port, method, path, body=None):
    """Make HTTP request to backend API. Returns (status, body_dict)."""
    url = f"http://127.0.0.1:{port}{path}"
    try:
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            return resp.status, resp_body
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"error": str(e)}
        return e.code, err_body
    except urllib.error.URLError as e:
        return 0, {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return 0, {"error": str(e)}


def mask_sensitive(text):
    """Mask sensitive data in a string."""
    if not isinstance(text, str):
        return text
    keywords = ["token", "password", "api_key", "secret"]
    for kw in keywords:
        if kw.lower() in text.lower():
            # Replace the value part
            idx = text.lower().find(kw.lower())
            if idx >= 0:
                return text[:idx + len(kw) + 1] + "****"
    return text


def main():
    print("=" * 60)
    print("  EmbyD Backend Start Task Diagnostic")
    print("=" * 60)

    # 1. Read backend port
    port = read_backend_port()
    if port is None:
        print("\nRESULT: FAILED - No backend port found")
        print("ACTION: Start the EmbyD GUI and ensure the backend is running.")
        return 1
    print(f"  Backend port: {port}")

    # 2. Check if backend PID is alive
    pid_alive = check_backend_pid()
    print(f"  Backend PID alive: {pid_alive}")

    # 3. Health check
    print("\n--- Health Check ---")
    status, health = api_request(port, "GET", "/api/health")
    if status != 200:
        print(f"  ERROR: Backend health check failed (HTTP {status}): {health.get('error', 'unknown')}")
        print("\nRESULT: FAILED - Backend API not reachable")
        print("ACTION: The backend process may have crashed. Restart the GUI.")
        return 1
    print(f"  Health: {health.get('status', 'unknown')}")

    # 4. Query tasks
    print("\n--- Tasks ---")
    status, tasks = api_request(port, "GET", "/api/tasks?limit=200")
    if status != 200:
        print(f"  ERROR: Failed to fetch tasks (HTTP {status})")
        return 1

    if isinstance(tasks, list):
        print(f"  Total tasks: {len(tasks)}")
        for t in tasks:
            tid = t.get("task_id", "?")[:8]
            tstat = t.get("status", "?")
            title_safe = (t.get("display_title") or t.get("title", "?"))[:40]
            print(f"    [{tstat:12}] {tid}...  {title_safe}")
    else:
        print(f"  Unexpected response: {type(tasks)}")
        tasks = []

    # 5. Find first pending task
    pending = [t for t in (tasks if isinstance(tasks, list) else []) if t.get("status") == "pending"]
    if not pending:
        print("\n  No pending tasks found.")
        print("  Checking for paused/failed tasks that can be resumed...")
        resumable = [t for t in (tasks if isinstance(tasks, list) else [])
                     if t.get("status") in ("paused", "failed")]
        if resumable:
            print(f"  Found {len(resumable)} resumable task(s).")
            task = resumable[0]
        else:
            print("\nRESULT: No pending or resumable tasks")
            print("ACTION: Create a download task from the GUI first.")
            return 0
    else:
        print(f"\n  Found {len(pending)} pending task(s). Selecting first.")
        task = pending[0]

    task_id = task["task_id"]
    task_title = (task.get("display_title") or task.get("title", "?"))[:40]
    task_status = task.get("status", "?")
    print(f"\n--- Selected Task ---")
    print(f"  Task ID:   {task_id[:16]}...")
    print(f"  Title:     {task_title}")
    print(f"  Status:    {task_status}")
    print(f"  Item ID:   {task.get('item_id', '?')[:16]}...")

    # 6. Call start endpoint
    print(f"\n--- Calling Start API ---")
    # Read download_dir from config (masked)
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from app.config.settings import load_config
        config = load_config()
        download_dir = config.download_dir or ""
    except Exception:
        download_dir = ""

    if not download_dir:
        print("  WARNING: download_dir is empty! API requires download_dir.")
        print("  Using fallback: current directory")
        download_dir = str(PROJECT_DIR)

    print(f"  download_dir: (set, length={len(download_dir)})")

    start_body = {"download_dir": download_dir}
    status, result = api_request(port, "POST", f"/api/tasks/{task_id}/start", start_body)
    print(f"  HTTP {status}: {json.dumps(result, default=str)}")

    if status not in (200, 201):
        print(f"\n  ERROR: Start request failed!")
        if isinstance(result, dict) and result.get("error"):
            print(f"  Error: {result['error']}")
        print("\nRESULT: FAILED - Start API returned error")
        return 1

    # 7. Poll status for 10 seconds
    print(f"\n--- Polling Status (10 seconds) ---")
    status_history = [task_status]
    target_endpoint = f"/api/tasks/{task_id}/start" if task_status == "pending" else f"/api/tasks/{task_id}/resume"

    for i in range(10):
        time.sleep(1)
        _, task_info = api_request(port, "GET", f"/api/tasks/{task_id}")
        if isinstance(task_info, dict):
            current_status = task_info.get("status", "?")
            error_msg = task_info.get("error_message", "")
            if current_status != (status_history[-1] if status_history else "?"):
                status_history.append(current_status)
                print(f"  T+{i+1:2d}s: status={current_status}", end="")
                if error_msg:
                    print(f"  error={mask_sensitive(error_msg)[:60]}")
                else:
                    print()
        else:
            print(f"  T+{i+1:2d}s: GET task failed")

    # 8. Summary
    print(f"\n--- Status Flow ---")
    flow = " -> ".join(status_history)
    print(f"  {flow}")

    final_status = status_history[-1] if status_history else "?"
    if final_status == "pending":
        print("\nRESULT: FAILED - Task still pending after 10 seconds!")
        print("  The backend start_task may not have been called.")
        print("  Check backend logs for errors.")
        print("  Possible causes:")
        print("    1. download_dir is invalid or not writable")
        print("    2. Backend has no valid token (not logged in)")
        print("    3. Emby server is not reachable")
        print("    4. Item media sources could not be resolved")
        return 1
    elif final_status in ("preparing", "downloading"):
        print(f"\nRESULT: PASSED - Task transitioned to {final_status}")
        return 0
    elif final_status == "failed":
        _, task_info = api_request(port, "GET", f"/api/tasks/{task_id}")
        err = ""
        if isinstance(task_info, dict):
            err = task_info.get("error_message", "")
        print(f"\nRESULT: Task failed (expected if env not configured)")
        if err:
            print(f"  Error: {mask_sensitive(err)[:200]}")
        return 0  # Not a code bug - task properly entered failed state
    else:
        print(f"\nRESULT: Task status is now {final_status}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
