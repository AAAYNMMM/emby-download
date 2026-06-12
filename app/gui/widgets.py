"""
Custom widgets for EmbyD GUI.

- LogWidget: Read-only log output area with color-coded messages.
- StatusBarWidget: Custom status bar showing server/user/connection.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QColor, QAction
from PySide6.QtWidgets import (
    QTextEdit, QWidget, QHBoxLayout, QLabel,
    QMenu, QFileDialog,
)
from html import escape

from app.utils.redaction import redact_sensitive
from app.gui.i18n import MENU_EXPORT_LOG, MENU_CLEAR_LOG, STATUS_NOT_CONNECTED


class LogWidget(QTextEdit):
    """Read-only log output area with color-coded messages."""

    MAX_LINES = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(self.MAX_LINES)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 11px;
                border: 1px solid #333;
            }
        """)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        export_action = QAction(MENU_EXPORT_LOG, self)
        export_action.triggered.connect(self._export_log)
        menu.addAction(export_action)
        clear_action = QAction(MENU_CLEAR_LOG, self)
        clear_action.triggered.connect(self.clear)
        menu.addAction(clear_action)
        menu.exec(self.mapToGlobal(pos))

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Log", "embyd_log.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.toPlainText())
                self.append_log("OK", f"Log exported to {path}")
            except Exception as e:
                self.append_log("ERROR", f"Failed to export log: {e}")

    def append_log(self, level: str, message: str):
        color_map = {
            "OK": "#4ec9b0",
            "INFO": "#9cdcfe",
            "WARNING": "#ce9178",
            "ERROR": "#f44747",
            "DEBUG": "#808080",
        }
        color = color_map.get(level, "#d4d4d4")
        timestamp = ""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        safe_message = escape(redact_sensitive(message), quote=False)
        safe_level = escape(redact_sensitive(level), quote=False)
        html = f'<span style="color: {color};">[{timestamp}] [{safe_level}] {safe_message}</span><br>'
        self.insertHtml(html)
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.ensureCursorVisible()


class StatusBarWidget(QWidget):
    """Custom status bar showing server URL, username, connection status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)

        self.server_label = QLabel("服务器: --")
        self.server_label.setStyleSheet("color: #888; padding: 2px 8px;")
        self.user_label = QLabel("用户: --")
        self.user_label.setStyleSheet("color: #888; padding: 2px 8px;")
        self.status_label = QLabel(STATUS_NOT_CONNECTED)
        self.status_label.setStyleSheet("color: #f44747; padding: 2px 8px; font-weight: bold;")

        layout.addWidget(self.server_label)
        layout.addWidget(self.user_label)
        layout.addStretch()
        layout.addWidget(self.status_label)

        self.setStyleSheet("""
            StatusBarWidget {
                background-color: #252526;
                border-top: 1px solid #333;
            }
        """)

    def set_server(self, url: str):
        self.server_label.setText(f"服务器: {url}")

    def set_user(self, username: str):
        self.user_label.setText(f"用户: {username}")

    def set_status(self, status: str, ok: bool = True):
        color = "#4ec9b0" if ok else "#f44747"
        self.status_label.setStyleSheet(f"color: {color}; padding: 2px 8px; font-weight: bold;")
        self.status_label.setText(status)
