# EmbyD Architecture

## Overview

EmbyD is a layered application designed to download media files from Emby servers.

```
+---------------------------------------------+
|                  GUI (PySide6)               |
|              (Presentation Layer)            |
+---------------------------------------------+
|                  Downloader                   |
|    (direct_download / stream_download        |
|      / range_downloader)                     |
+---------------------------------------------+
|                  Core                         |
|  (emby_api_client / auth / playback_info     |
|   / naming / download_preview)               |
+---------------------------------------------+
|       Storage / Config / Logger              |
|     (SQLite / JSON / keyring / logging)      |
+---------------------------------------------+
```

**Note:** CLI control layer has been removed. EmbyD is now GUI-only.

## Architecture Decisions

### Why Python?
- Fastest time to MVP
- Rich ecosystem for HTTP, async, and GUI
- Easy debugging and REPL testing

### Async vs Sync
- Core API calls: sync (requests) for simplicity
- Download: async (aiohttp) for non-blocking I/O
- GUI: QThread workers for responsive UI

## Module Dependencies

```
gui/app.py
  +-- gui/main_window.py
  |     +-- config/settings.py
  |     +-- config/schema.py
  |     +-- core/auth.py
  |     +-- core/emby_api.py
  |     +-- core/playback_info.py
  |     +-- core/download_capability.py
  |     +-- gui/workers.py
  |     +-- gui/download_controller.py
  |     +-- downloader/task_store.py
  |     +-- utils/logger.py
  +-- utils/logger.py
```

## Data Flow

### Login Flow
```
User Input -> auth.authenticate() -> POST /Users/AuthenticateByName
  -> Receive AccessToken -> encrypt_token() -> save to config
```

### Download Flow
```
User Input (item_id)
  -> emby_api.get_item() -> Get movie metadata
  -> emby_api.get_playback_info() -> Get MediaSources
  -> download_capability.check() -> Determine best method
  -> download_controller.start_download() -> Create DB task
  -> range_downloader.download() -> HTTP Range requests
  -> progress_callback() -> Update DB + GUI progress
  -> Complete -> rename .part -> Final file
```

## Current Status

GUI-only mode. CLI removed in Stage 12g.
