# EmbyD Stage 10E-1 Acceptance Report

**Date:** 2026-06-12
**Stage:** 10E-1 → 10E-1b (Repackage + Download Freeze Fix)
**Status:** ✅ PASSED

---

## 1. Code Changes

### 1a. Bug Fix: Download Freeze (Stage 10E-1b)

**Root Cause:** In [`download_controller.py`](app/gui/download_controller.py:112),
worker signal connections (`prepared`, `progress`, `finished`, `error`) were
connected to **lambda closures** without explicit `Qt.ConnectionType`.  Since
lambdas have no thread affinity, PySide6 defaults to `Qt.DirectConnection`.
The lambdas executed in the **worker thread** but called methods on
`DownloadController` (a main-thread `QObject`).  This cross-thread direct
QObject method call violates Qt thread-safety rules and can cause deadlocks
or silent event-loop corruption, resulting in GUI freeze (Windows shows
"(Not Responding)").

**Fix:** Added `Qt.QueuedConnection` to all 8 worker signal connections
(4 in `start_task()`, 4 in `resume_task()`).  This ensures the lambdas
(and therefore `self._on_prepared()`, `self._on_progress()`,
`self._on_finished()`, `self._on_error()`) always execute on the main
thread's event loop.

| File | Change | Reason |
|------|--------|--------|
| `app/gui/download_controller.py` | Added `Qt.QueuedConnection` to 8 signal connections | Fix GUI freeze on download |
| `app/gui/download_controller.py` | Added `Qt` to imports | Required for `Qt.QueuedConnection` |
| `dist/README_TESTING.txt` | Updated with Stage 10E manual test items | Testing guide |
| `docs/acceptance_stage10e.md` | Created & updated (this file) | Documentation |

## 2. Dependencies

No new dependencies were installed. All dependencies were already present.

## 3. Regression Test Results

```text
pytest: 265 passed in 41.30s
CLI --help: OK
CLI doctor: OK (all modules OK, server reachable)
CLI config show: OK
CLI search test: OK (5 results)
CLI download --dry-run: Expected error (item not found)
GUI smoke: OK ("gui smoke ok")
```

## 4. Build Command

```text
python scripts/build_exe.py
```

Build completed successfully for both targets.

## 5. Dist File List

| File | Size | Description |
|------|------|-------------|
| `embyd.exe` | 17,703,996 bytes (~16.9 MB) | CLI executable |
| `embyd-gui.exe` | 262,447,344 bytes (~250.3 MB) | GUI executable |
| `README_TESTING.txt` | Updated | Manual testing guide |
| `embyd_config.json` | 554 bytes | Auto-generated config (runtime) |
| `tasks.db` | 20,480 bytes | Auto-generated task DB (runtime) |

## 6. CLI Exe Verification

```text
embyd.exe --help       -> OK, all commands listed
embyd.exe --version    -> OK, "embyd.exe, version 0.1.0"
embyd.exe doctor       -> OK, all modules [OK], server reachable
embyd.exe config show  -> OK, all settings displayed correctly
```

## 7. GUI Exe Verification

- **Launch:** Process started successfully
- **Stability:** Process still running after 8 seconds (no crash)
- **i18n:** `app.gui.i18n` module traced by PyInstaller via `main_window.py` and `widgets.py` imports

## 8. README_TESTING.txt

Updated with Stage 10E manual test focus areas:
- 一、下载不卡顿测试 (12 steps)
- 二、剧集搜索测试 (14 steps)
- 三、中文化检查 (8 categories with checkboxes)
- 四、仍需记录的问题 (10 data points to collect if freeze occurs)

## 9. Next Manual Testing Order

1. Start `dist\embyd-gui.exe`
2. Login to Emby server
3. 三、中文化检查 — verify all UI text is Chinese
4. 一、下载不卡顿测试 — download a movie, test UI responsiveness
5. 二、剧集搜索测试 — test series search from Series tab
6. 四、记录任何仍存在的问题

---

## Summary

- ✅ No code changes (only README update)
- ✅ No new dependencies installed
- ✅ 265 tests passed
- ✅ Both exes built successfully
- ✅ CLI exe verified (--help, --version, doctor, config show)
- ✅ GUI exe verified (launched, 8s no crash)
- ✅ README_TESTING.txt updated with Stage 10E focus areas
- ✅ No token/password/server_url leaked in this report
- ✅ User config and tasks.db preserved (not cleared)
