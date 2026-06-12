"""
CLI command implementations for EmbyD.

Each function corresponds to a CLI subcommand and handles
the actual business logic (or dispatches to core modules).
"""

import os
import sys
from typing import Optional

from app.config.schema import EmbyConfig, CONFIG_FIELD_META
from app.config.settings import (
    load_config,
    save_config,
    get_config_path_display,
    config_exists,
)
from app.utils.logger import setup_logger, get_logger
from app.utils.redaction import redact_sensitive


def _format_cli_error(error: object) -> str:
    """Return redacted ASCII-only error text for Windows consoles."""
    text = redact_sensitive(error)
    return text.encode("ascii", errors="backslashreplace").decode("ascii")


def _resolve_download_dir(config: EmbyConfig, download_dir: Optional[str] = None) -> str:
    """Resolve the download directory or exit with a clear CLI error."""
    resolved = (download_dir or config.download_dir or "").strip()
    if not resolved:
        print("[ERROR] Download directory is not set.")
        print("        Use --dir <path> for this download, or run:")
        print("        embyd config set download_dir <path>")
        sys.exit(1)
    return resolved


def cmd_login(server: str, username: str, config_path: Optional[str] = None):
    """Login to Emby server and save access token."""
    import getpass

    from app.core.auth import login as auth_login
    from app.core.emby_api import EmbyAuthError

    password = getpass.getpass("Password: ")

    logger = get_logger()

    try:
        config, user_id = auth_login(
            server_url=server,
            username=username,
            password=password,
            storage_method="file",  # "keyring" for Windows Credential Manager
        )

        # Merge with existing config if any (preserve download_dir etc.)
        existing = load_config(config_path)
        existing.server_url = config.server_url
        existing.username = config.username
        existing.token_encrypted = config.token_encrypted
        existing.token_storage = config.token_storage

        save_config(existing, config_path)
        print(f"[OK] Successfully logged in as '{username}' (User ID: {user_id})")
        print(f"  Token saved securely to config file.")

    except EmbyAuthError as e:
        print(f"[ERROR] Authentication failed: {_format_cli_error(e)}")
        sys.exit(1)
    except ConnectionError as e:
        print(f"[ERROR] {_format_cli_error(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Login failed: {_format_cli_error(e)}")
        logger.error(f"Login error: {e}", exc_info=True)
        sys.exit(1)


def cmd_libraries(config_path: Optional[str] = None):
    """List available media libraries."""
    config = load_config(config_path)
    _ensure_logged_in(config)

    client = _create_client(config)

    try:
        libraries = client.get_libraries(_get_user_id(config))

        if not libraries:
            print("No media libraries found.")
            return

        print(f"\n{'ID':<10} {'Name':<40} {'Type':<15}")
        print("-" * 65)
        for lib in libraries:
            lib_id = lib.get("Id", "?")[:8]
            name = lib.get("Name", "Unknown")
            collection_type = lib.get("CollectionType", lib.get("Type", "unknown"))
            print(f"{lib_id:<10} {name:<40} {collection_type:<15}")

        print(f"\nTotal: {len(libraries)} libraries")

    except Exception as e:
        _handle_api_error(e, "Failed to fetch libraries")
    finally:
        client.close()


def cmd_search(
    query: str,
    library: Optional[str] = None,
    limit: int = 20,
    config_path: Optional[str] = None,
):
    """Search for movies and TV episodes by title."""
    config = load_config(config_path)
    _ensure_logged_in(config)

    client = _create_client(config)

    try:
        items = client.search_items(
            user_id=_get_user_id(config),
            query=query,
            parent_id=library,
            limit=limit,
        )

        if not items:
            print(f'No results found for "{query}".')
            return

        from app.core.download_preview import build_item_display_title, format_episode_code

        print(f'\nSearch results for "{query}":')
        print(f"{'ID':<12} {'Title':<50} {'Year':<6} {'Type':<12}")
        print("-" * 80)
        for item in items:
            item_id = item.get("Id", "?")[:10]
            name = build_item_display_title(item)
            year = item.get("ProductionYear", "")
            if item.get("Type") == "Episode":
                year = format_episode_code(
                    int(item.get("ParentIndexNumber") or 0),
                    int(item.get("IndexNumber") or 0),
                )
            item_type = item.get("Type", "")
            print(f"{item_id:<12} {name:<50} {str(year):<6} {item_type:<12}")

        print(f"\nTotal: {len(items)} results")

    except Exception as e:
        _handle_api_error(e, "Failed to search")
    finally:
        client.close()


def cmd_info(item_id: str, verbose: bool = False, config_path: Optional[str] = None):
    """Show movie details and download capability."""
    config = load_config(config_path)
    _ensure_logged_in(config)

    client = _create_client(config)

    try:
        from app.core.playback_info import parse_media_sources, select_best_source
        from app.core.download_capability import (
            check_download_capability,
            get_method_icon,
            get_method_label,
        )

        # Get item details
        user_id = _get_user_id(config)
        item = client.get_item(user_id, item_id)

        # Basic info
        name = item.get("Name", "Unknown")
        year = item.get("ProductionYear", "")
        runtime = item.get("RunTimeTicks", 0) // 100 // 60  # minutes
        genres = ", ".join(item.get("Genres", [])) or "N/A"
        overview = item.get("Overview", "")
        container = item.get("MediaSources", [{}])[0].get("Container", "N/A") if item.get("MediaSources") else "N/A"

        print(f"\n{'='*60}")
        print(f"  {name} ({year})")
        print(f"{'='*60}")
        print(f"  Runtime:      {runtime} min")
        print(f"  Container:    {container.upper()}")
        print(f"  Genres:       {genres}")
        if overview:
            # Show first 200 chars of overview
            short_overview = overview[:200] + ("..." if len(overview) > 200 else "")
            print(f"  Overview:     {short_overview}")
        print()

        # Get PlaybackInfo
        playback_info = client.get_playback_info(item_id, user_id)
        sources = parse_media_sources(playback_info)

        if not sources:
            print(f"  [WARNING] No media sources found for this item.")
            return

        print(f"  Media Sources ({len(sources)} total):")
        print(f"  {'-'*56}")

        for i, source in enumerate(sources, 1):
            cap = check_download_capability(client, item_id, source)
            icon = get_method_icon(cap.recommended_method)
            method_label = get_method_label(cap.recommended_method)
            size_str = source.size_human
            dur_str = source.duration_human

            print(f"  [{i}] {source.name or 'Default'}")
            print(f"      Container:  {source.container.upper() or 'N/A'}")
            print(f"      Size:       {size_str}")
            print(f"      Duration:   {dur_str}")
            print(f"      Protocol:   {source.protocol}")
            print(f"      Download:   {icon} {method_label}")

            if verbose:
                print(f"      MediaSourceId: {source.id}")
                print(f"      Bitrate:       {source.bitrate:,} bps")
                print(f"      DirectStream:  {source.supports_direct_stream}")
                print(f"      Transcoding:   {source.supports_transcoding}")
                print(f"      RequiresTrans: {source.requires_transcoding}")
                print(f"      IsRemote:      {source.is_remote}")
                print(f"      Path:          {source.path}")

            print()

        # Summary
        best = select_best_source(sources)
        if best:
            cap = check_download_capability(client, item_id, best)
            icon = get_method_icon(cap.recommended_method)
            status = "Available" if cap.can_download else "NOT Available"
            print(f"  {'='*56}")
            print(f"  Best Source:   {best.name or 'Default'}")
            print(f"  Download:      {icon} {status}")
            print(f"  Method:        {get_method_label(cap.recommended_method)}")
            if cap.file_size:
                from app.core.playback_info import format_size
                print(f"  File Size:     {format_size(cap.file_size)}")
            print(f"  Info:          {cap.reason}")

    except Exception as e:
        _handle_api_error(e, f"Failed to get info for item {item_id}")
    finally:
        client.close()


def cmd_dry_run(
    item_id: str,
    download_dir: Optional[str] = None,
    method: str = "auto",
    config_path: Optional[str] = None,
):
    """Preview what would be downloaded without actually downloading."""
    from app.core.auth import get_token
    from app.core.download_preview import build_download_preview

    config = load_config(config_path)
    _ensure_logged_in(config)

    token = get_token(config)
    if not token:
        print("Error: No access token found. Run 'embyd login' first.")
        sys.exit(1)

    dl_dir = _resolve_download_dir(config, download_dir)

    result = build_download_preview(
        item_id=item_id,
        server_url=config.server_url,
        token=token,
        download_dir=dl_dir,
        method=method,
    )

    if result.error_message:
        print(f"[ERROR] {result.error_message}")
        sys.exit(1)

    print(f"\n{'='*60}")
    year_str = f" ({result.year})" if result.year else ""
    print(f"  [DRY-RUN] Item: {result.title}{year_str}")
    print(f"{'='*60}")

    print(f"\n  Title:       {result.title}")
    if result.year:
        print(f"  Year:        {result.year}")
    print(f"  Sources:     {result.media_source_count} total")
    print(f"  Container:   {result.container}")
    print(f"  Size:        {result.size_human}")
    print(f"  Duration:    {result.runtime_human}")
    print(f"  Protocol:    {result.protocol}")
    print(f"  Method:      {result.method_label}")
    status = "[OK] Downloadable" if result.can_download else "[FAIL] Cannot download"
    print(f"  Status:      {status}")
    print(f"  Reason:      {result.reason}")
    print(f"  Output:      {result.output_path}")

    if method != "auto":
        print(f"  Requested:   {method} (overrides auto-select)")
        if method == "direct" and not result.can_download:
            print("  [WARNING] Direct download not available; will fall back to best method")

    print(f"\n  [DRY-RUN] No files were downloaded. Use without --dry-run to download.")
    print(f"{'='*60}")


def cmd_download(
    item_id: str,
    download_dir: Optional[str] = None,
    method: str = "auto",
    resume: bool = False,
    config_path: Optional[str] = None,
    with_subtitles: bool = False,
    with_metadata: bool = False,
    subtitle_lang: Optional[str] = None,
):
    """Download a movie or TV episode file to local storage."""
    from pathlib import Path

    config = load_config(config_path)
    _ensure_logged_in(config)

    client = _create_client(config)

    try:
        user_id = _get_user_id(config)
        item = client.get_item_metadata(item_id, user_id)
        from app.core.download_preview import build_item_display_title, build_item_filename_base

        name = item.get("Name", f"item_{item_id}")
        year = item.get("ProductionYear", "")
        display_title = build_item_display_title(item)

        # Get PlaybackInfo and decide download method
        from app.core.playback_info import parse_media_sources, select_best_source
        from app.core.download_capability import (
            check_download_capability,
            DownloadMethod,
            get_method_label,
        )

        playback_info = client.get_playback_info(item_id, user_id)
        sources = parse_media_sources(playback_info)

        if not sources:
            print(f"[ERROR] No media sources found for item {item_id}")
            return

        best_source = select_best_source(sources)
        cap = check_download_capability(client, item_id, best_source)

        if not cap.can_download:
            print(f"[ERROR] Cannot download this item.")
            print(f"  Reason: {cap.reason}")
            return

        # Override method if specified
        if method == "direct" and cap.recommended_method != DownloadMethod.DIRECT:
            print("[WARNING] Direct download not available for this item. Using best available method.")
        elif method == "stream" and cap.recommended_method != DownloadMethod.STREAM:
            print("[WARNING] Stream download not available for this item. Using best available method.")

        download_url = cap.recommended_url
        download_method = cap.recommended_method
        file_size = cap.file_size or best_source.size

        # Determine output path
        movie_name = build_item_filename_base(item)
        container = best_source.container or "mkv"
        filename = f"{movie_name}.{container}"

        dl_dir = Path(_resolve_download_dir(config, download_dir))
        dl_dir = dl_dir.resolve()
        dl_dir.mkdir(parents=True, exist_ok=True)
        dest_path = str(dl_dir / filename)
        temp_path = dest_path + ".part"

        # Check for existing completed download
        if os.path.exists(dest_path):
            existing_size = os.path.getsize(dest_path)
            if file_size and existing_size >= file_size:
                print(f"[OK] File already exists: {dest_path}")
                print(f"  Size: {existing_size} bytes - already downloaded.")
                return
            else:
                print(f"[INFO] Partial file exists ({existing_size} bytes), will overwrite.")

        # Check task store for existing completed task
        from app.downloader.task_store import task_exists, create_task, update_task
        if task_exists(item_id, "completed"):
            print(f"[INFO] Task for item '{name}' was already completed. Use --resume to re-download.")
            # Continue anyway if user explicitly requested

        # Check Windows path length
        MAX_PATH = 260
        if len(dest_path) >= MAX_PATH:
            print(f"[WARNING] Output path length ({len(dest_path)} chars) exceeds Windows limit of {MAX_PATH}.")
            print(f"  Path: {dest_path}")
            print(f"  Download may fail. Consider using a shorter download directory.")
            print(f"  You can set it with: embyd config set download_dir <shorter_path>")

        # Create a new task record
        task = create_task(
            item_id=item_id,
            title=name,
            download_url=download_url,
            save_path=dest_path,
            temp_path=temp_path,
            total_bytes=file_size,
            media_source_id=best_source.id,
            container=best_source.container,
        )
        update_task(task.task_id, status="downloading")

        print(f"\n{'='*60}")
        print(f"  Downloading: {display_title}")
        print(f"  Task ID:     {task.task_id}")
        print(f"  Method:      {get_method_label(download_method)}")
        if file_size:
            from app.core.playback_info import format_size
            print(f"  Size:        {format_size(file_size)}")
        print(f"  Save to:     {dest_path}")
        print(f"{'='*60}\n")

        # Progress bar
        from tqdm import tqdm
        init_pbar = (os.path.getsize(temp_path) if resume and os.path.exists(temp_path) else 0)
        pbar = tqdm(
            total=file_size or 0,
            initial=init_pbar,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=name[:30],
            leave=True,
        )

        def progress_callback(downloaded, total, speed):
            pbar.total = total or pbar.total
            pbar.n = downloaded
            pbar.set_postfix(speed=f"{download_speed(speed)}", refresh=False)
            pbar.refresh()
            # Update task store periodically
            if int(downloaded) % (1024 * 1024 * 4) < 65536:  # every ~4MB
                update_task(task.task_id, downloaded_bytes=int(downloaded))

        # Run async download
        import asyncio
        from app.downloader.direct_download import download_direct
        from app.downloader.stream_download import download_stream

        async def run_download():
            if download_method == DownloadMethod.STREAM:
                return await download_stream(
                    url=download_url,
                    dest_path=dest_path,
                    chunk_size=config.chunk_size_mb * 1024 * 1024,
                    resume=resume,
                    retry_count=config.retry_count,
                    retry_delay=config.retry_delay_seconds,
                    timeout=config.timeout_seconds,
                    progress_callback=progress_callback,
                )
            else:
                return await download_direct(
                    url=download_url,
                    dest_path=dest_path,
                    chunk_size=config.chunk_size_mb * 1024 * 1024,
                    resume=resume,
                    retry_count=config.retry_count,
                    retry_delay=config.retry_delay_seconds,
                    timeout=config.timeout_seconds,
                    progress_callback=progress_callback,
                )

        result = asyncio.run(run_download())
        pbar.close()

        if result.success:
            update_task(task.task_id, status="completed", downloaded_bytes=result.total_bytes)
            print(f"\n[OK] Download complete: {dest_path}")

            # --- Metadata download (Stage 7) ---
            dl_dir_str = str(dl_dir)

            if with_metadata or with_subtitles:
                import asyncio

            item_type = item.get("Type", "")
            if with_metadata and item_type != "Movie":
                print("[WARNING] NFO metadata generation currently supports movies only; skipping.")
            elif with_metadata:
                print(f"\n[INFO] Generating NFO metadata...")
                from app.metadata.metadata import generate_nfo
                try:
                    nfo = generate_nfo(item, dest_dir=dl_dir_str, base_name=movie_name)
                    print(f"[OK] NFO saved: {dl_dir_str}{os.sep}{movie_name}.nfo")
                except Exception as e:
                    print(f"[WARNING] Failed to generate NFO: {_format_cli_error(e)}")

            if with_subtitles:
                print(f"[INFO] Downloading subtitles...")
                from app.metadata.metadata import download_subtitles
                lang_filter = subtitle_lang.split(",") if subtitle_lang else None
                try:
                    sub_paths = asyncio.run(download_subtitles(
                        client, item_id, best_source.id, dl_dir_str, movie_name,
                        language_filter=lang_filter,
                    ))
                    if sub_paths:
                        for s in sub_paths:
                            print(f"[OK] Subtitle saved: {s}")
                    else:
                        print(f"[INFO] No subtitles found for download.")
                except Exception as e:
                    print(f"[WARNING] Failed to download subtitles: {_format_cli_error(e)}")

        else:
            status = "paused" if "cancelled" in result.error_message.lower() else "failed"
            update_task(task.task_id, status=status, error_message=result.error_message,
                        downloaded_bytes=result.downloaded_bytes)
            print(f"\n[ERROR] Download failed: {result.error_message}")

    except Exception as e:
        _handle_api_error(e, f"Failed to download item {item_id}")
    finally:
        client.close()


def download_speed(bytes_per_sec: float) -> str:
    """Format download speed for tqdm display."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.0f} B/s"
    elif bytes_per_sec < 1024 ** 2:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    elif bytes_per_sec < 1024 ** 3:
        return f"{bytes_per_sec / 1024 ** 2:.1f} MB/s"
    else:
        return f"{bytes_per_sec / 1024 ** 3:.2f} GB/s"


def cmd_tasks(
    status: Optional[str] = None,
    limit: int = 20,
    config_path: Optional[str] = None,
):
    """List download tasks."""
    config = load_config(config_path)
    _ensure_logged_in(config)

    from app.downloader.task_store import list_tasks, count_tasks

    try:
        tasks = list_tasks(status_filter=status, limit=limit)
        total = count_tasks(status_filter=status)

        if not tasks:
            print("No download tasks found.")
            return

        print(f"\nDownload Tasks (showing {len(tasks)} of {total} total):")
        if status:
            print(f"  Filter: status = {status}")
        print(f"{'ID':<10} {'Title':<35} {'Size':<12} {'Progress':<10} {'Status':<12}")
        print("-" * 79)

        for t in tasks:
            size_str = f"{t.total_bytes / (1024**3):.1f} GB" if t.total_bytes > 0 else "?"
            if t.total_bytes > 0:
                pct = int(t.downloaded_bytes * 100 / t.total_bytes)
            else:
                pct = 0
            progress = f"{pct}% ({t.downloaded_bytes//(1024**2)}MB)" if t.downloaded_bytes > 0 else "0%"
            print(f"{t.task_id:<10} {t.title[:34]:<35} {size_str:<12} {progress:<10} {t.status:<12}")

    except Exception as e:
        _handle_api_error(e, "Failed to list tasks")


def cmd_resume(task_id: Optional[str] = None, config_path: Optional[str] = None):
    """Resume failed or paused downloads."""
    config = load_config(config_path)
    _ensure_logged_in(config)

    from app.downloader.task_store import get_task, list_tasks, update_task

    try:
        # If no task_id specified, resume all failed/paused tasks
        if not task_id:
            pending = list_tasks(status_filter="failed", limit=50)
            pending += list_tasks(status_filter="paused", limit=50)
            if not pending:
                print("No failed or paused tasks to resume.")
                return
            print(f"Found {len(pending)} tasks to resume:")
            for t in pending[:10]:
                print(f"  {t.task_id}: {t.title} ({t.status}, {t.downloaded_bytes}/{t.total_bytes} bytes)")
            if len(pending) > 10:
                print(f"  ... and {len(pending) - 10} more")
            print("\nUse 'embyd resume <task_id>' to resume a specific task.")
            return

        # Resume a specific task
        task = get_task(task_id)
        if not task:
            print(f"[ERROR] Task '{task_id}' not found.")
            return

        if task.status == "completed":
            print(f"[INFO] Task '{task_id}' is already completed.")
            if task.save_path and os.path.exists(task.save_path):
                print(f"  File: {task.save_path}")
            return

        if task.status == "pending":
            print(f"[INFO] Task '{task_id}' has not started yet. Use 'embyd download' instead.")
            return

        # Verify .part file exists
        temp_path = task.temp_path
        if not temp_path or not os.path.exists(temp_path):
            print(f"[WARNING] Temp file not found: {temp_path}")
            print(f"  Download will start from the beginning.")
            update_task(task_id, downloaded_bytes=0)
        else:
            part_size = os.path.getsize(temp_path)
            print(f"[INFO] Resuming from {part_size} bytes (temp file: {temp_path})")

        # Run the download
        from app.core.emby_api import EmbyApiClient
        client = EmbyApiClient(config.server_url)
        from app.core.auth import get_token
        token = get_token(config)
        if not token:
            print("[ERROR] No access token found.")
            return
        client.set_token(token)

        update_task(task_id, status="downloading")

        print(f"\n  Resuming: {task.title}")
        print(f"  Task ID:  {task.task_id}")
        print(f"{'='*50}\n")

        from tqdm import tqdm
        import asyncio
        from app.downloader.direct_download import download_direct

        init_bytes = os.path.getsize(temp_path) if temp_path and os.path.exists(temp_path) else 0
        pbar = tqdm(
            total=task.total_bytes or 0,
            initial=init_bytes,
            unit="B", unit_scale=True, unit_divisor=1024,
            desc=task.title[:30], leave=True,
        )

        def progress_callback(downloaded, total, speed):
            pbar.total = total or pbar.total
            pbar.n = downloaded
            pbar.set_postfix(speed=f"{download_speed(speed)}", refresh=False)
            pbar.refresh()

        async def run():
            return await download_direct(
                url=task.download_url,
                dest_path=task.save_path,
                resume=True,
                progress_callback=progress_callback,
            )

        result = asyncio.run(run())
        pbar.close()

        if result.success:
            update_task(task_id, status="completed", downloaded_bytes=result.total_bytes)
            print(f"\n[OK] Download complete: {task.save_path}")
        else:
            status = "paused" if "cancelled" in result.error_message.lower() else "failed"
            update_task(task_id, status=status, error_message=result.error_message)
            print(f"\n[ERROR] Download failed: {result.error_message}")

    except Exception as e:
        _handle_api_error(e, "Failed to resume download")


# --- Config subcommands (implemented in Stage 1) ---


def cmd_config_show(config_path: Optional[str] = None):
    """Display current configuration."""
    config = load_config(config_path)
    path = get_config_path_display(config_path)

    print(f"Configuration file: {path}")
    print()

    # Show all non-sensitive fields
    for field_name, meta in CONFIG_FIELD_META.items():
        if meta.get("sensitive", False):
            display_value = "*** (encrypted)" if getattr(config, field_name, "") else "(not set)"
        else:
            value = getattr(config, field_name, "")
            if value == "" or value is None:
                display_value = "(not set)"
            else:
                display_value = str(value)

        print(f"  {field_name:30s} = {display_value}")
        print(f"  {'':30s}  {meta['description']}")

    # Validate
    errors = config.validate()
    if errors:
        print()
        print("Configuration warnings:")
        for error in errors:
            print(f"  [WARNING] {error}")


def cmd_config_set(key: str, value: str, config_path: Optional[str] = None):
    """Set a configuration value."""
    config = load_config(config_path)

    if key not in CONFIG_FIELD_META:
        print(f"Error: Unknown configuration key '{key}'")
        print(f"Valid keys: {', '.join(sorted(CONFIG_FIELD_META.keys()))}")
        sys.exit(1)

    if CONFIG_FIELD_META[key].get("sensitive", False):
        print(f"Warning: '{key}' is a sensitive field. Use the login command instead.")
        sys.exit(1)

    # Type conversion based on schema defaults
    schema = EmbyConfig()
    default_value = getattr(schema, key)

    try:
        if isinstance(default_value, bool):
            typed_value = value.lower() in ("true", "1", "yes", "on")
        elif isinstance(default_value, int):
            typed_value = int(value)
        else:
            typed_value = value
    except (ValueError, TypeError) as e:
        print(f"Error: Cannot convert '{value}' to type {type(default_value).__name__}: {_format_cli_error(e)}")
        sys.exit(1)

    setattr(config, key, typed_value)

    errors = config.validate()
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  [ERROR] {error}")
        sys.exit(1)

    save_config(config, config_path)
    print(f"[OK] '{key}' set to '{value}'")


def cmd_config_get(key: str, config_path: Optional[str] = None):
    """Get a single configuration value."""
    config = load_config(config_path)

    if key not in CONFIG_FIELD_META:
        print(f"Error: Unknown configuration key '{key}'")
        sys.exit(1)

    value = getattr(config, key, "")
    if CONFIG_FIELD_META[key].get("sensitive", False) and value:
        print("***")
    else:
        print(value)


def _ensure_logged_in(config: EmbyConfig):
    """Check if user is logged in (has server_url and token)."""
    from app.core.auth import get_token

    if not config.server_url:
        print("Error: Not logged in. Run 'embyd login' first.")
        sys.exit(1)

    token = get_token(config)
    if not token:
        print("Error: No access token found. Run 'embyd login' first.")
        sys.exit(1)


def _create_client(config: EmbyConfig):
    """Create an EmbyApiClient from config with token."""
    from app.core.auth import get_token
    from app.core.emby_api import EmbyApiClient

    token = get_token(config)
    if not token:
        print("Error: No access token found. Run 'embyd login' first.")
        sys.exit(1)

    return EmbyApiClient(config.server_url, token)


def _get_user_id(config: EmbyConfig) -> str:
    """Get the user ID from the Emby server using current token."""
    client = _create_client(config)
    try:
        user = client.get_user()
        return user.get("Id", "")
    finally:
        client.close()


def _handle_api_error(e: Exception, context: str):
    """Handle API errors with user-friendly messages."""
    from app.core.emby_api import EmbyAuthError, EmbyNotFoundError, EmbyServerError

    if isinstance(e, EmbyAuthError):
        print(f"[ERROR] {context}: Authentication failed. {_format_cli_error(e)}")
    elif isinstance(e, EmbyNotFoundError):
        print(f"[ERROR] {context}: Resource not found.")
    elif isinstance(e, EmbyServerError):
        print(f"[ERROR] {context}: Server error. Please try again later.")
    else:
        print(f"[ERROR] {context}: {_format_cli_error(e)}")
        get_logger().error(f"{context}: {e}", exc_info=True)

    sys.exit(1)


def setup_logging(config: EmbyConfig, log_file: Optional[str] = None):
    """Initialize logging based on config."""
    level = config.log_level if config.log_level else "INFO"
    setup_logger(level=level, log_file=log_file)


# ---- Doctor command (Stage 8.5) ----


def cmd_doctor(config_path: Optional[str] = None):
    """Run diagnostic checks on the EmbyD installation and configuration."""
    import platform
    import sys
    import os

    print("=" * 60)
    print("  EmbyD Doctor - Diagnostic Report")
    print("=" * 60)

    # 1. Environment info
    print("\n[Environment]")
    print(f"  Python:      {sys.version.split()[0]}")
    print(f"  Platform:    {platform.platform()}")
    print(f"  Executable:  {sys.executable}")
    is_bundled = getattr(sys, 'frozen', False)
    print(f"  Packaged:    {'Yes (PyInstaller)' if is_bundled else 'No (source)'}")
    if is_bundled:
        import os
        print(f"  Exe path:    {os.path.abspath(sys.executable)}")

    # 2. Core module imports
    print("\n[Core Modules]")
    modules = [
        "app.config.settings", "app.config.schema",
        "app.core.emby_api", "app.core.auth",
        "app.core.playback_info", "app.core.download_capability",
        "app.core.naming",
        "app.downloader.range_downloader", "app.downloader.task_store",
        "app.metadata.metadata",
    ]
    for mod_name in modules:
        try:
            __import__(mod_name)
            print(f"  [OK] {mod_name}")
        except Exception as e:
            print(f"  [FAIL] {mod_name}: {_format_cli_error(e)}")

    # 3. Configuration
    print("\n[Configuration]")
    config = load_config(config_path)
    cfg_path = get_config_path_display(config_path)
    print(f"  Config file: {cfg_path}")
    print(f"  File exists: {'Yes' if os.path.exists(cfg_path) else 'No'}")

    if config.server_url:
        print(f"  Server URL:  {config.server_url}")
    else:
        print(f"  Server URL:  [Not set]")

    if config.username:
        print(f"  Username:    {config.username}")
    else:
        print(f"  Username:    [Not set]")

    # 4. Token
    print("\n[Token]")
    from app.core.auth import get_token
    token = get_token(config)
    if token:
        print(f"  Token:       [Present] ({len(token)} chars)")
    else:
        print(f"  Token:       [Not found]")
        print(f"  Token file:  {'Encrypted field set' if config.token_encrypted else 'Empty'}")

    # 5. Download directory
    print("\n[Download Directory]")
    dl_dir = (config.download_dir or "").strip()
    import os
    if not dl_dir:
        print("  Path:        [Not set]")
        print("  Status:      [INFO] Set with --dir or config set download_dir <path>")
    else:
        dl_path = os.path.abspath(dl_dir)
        print(f"  Path:        {dl_path}")
        if os.path.exists(dl_path):
            print(f"  Status:      [OK] Directory exists")
        else:
            try:
                os.makedirs(dl_path, exist_ok=True)
                print(f"  Status:      [OK] Directory created")
            except Exception as e:
                print(f"  Status:      [FAIL] Cannot create: {_format_cli_error(e)}")

    # 6. Task database
    print("\n[Task Database]")
    try:
        from app.downloader.task_store import count_tasks, get_task_db_path
        total = count_tasks()
        print(f"  Path:        {get_task_db_path()}")
        print(f"  Tasks:       {total} total")
        failing = count_tasks("failed")
        if failing > 0:
            print(f"  Warning:     {failing} failed tasks exist. Use 'embyd resume' to retry.")
    except Exception as e:
        print(f"  Status:      [FAIL] {_format_cli_error(e)}")

    # 7. Network check (optional)
    if config.server_url:
        print("\n[Server Connection]")
        from urllib.parse import urlparse
        parsed = urlparse(config.server_url)
        print(f"  Host:        {parsed.hostname}")
        print(f"  Port:        {parsed.port or (443 if parsed.scheme == 'https' else 80)}")
        print(f"  Protocol:    {parsed.scheme}")
        try:
            import requests
            try:
                r = requests.get(f"{config.server_url}/System/Info", timeout=5,
                                 headers={"X-Emby-Token": token if token else ""})
                if r.status_code == 200:
                    data = r.json()
                    print(f"  Status:      [OK] Server reachable")
                    print(f"  Server:      {data.get('ServerName', '?')} v{data.get('Version', '?')}")
                elif r.status_code == 401:
                    print(f"  Status:      [WARNING] Server reachable but token invalid (401)")
                else:
                    print(f"  Status:      [WARNING] HTTP {r.status_code}")
            except requests.exceptions.ConnectionError:
                print(f"  Status:      [FAIL] Cannot connect")
            except requests.exceptions.Timeout:
                print(f"  Status:      [FAIL] Timeout (>5s)")
            except Exception as e:
                print(f"  Status:      [FAIL] {_format_cli_error(e)}")
        except ImportError:
            print(f"  Status:      [SKIP] requests not available")

    print("\n" + "=" * 60)
    print("  Doctor check complete.")
    print("=" * 60)


# ---- Server commands (Stage 8.5) ----


def cmd_server_ping(config_path: Optional[str] = None):
    """Check if the Emby server is reachable."""
    config = load_config(config_path)

    if not config.server_url:
        print("[ERROR] No server URL configured. Run 'embyd login' or 'embyd config set server_url <url>' first.")
        return

    import requests
    try:
        print(f"Pinging {config.server_url}...")
        r = requests.get(f"{config.server_url}/System/Info", timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"[OK] Server is reachable.")
            print(f"     Name:    {data.get('ServerName', '?')}")
            print(f"     Version: {data.get('Version', '?')}")
        elif r.status_code == 401:
            print(f"[WARNING] Server reachable, but authentication required (401).")
            print(f"          Run 'embyd login' to authenticate.")
        else:
            print(f"[WARNING] Server returned HTTP {r.status_code}")
    except requests.exceptions.ConnectionError as e:
        error = str(e).lower()
        if "refused" in error:
            print(f"[FAIL] Connection refused. Is the server running at {config.server_url}?")
        else:
            print(f"[FAIL] Cannot connect to {config.server_url}. Check network.")
    except requests.exceptions.Timeout:
        print(f"[FAIL] Timeout (>10s): {config.server_url}")
    except Exception as e:
        print(f"[FAIL] {_format_cli_error(e)}")


def cmd_server_whoami(config_path: Optional[str] = None):
    """Check current authentication status and user info."""
    config = load_config(config_path)

    if not config.server_url:
        print("[ERROR] No server URL configured. Run 'embyd login' first.")
        return

    from app.core.auth import get_token
    from app.core.emby_api import EmbyApiClient, EmbyAuthError

    token = get_token(config)
    if not token:
        print("[WARNING] No access token found. Run 'embyd login' to authenticate.")
        return

    client = EmbyApiClient(config.server_url, token)
    try:
        user = client.get_user()
        print(f"[OK] Authenticated")
        print(f"     Username:    {user.get('Name', '?')}")
        print(f"     User ID:     {user.get('Id', '?')}")
        print(f"     Policy:      Download={user.get('Policy', {}).get('EnableDownload', '?')}")
        print(f"                EnableMediaConversion={user.get('Policy', {}).get('EnableMediaConversion', '?')}")
        print(f"     Server:      {config.server_url}")
    except EmbyAuthError as e:
        if "401" in str(e):
            print(f"[FAIL] Token is invalid or expired. Run 'embyd login' again.")
        elif "403" in str(e):
            print(f"[FAIL] Token is valid but account lacks permissions.")
        else:
            print(f"[FAIL] {_format_cli_error(e)}")
    except Exception as e:
        print(f"[FAIL] {_format_cli_error(e)}")
    finally:
        client.close()
