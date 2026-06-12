# EmbyD Manual Test Guide

Test against a real Emby server to verify all functionality.

## Prerequisites
- A running Emby server (e.g., http://192.168.1.100:8096)
- An Emby account with download permissions (ask admin if unsure)
- An Emby account WITHOUT download permissions (for testing error handling)

## Test Steps

### 1. Version & Help
```powershell
# Verify CLI is accessible
embyd.exe --version
# Expected: embyd, version 0.1.0

embyd.exe --help
# Expected: Lists all commands (login, libraries, search, info, download, tasks, resume, config, doctor, server)

embyd.exe config show
# Expected: Shows configuration file path in the same directory as the exe/source cwd
```

### 2. Doctor (Diagnostic)
```powershell
embyd.exe doctor
# Expected: Shows environment info, module status, configuration, token status, server connection
# Common issues:
# - Config file: Should be in the software current directory
# - Token: Should be present after login
# - Server connection: Shows server name + version if reachable
```

### 3. Login
```powershell
embyd.exe login --server http://192.168.1.100:8096 --username my_username
# Prompts for password interactively
# Expected: "[OK] Successfully logged in as 'my_username' (User ID: abc123)"
# Token saved to encrypted config file.

# Test server ping after login:
embyd.exe server ping
# Expected: Shows server name and version

# Test whoami:
embyd.exe server whoami
# Expected: Shows username, user ID, download policy

# Failure cases:
# - Wrong password: "[ERROR] Authentication failed: Unauthorized..."
# - Wrong server URL: "[ERROR] Login failed: Connection refused..."
# - No network: "[ERROR] Login failed: Connection failed..."
```

### 4. Libraries
```powershell
embyd.exe libraries
# Expected: Table of libraries with ID, Name, Type
# Example:
#   ID         Name                                      Type
#   ---------------------------------------------------------------
#   abc12345   电影库                                    movies
#   def67890   剧集库                                    tvshows

# Failure cases:
# - No libraries: "No media libraries found."
# - Token expired: "[ERROR] Failed to fetch libraries: Authentication failed..."
```

### 5. Search
```powershell
embyd.exe search "Inception"
# Expected: Table of matching movies/episodes with ID, Title, Year/episode code, Type

embyd.exe search "Inception" --limit 5
# Expected: Limited to 5 results

embyd.exe search "NonExistentMovieXYZ"
# Expected: 'No results found for "NonExistentMovieXYZ".'
```

### 6. Info (PlaybackInfo & Download Capability)
```powershell
# Get a movie or episode ID from search first
embyd.exe search "Inception"
# Copy the ID from results

embyd.exe info <item_id>
# Expected:
# - Media info: title, year, runtime, genres
# - Media Sources list: container, size, duration, protocol
# - Download status: [OK] or [X] with method
# - Summary with best source and download capability

embyd.exe info <item_id> --verbose
# Expected: Additional MediaSource details (bitrate, stream flags, path)
```

### 7. Download
```powershell
# Dry-run first (no actual download):
embyd.exe download <item_id> --dry-run --dir C:\Users\YourName\Videos\EmbyD
# Expected: Shows what WOULD be downloaded without downloading
# - Title, sources, container, size, duration
# - Download method (direct/stream)
# - Status (downloadable or not)
# - Output file path
# Note: "[DRY-RUN] No files were downloaded."

# Real download:
embyd.exe download <item_id> --dir C:\Users\YourName\Videos\EmbyD
# Expected: Progress bar, "[OK] Download complete: C:\Users\YourName\Videos\EmbyD\Movie Name (2024).mkv"

# Download with metadata:
embyd.exe download <item_id> --with-all
# Expected: Download movie + automatically save NFO + subtitles

# Download with specific subtitles:
embyd.exe download <item_id> --with-subtitles --subtitle-lang chi,eng
# Expected: Download only Chinese and English subtitles
```

### 8. Download Error Handling
```powershell
# Test with item that has no download permission:
embyd.exe download <no_download_item_id>
# Expected: "[ERROR] Cannot download this item. Reason: ..."

# Test with non-existent item:
embyd.exe download "non_existent_id"
# Expected: "[ERROR] Failed to download item... Resource not found."

# Test with --dry-run on non-existent item:
embyd.exe download "non_existent_id" --dry-run
# Expected: "[ERROR] Failed to analyze item... Resource not found."
```

### 9. Tasks & Resume
```powershell
# List all tasks:
embyd.exe tasks
# Expected: Table of download tasks with ID, Title, Size, Progress, Status

# List only downloading tasks:
embyd.exe tasks --status downloading
# Expected: Only tasks in 'downloading' status

# Resume a failed task:
embyd.exe resume <task_id>
# Expected: Resumes download from last saved position

# List tasks needing resume:
embyd.exe resume
# Expected: Lists all failed/paused tasks
```

### 9B. GUI Pause / Continue
```powershell
python -m app.gui.app
# Login, choose a download directory, Preview an item, then click Download.
# Expected: Progress updates while the GUI remains responsive.
# Click Pause.
# Expected: Task status becomes paused and a .part file remains.
# Click Continue.
# Expected: Download resumes from the partial file.
```

### 10. Server Commands
```powershell
embyd.exe server ping
# Expected: Shows server name + version

embyd.exe server whoami
# Expected: Shows authenticated user info + download policy
```

### 11. GUI From Source
```powershell
python -m app.gui.app
# Expected: Main window opens without traceback.

python -c "from app.gui.widgets import LogWidget; print('LogWidget import ok')"
# Expected: LogWidget import ok

python -c "from app.gui.workers import LoginWorker, PingWorker, WhoamiWorker, SearchWorker, DryRunWorker, TaskListWorker; print('workers import ok')"
# Expected: workers import ok
```

GUI workflow:
- Login tab: enter server URL, username, password, then click Login.
- Click Ping to confirm server reachability.
- Search tab: search a known movie title.
- Preview tab: double-click a search result or enter an item ID, then click Preview.
- Download: only click Download after Preview says the item is downloadable. Test Pause and Continue.
- Episodes tab: search a series, select multiple Episode rows, then click Download Selected.
- Tasks tab: click Refresh and confirm empty/completed/paused/failed lists render normally.

### 12. Packaged EXE Smoke Test
```powershell
python scripts\build_exe.py

dist\embyd.exe --help
dist\embyd.exe --version
dist\embyd.exe doctor

dist\embyd-gui.exe
# Expected: GUI opens without a PyInstaller "Failed to execute script" dialog.
```

If `dist\embyd-gui.exe` does not open, run the source GUI command above to see the Python traceback, then rebuild with `python scripts\build_exe.py`.

## Common Error Messages & Solutions

| Error | Likely Cause | Solution |
|---|---|---|
| "Connection refused" | Server not running or wrong port | Check server URL, ensure Emby is running |
| "Connection failed" | Network issue | Check network connectivity |
| "Request timed out" | Server slow or firewall | Increase timeout, check firewall |
| "Unauthorized (401)" | Token expired/invalid | Run `embyd login` again |
| "Forbidden (403)" | No download permission | Ask admin to enable download for your account |
| "Resource not found (404)" | Item deleted or wrong ID | Verify item ID via `embyd search` |
| "Server error (5xx)" | Server-side issue | Try again later, check Emby server logs |
| "No media sources found" | Item has no playable media | Verify item is a movie, not a collection |
| "SSL error" | HTTPS certificate issue | Use http:// or fix certificate |

## Permission Test Matrix

| Account Type | Login | Libraries | Search | Info | Download |
|---|---|---|---|---|---|
| Admin (full access) | OK | OK | OK | OK | OK |
| User with download | OK | OK | OK | OK | OK |
| User no download | OK | OK | OK | OK | [FORBIDDEN] |
| Invalid password | [FAIL] | - | - | - | - |
| Expired token | - | [FAIL] | [FAIL] | [FAIL] | [FAIL] |
