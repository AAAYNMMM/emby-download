# Stage 11: Backend HTTP + WebSocket server.
# Runs in a separate process, managed by the GUI.

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional, Set

import aiohttp
from aiohttp import web

from app.backend.download_manager import BackendDownloadManager
from app.backend.api import setup_routes
from app.config.settings import load_config
from app.utils.logger import setup_logger, get_logger

_logger = get_logger()

DEFAULT_PORT = 19999
PID_FILE = "embyd_backend.pid"
PORT_FILE = "embyd_backend.port"


class BackendServer:
    """EmbyD backend server: HTTP API + WebSocket events."""

    def __init__(self, port: int = DEFAULT_PORT, config_path: Optional[str] = None):
        self._port = port
        self._config = load_config(config_path)
        self._manager = BackendDownloadManager(config=self._config)
        self._ws_clients: Set[web.WebSocketResponse] = set()
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None

    def _event_callback(self, event_type: str, data: dict):
        """Broadcast event to all connected WebSocket clients."""
        message = json.dumps({"type": event_type, **data}, default=str)
        dead = set()
        for ws in self._ws_clients:
            try:
                asyncio.ensure_future(ws.send_str(message))
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    async def _ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.add(ws)
        _logger.info(f"WebSocket client connected ({len(self._ws_clients)} total)")

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _logger.error(f"WebSocket error: {ws.exception()}")
        finally:
            self._ws_clients.discard(ws)
            _logger.info(f"WebSocket client disconnected ({len(self._ws_clients)} total)")
        return ws

    async def start(self):
        """Start the HTTP + WebSocket server."""
        self._app = web.Application()
        self._manager.set_event_callback(self._event_callback)
        setup_routes(self._app, self._manager)

        # Add WebSocket route
        self._app.router.add_get("/ws", self._ws_handler)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self._port)
        await site.start()

        # Write PID and port files
        pid = os.getpid()
        app_dir = Path.cwd()
        (app_dir / PID_FILE).write_text(str(pid))
        (app_dir / PORT_FILE).write_text(str(self._port))

        _logger.info(f"Backend server started on http://127.0.0.1:{self._port}")
        _logger.info(f"PID: {pid}")

    async def stop(self):
        """Stop the server and clean up."""
        _logger.info("Shutting down backend server...")

        # Close all WebSocket connections
        for ws in set(self._ws_clients):
            await ws.close(code=1000, message=b"Server shutting down")
        self._ws_clients.clear()

        # Shutdown download manager
        await self._manager.shutdown()

        # Clean up runner
        if self._runner:
            await self._runner.cleanup()

        # Remove PID and port files
        app_dir = Path.cwd()
        for f in (PID_FILE, PORT_FILE):
            try:
                (app_dir / f).unlink(missing_ok=True)
            except Exception:
                pass

        _logger.info("Backend server stopped.")


def find_available_port(start: int = DEFAULT_PORT) -> int:
    """Find an available port starting from start."""
    import socket
    port = start
    for _ in range(100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start  # fallback


def main():
    """Entry point for standalone backend process."""
    import argparse
    parser = argparse.ArgumentParser(description="EmbyD Backend Server")
    parser.add_argument("--port", type=int, default=None, help="HTTP server port")
    parser.add_argument("--config", "-c", type=str, default=None, help="Config file path")
    args = parser.parse_args()

    setup_logger(level="INFO")

    port = args.port or find_available_port()

    server = BackendServer(port=port, config_path=args.config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(server.start())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(server.stop())
        loop.close()


if __name__ == "__main__":
    main()
