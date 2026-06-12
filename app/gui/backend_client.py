# Stage 11: GUI-side backend client.
# Launches the backend process and provides HTTP + WebSocket communication.

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional, Callable

import aiohttp
from PySide6.QtCore import QObject, QThread, Signal, QTimer

from app.config.settings import load_config, get_app_dir

BACKEND_PORT_FILE = "embyd_backend.port"
BACKEND_PID_FILE = "embyd_backend.pid"

DEFAULT_BACKEND_PORT = 19999


class BackendProcess(QObject):
    """Launches and manages the backend subprocess."""

    started = Signal(int)   # port
    error = Signal(str)
    log = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._port: Optional[int] = None

    @property
    def port(self) -> Optional[int]:
        return self._port

    def start(self, config_path: Optional[str] = None):
        """Launch the backend Python process."""
        try:
            # Try importing to ensure the backend module is available
            from app.backend.server import find_available_port
            port = find_available_port(DEFAULT_BACKEND_PORT)

            if getattr(sys, "frozen", False):
                # In PyInstaller build, use the sibling embyd.exe (CLI) as backend
                exe_dir = Path(sys.executable).parent
                cli_exe = exe_dir / "embyd.exe"
                if cli_exe.exists():
                    args = [str(cli_exe), "backend", "--port", str(port)]
                else:
                    args = [str(Path(sys.executable)), "backend", "--port", str(port)]
            else:
                args = [sys.executable, "-m", "app.backend.server", "--port", str(port)]

            if config_path:
                args += ["--config", config_path]

            import subprocess
            app_dir = str(get_app_dir())

            self._process = subprocess.Popen(
                args,
                cwd=app_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                encoding="utf-8",
                errors="replace",
            )

            # Wait for backend to be ready
            base_url = f"http://127.0.0.1:{port}"
            for i in range(50):  # up to ~5 seconds
                time.sleep(0.1)
                if self._process.poll() is not None:
                    # Process exited early
                    stderr = self._process.stderr.read() if self._process.stderr else ""
                    self.error.emit(f"Backend process exited: {stderr[:500]}")
                    return
                try:
                    import urllib.request
                    urllib.request.urlopen(f"{base_url}/api/health", timeout=1)
                    self._port = port
                    self.started.emit(port)
                    self.log.emit(f"Backend started on port {port}")
                    return
                except Exception:
                    continue

            self.error.emit("Backend process did not start in time")

        except Exception as e:
            self.error.emit(f"Failed to start backend: {e}")

    def stop(self):
        """Stop the backend process."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
            self._port = None

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None


class BackendWebSocket(QObject):
    """Manages WebSocket connection to backend. Runs in a QThread."""

    connected = Signal()
    disconnected = Signal()
    event_received = Signal(str, object)  # event_type, data dict
    connection_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port: Optional[int] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional['_WsWorker'] = None

    def start(self, port: int):
        """Start WebSocket connection in a background thread."""
        self._port = port
        self._running = True

        self._thread = QThread()
        self._worker = _WsWorker(port)
        self._worker.moveToThread(self._thread)

        self._worker.connected.connect(self.connected)
        self._worker.disconnected.connect(self.disconnected)
        self._worker.event_received.connect(self.event_received)
        self._worker.connection_error.connect(self.connection_error)

        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def stop(self):
        """Stop WebSocket connection."""
        self._running = False
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None


class _WsWorker(QObject):
    """Worker that runs the WebSocket event loop in a dedicated thread."""
    connected = Signal()
    disconnected = Signal()
    event_received = Signal(str, object)
    connection_error = Signal(str)

    def __init__(self, port: int):
        super().__init__()
        self._port = port
        self._running = False

    def run(self):
        self._running = True
        asyncio.run(self._connect_and_listen())

    def stop(self):
        self._running = False

    async def _connect_and_listen(self):
        import aiohttp
        url = f"http://127.0.0.1:{self._port}/ws"
        session = aiohttp.ClientSession()

        while self._running:
            try:
                async with session.ws_connect(url) as ws:
                    self.connected.emit()
                    async for msg in ws:
                        if not self._running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                event_type = data.pop("type", "unknown")
                                self.event_received.emit(event_type, data)
                            except json.JSONDecodeError:
                                pass
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except aiohttp.ClientConnectorError as e:
                self.connection_error.emit(f"Cannot connect to backend: {e}")
            except Exception as e:
                self.connection_error.emit(f"WebSocket error: {e}")

            # Reconnect delay
            if self._running:
                await asyncio.sleep(1)

        self.disconnected.emit()
        await session.close()


class BackendClient(QObject):
    """High-level backend client for the GUI.

    Provides:
    - REST API methods (async via QThread)
    - WebSocket event reception (bridged to Qt signals)
    - Backend process lifecycle
    """

    # Mirrors the old DownloadController signals
    progress = Signal(str, object, object, float)    # task_id, downloaded, total, speed
    status_changed = Signal(str, str)                 # task_id, status
    error = Signal(str, str)                          # task_id, message
    finished_signal = Signal(str, str)                # task_id, output_path
    task_created = Signal(object)                     # task dict
    task_deleted = Signal(str)                        # task_id
    log_message = Signal(str, str)                    # level, message
    backend_ready = Signal()
    backend_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = BackendProcess()
        self._ws = BackendWebSocket()
        self._port: Optional[int] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._ready = False

        # Wire process signals
        self._process.started.connect(self._on_process_started)
        self._process.error.connect(self._on_process_error)

        # Wire WebSocket signals
        self._ws.connected.connect(self._on_ws_connected)
        self._ws.event_received.connect(self._on_ws_event)
        self._ws.connection_error.connect(self._on_ws_error)

    @property
    def port(self) -> Optional[int]:
        return self._port

    @property
    def is_ready(self) -> bool:
        return self._ready

    def start(self, config_path: Optional[str] = None):
        """Launch the backend process. Backend will auto-start WebSocket."""
        self._process.start(config_path)

    def stop(self):
        """Stop WebSocket, backend process, and clean up."""
        self._ready = False
        self._ws.stop()
        self._process.stop()

    def _on_process_started(self, port: int):
        self._port = port
        self._ws.start(port)

    def _on_process_error(self, error_msg: str):
        self._ready = False
        self.backend_error.emit(error_msg)
        self.log_message.emit("ERROR", f"Backend error: {error_msg}")

    def _on_ws_connected(self):
        self._ready = True
        self.backend_ready.emit()
        self.log_message.emit("INFO", "Connected to download backend")

    def _on_ws_error(self, error_msg: str):
        self.log_message.emit("ERROR", f"WebSocket: {error_msg}")

    def _on_ws_event(self, event_type: str, data: dict):
        """Route WebSocket events to appropriate signals."""
        if event_type == "progress":
            task_id = data.get("task_id", "")
            downloaded = data.get("downloaded", 0)
            total = data.get("total")
            speed = data.get("speed", 0.0)
            self.progress.emit(task_id, downloaded, total, speed)
        elif event_type == "status_changed":
            task_id = data.get("task_id", "")
            status = data.get("status", "")
            self.status_changed.emit(task_id, status)
        elif event_type == "error":
            task_id = data.get("task_id", "")
            message = data.get("message", "")
            self.error.emit(task_id, message)
        elif event_type == "finished":
            task_id = data.get("task_id", "")
            output_path = data.get("output_path", "")
            self.finished_signal.emit(task_id, output_path)
        elif event_type == "task_created":
            self.task_created.emit(data)
        elif event_type == "task_deleted":
            self.task_deleted.emit(data.get("task_id", ""))
        elif event_type == "log":
            self.log_message.emit(data.get("level", "INFO"), data.get("message", ""))

    # ---- HTTP API helpers (run in thread) ----

    async def _http_get(self, path: str) -> dict:
        import aiohttp
        if not self._port:
            return {"error": "Backend not started"}
        url = f"http://127.0.0.1:{self._port}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.json()

    async def _http_post(self, path: str, data: dict = None) -> dict:
        import aiohttp
        if not self._port:
            return {"error": "Backend not started"}
        url = f"http://127.0.0.1:{self._port}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data or {}) as resp:
                try:
                    return await resp.json()
                except Exception:
                    return {"status": "error", "code": resp.status}

    async def _http_delete(self, path: str) -> dict:
        import aiohttp
        if not self._port:
            return {"error": "Backend not started"}
        url = f"http://127.0.0.1:{self._port}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.delete(url) as resp:
                try:
                    return await resp.json()
                except Exception:
                    return {"status": "error", "code": resp.status}

    # ---- Public async API ----

    async def fetch_tasks(self, status_filter: Optional[str] = None, limit: int = 200) -> list:
        params = f"limit={limit}"
        if status_filter:
            params += f"&status={status_filter}"
        return await self._http_get(f"/api/tasks?{params}")

    async def fetch_stats(self) -> dict:
        return await self._http_get("/api/tasks/stats")

    async def create_task(self, **kwargs) -> dict:
        return await self._http_post("/api/tasks", kwargs)

    async def start_task(self, task_id: str, download_dir: str) -> dict:
        return await self._http_post(f"/api/tasks/{task_id}/start", {"download_dir": download_dir})

    async def batch_start(self, task_ids: list, download_dir: str) -> dict:
        return await self._http_post("/api/tasks/batch-start", {"task_ids": task_ids, "download_dir": download_dir})

    async def pause_task(self, task_id: str) -> dict:
        return await self._http_post(f"/api/tasks/{task_id}/pause")

    async def resume_task(self, task_id: str, download_dir: str) -> dict:
        return await self._http_post(f"/api/tasks/{task_id}/resume", {"download_dir": download_dir})

    async def cancel_task(self, task_id: str) -> dict:
        return await self._http_post(f"/api/tasks/{task_id}/cancel")

    async def delete_task(self, task_id: str) -> dict:
        return await self._http_delete(f"/api/tasks/{task_id}")
