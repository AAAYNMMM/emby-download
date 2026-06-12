"""
debug_prepare_task.py - Trace prepare phase for a task (no actual download).
"""
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
import argparse
from app.downloader.task_store import get_task
from app.config.settings import load_config
def main():
    parser = argparse.ArgumentParser(description="Debug prepare phase")
    parser.add_argument("task_id", help="Task ID to debug")
    args = parser.parse_args()
    print("=" * 60)
    print("PREPARE PHASE DEBUGGER")
    print("=" * 60)
    task = get_task(args.task_id)
    if task is None:
        print(f"FAIL: Task {args.task_id} not found")
        sys.exit(1)
    print(f"[1] Task loaded: {task.task_id} item={task.item_id} status={task.status}")
    config = load_config()
    print(f"[2] Config: server={'[set]' if config.server_url else '[empty]'} dir={config.download_dir or '[empty]'}")
    from app.core.auth import get_token
    token = get_token(config)
    if not token:
        print("FAIL: No token (not logged in)")
        sys.exit(1)
    print(f"[3] Token: available (prefix={token[:8]})")
    if not config.download_dir:
        print("FAIL: download_dir not configured")
        sys.exit(1)
    print(f"[4] Download dir: {config.download_dir}")
    from app.core.emby_api import EmbyApiClient
    client = EmbyApiClient(config.server_url, token)
    try:
        user = client.get_user()
        user_id = user.get("Id", "")
    except Exception as e:
        print(f"FAIL: get_user: {e}")
        sys.exit(1)
    print(f"[5] User ID: {user_id}")
    try:
        item = client.get_item_metadata(task.item_id, user_id)
    except Exception as e:
        print(f"FAIL: get_item_metadata: {e}")
        sys.exit(1)
    print(f"[6] Item metadata: {item.get('Name','?')} ({item.get('Type','?')})")
    try:
        playback_info = client.get_playback_info(task.item_id, user_id)
    except Exception as e:
        print(f"FAIL: get_playback_info: {e}")
        sys.exit(1)
    from app.core.playback_info import parse_media_sources, find_source_by_id, select_best_source
    sources = parse_media_sources(playback_info)
    print(f"[7] PlaybackInfo: {len(sources)} source(s)")
    if task.media_source_id:
        best = find_source_by_id(sources, task.media_source_id)
        if best is None:
            print(f"FAIL: media_source_id={task.media_source_id} not found")
            client.close()
            sys.exit(1)
        print(f"    Using selected source: {best.id[:20]} container={best.container}")
    else:
        best = select_best_source(sources)
        if best is None:
            print("FAIL: No sources available")
            client.close()
            sys.exit(1)
        print(f"    Auto-selected: {best.id[:20]} container={best.container}")
    from app.core.download_capability import check_download_capability
    cap = check_download_capability(client, task.item_id, best)
    if not cap.can_download:
        print(f"FAIL: {cap.reason}")
        client.close()
        sys.exit(1)
    print(f"[8] Capability: method={cap.recommended_method.value} size={cap.file_size or 0}")
    print("=" * 60)
    print("Result: All prepare checks passed. Ready to download.")
    print("(No download was started)")
    print("=" * 60)
    client.close()
if __name__ == "__main__":
    main()