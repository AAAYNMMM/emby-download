"""
EmbyD MainWindow - PySide6 GUI main window.

Tabs:
- Login / Config (登录 / 配置)
- Search (搜索)
- Preview (预览)
- Series Browser (剧集)
- Tasks (任务)
"""

import time as _time
from typing import Optional
import os as _os
from pathlib import Path

import time as _time
from typing import Optional
import os as _os
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
    QMessageBox, QComboBox, QGridLayout, QFileDialog,
    QMenu, QAbstractItemView, QSplitter, QListWidget,
    QListWidgetItem, QStackedWidget, QProgressBar, QTextEdit,
)
from PySide6.QtGui import QAction, QColor

from app.config.settings import load_config, save_config, get_config_path_display
from app.config.schema import EmbyConfig
from app.core.auth import get_token
from app.core.download_capability import get_method_label

from app.gui.widgets import LogWidget, StatusBarWidget
from app.gui.workers import (
    LoginWorker, PingWorker, WhoamiWorker,
    SearchWorker, DryRunWorker, TaskListWorker,
    DownloadItemWorker, SeriesSeasonsWorker, SeasonEpisodesWorker,
    SeriesSearchWorker, StartTasksWorker, MediaSourcesWorker,
)
from app.gui.download_controller import DownloadController
from app.downloader.task_store import (
    get_task, update_task, list_tasks as db_list_tasks,
    delete_task as db_delete_task, delete_tasks as db_delete_tasks,
    count_tasks,
)
from app.utils.formatting import (
    format_bytes, format_speed_gui, format_eta, format_progress_pct,
    format_updated_at, compute_eta_seconds,
)
from app.utils.timing import timed_step, timing_event
from app.gui.i18n import (
    TAB_LOGIN, TAB_SEARCH, TAB_PREVIEW, TAB_SERIES, TAB_TASKS,
    GRP_SERVER, LBL_SERVER_URL, LBL_USERNAME, LBL_PASSWORD,
    BTN_LOGIN, BTN_PING, GRP_DOWNLOAD_DIR, BTN_BROWSE, BTN_SAVE_DIR,
    PLACEHOLDER_SERVER, PLACEHOLDER_USERNAME, PLACEHOLDER_PASSWORD,
    PLACEHOLDER_DOWNLOAD_DIR, PLACEHOLDER_SEARCH, LBL_LIMIT, BTN_SEARCH,
    COL_ID, COL_TITLE, COL_INFO, COL_TYPE,
    LBL_ITEM_ID, BTN_PREVIEW, BTN_DOWNLOAD, GRP_PREVIEW,
    LBL_PREVIEW_TITLE, LBL_PREVIEW_SIZE, LBL_PREVIEW_DURATION,
    LBL_PREVIEW_CONTAINER, LBL_PREVIEW_PROTOCOL, LBL_PREVIEW_METHOD,
    LBL_PREVIEW_STATUS, LBL_PREVIEW_REASON, LBL_PREVIEW_OUTPUT,
    LBL_SERIES_TITLE, LBL_SERIES_HINT, LBL_SEASONS,
    BTN_BACK_TO_SEASONS, BTN_REFRESH_SEASONS, BTN_REFRESH_EPISODES,
    BTN_SELECT_ALL_VISIBLE, BTN_CLEAR_VISIBLE,
    BTN_SELECT_SEASON, BTN_CLEAR_SEASON,
    BTN_DOWNLOAD_SELECTED, BTN_CREATING_TASKS,
    PLACEHOLDER_SERIES_SEARCH, BTN_SERIES_SEARCH,
    COL_SERIES_NAME, COL_SERIES_YEAR, COL_SERIES_ID,
    LBL_FILTER, BTN_REFRESH_TASKS,
    BTN_START_SELECTED, BTN_PAUSE_SELECTED, BTN_RESUME_SELECTED, BTN_CANCEL_SELECTED,
    BTN_DELETE_SELECTED, BTN_OPEN_FOLDER, BTN_SHOW_ERROR,
    BTN_CLEAN_COMPLETED, PLACEHOLDER_TASK_SEARCH,
    COL_TASK_ID, COL_TASK_TITLE, COL_TASK_ITEM_ID, COL_TASK_STATUS,
    COL_TASK_PROGRESS, COL_TASK_DOWNLOADED, COL_TASK_TOTAL,
    COL_TASK_SPEED, COL_TASK_ETA, COL_TASK_UPDATED,
    COL_TASK_SAVE_PATH, COL_TASK_LAST_ERROR,
    COL_TASK10F_TITLE, COL_TASK10F_STATUS, COL_TASK10F_PROGRESS,
    COL_TASK10F_SIZE, COL_TASK10F_SPEED, COL_TASK10F_ETA, COL_TASK10F_UPDATED,
    FILTER_ALL, FILTER_PENDING, FILTER_PREPARING, FILTER_DOWNLOADING, FILTER_PAUSED,
    FILTER_COMPLETED, FILTER_FAILED, FILTER_CANCELLED,
    status_text,
    SIDEBAR_ALL, SIDEBAR_DOWNLOADING, SIDEBAR_PREPARING, SIDEBAR_PENDING, SIDEBAR_PAUSED,
    SIDEBAR_COMPLETED, SIDEBAR_FAILED, SIDEBAR_CANCELLED,
    DETAIL_TAB_OVERVIEW, DETAIL_TAB_ERROR, DETAIL_TAB_LOG,
    DETAIL_LBL_TITLE, DETAIL_LBL_STATUS, DETAIL_LBL_PROGRESS,
    DETAIL_LBL_SAVE_PATH, DETAIL_LBL_FILENAME,
    DETAIL_LBL_TASK_ID, DETAIL_LBL_ITEM_ID, DETAIL_LBL_TYPE,
    DETAIL_LBL_SERIES_INFO, DETAIL_LBL_CREATED, DETAIL_LBL_UPDATED,
    DETAIL_LBL_NO_ERROR, DETAIL_LBL_UNKNOWN,
    EMPTY_TASKS_TITLE, EMPTY_TASKS_HINT, EMPTY_TASKS_BTN,
    DLG_DELETE_TITLE, DLG_DELETE_MSG, DLG_DELETE_ACTIVE, DLG_DELETED,
    DLG_CLEAN_TITLE, DLG_CLEAN_MSG, DLG_CLEAN_RESULT, DLG_CLEAN_NONE,
    CONN_NOT_CONFIGURED, CONN_NOT_VERIFIED, CONN_SERVER_REACHABLE,
    CONN_TOKEN_EXPIRED,
    MENU_PAUSE, MENU_RESUME, MENU_CANCEL, MENU_DELETE, MENU_OPEN_FOLDER,
    MENU_SHOW_ERROR, MENU_REFRESH, MENU_START, MENU_COPY_TITLE, MENU_COPY_PATH,
    DLG_MISSING_FIELDS, DLG_MISSING_FIELDS_MSG,
    DLG_NOT_LOGGED_IN, DLG_NOT_LOGGED_IN_MSG,
    DLG_MISSING_DIR, DLG_MISSING_DIR_MSG,
    DLG_MISSING_SERVER, DLG_MISSING_SERVER_MSG,
    DLG_NO_SELECTION, DLG_NO_SELECTION_MSG,
    DLG_SELECT_ONE, DLG_NOT_FOUND, DLG_NOT_FOUND_MSG,
    DLG_NO_PATH, DLG_NO_PATH_MSG,
    DLG_PATH_NOT_FOUND, DLG_PATH_NOT_FOUND_MSG,
    DLG_NO_ERROR, DLG_NO_ERROR_MSG,
    DLG_UNKNOWN_TYPE, DLG_UNKNOWN_TYPE_MSG,
    DLG_ACTIVE_DOWNLOADS, DLG_ACTIVE_DOWNLOADS_MSG,
    DLG_RESUME_CANCELLED, DLG_RESUME_CANCELLED_MSG,
    DLG_NO_EPISODES, DLG_NO_EPISODES_MSG,
    DLG_NO_SERIES_RESULTS, DLG_EMPTY_SERIES_SEARCH,
    DLG_OPEN_FOLDER_ERROR,
    STATUS_NOT_CONNECTED, STATUS_CONNECTED,
    WINDOW_TITLE, STR_LOADING, STR_STARTING, STR_UNKNOWN,
    STR_NO_SERIES_LOADED, STR_DOUBLE_CLICK_HINT,
    STR_LOADING_SEASONS, STR_LOADING_EPISODES,
    STR_NO_SEASONS, STR_NO_SEASONS_AVAILABLE,
    STR_CLICK_SEASON, STR_SEASON_LOADED, STR_EPISODES_LOADED,
    STR_EPISODE,
)


class MainWindow(QMainWindow):
    """EmbyD main application window."""


    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.config_path = config_path
        self.config = load_config(config_path)

        # Worker threads (keep reference to prevent GC)
        self._threads = []

        # Download controller (owns all download worker threads)
        self._download_controller = DownloadController(self.config, self)

        # Cache for real-time row updates: task_id -> row index
        self._task_row_index: dict[str, int] = {}

        # Cache: search results (raw item dicts) for type routing on double-click
        self._search_items: list[dict] = []

        # Series Browser state
        self._series_browser_series_id: str = ""
        self._series_browser_series_name: str = ""
        self._series_browser_selected_episode_ids: set[str] = set()
        # Cache episodes per season for download: season_id -> list[episode_dict]
        self._series_browser_episode_cache: dict[str, list[dict]] = {}

        # Series Browser search results cache
        self._series_search_results: list[dict] = []

        # ---- Progress store: task_id -> (downloaded, total, speed) ----
        self._progress_store: dict[str, tuple] = {}
        self._progress_last_fast_update: dict[str, float] = {}

        # ---- Heartbeat timer for GUI responsiveness diagnostics ----
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(500)
        self._heartbeat_timer.timeout.connect(self._on_heartbeat)
        self._heartbeat_count = 0
        self._heartbeat_timer.start()

        # ---- Progress timer: update UI every 5 seconds ----
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(5000)
        self._progress_timer.timeout.connect(self._on_progress_timer)
        self._progress_timer.start()

        self._init_ui()
        self._connect_controller_signals()
        self._load_config_to_ui()

        # Recover interrupted downloading tasks from previous session
        self._recover_interrupted_tasks()

    def _recover_interrupted_tasks(self):
        """Mark previously downloading/preparing tasks as failed on startup."""
        tasks = db_list_tasks()
        for t in tasks:
            if t.status in ("downloading", "preparing"):
                update_task(t.task_id, status="failed",
                           error_message="Interrupted: GUI was closed during download")
                pass

        # Start the backend process (independent download worker)
        # DownloadController handles threading - no backend process needed

    # ---- Heartbeat (diagnostic) ----

    def _on_heartbeat(self):
        """Heartbeat tick - used to verify GUI event loop is alive."""
        self._heartbeat_count += 1
        # Log every 20 ticks (10s) at DEBUG level to avoid noise
        if self._heartbeat_count % 20 == 0:
            self.log.append_log("DEBUG", f"GUI heartbeat #{self._heartbeat_count}")

    # ---- UI Initialization ----

    def _init_ui(self):
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(900, 650)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Log widget (created early, embedded in Tasks tab detail panel)
        self.log = LogWidget()
        self.log.setMaximumHeight(150)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 0; }
            QTabBar::tab { padding: 8px 16px; }
        """)

        self._init_login_tab()
        self._init_search_tab()
        self._init_series_browser_tab()
        self._init_preview_tab()
        self._init_tasks_tab()

        layout.addWidget(self.tabs)

        # Status bar
        self.status_bar = StatusBarWidget()
        layout.addWidget(self.status_bar)

        # Update status from config with proper connection state
        if self.config.server_url:
            self.status_bar.set_server(self.config.server_url)
        if self.config.username:
            self.status_bar.set_user(self.config.username)
        self._update_connection_status()

    def _update_connection_status(self):
        """Update the connection status indicator based on current config."""
        token = get_token(self.config)
        if not self.config.server_url:
            self.status_bar.set_status(CONN_NOT_CONFIGURED, ok=False)
        elif not token:
            self.status_bar.set_status(CONN_NOT_VERIFIED, ok=False)
        else:
            self.status_bar.set_status(STATUS_CONNECTED, ok=True)

    # ---- DownloadController signal wiring ----

    def _connect_controller_signals(self):
        """Connect DownloadController signals to UI slots."""
        dc = self._download_controller
        dc.log_message.connect(self.log.append_log)
        dc.progress.connect(self._on_controller_progress)
        dc.status_changed.connect(self._on_controller_status_changed)
        dc.error.connect(self._on_controller_error)
        dc.finished_signal.connect(self._on_controller_finished)
        dc.paused_signal.connect(lambda tid: self._refresh_tasks())
        dc.cancelled_signal.connect(lambda tid: self._refresh_tasks())
        
        

    # ---- Progress throttle counter for log reporting ----

    def _on_controller_progress(self, task_id: str, downloaded: object, total: object, speed: float):
        """Store latest progress. Fast update every ~1s, plus 5s timer flush."""
        self._progress_store[task_id] = (downloaded, total, speed)
        now = _time.time()
        last = self._progress_last_fast_update.get(task_id, 0)
        if now - last >= 1.0:
            self._progress_last_fast_update[task_id] = now
            dl = int(downloaded) if downloaded is not None else 0
            tot = int(total) if total is not None else None
            self._update_task_row(task_id, dl, tot, speed)

    def _on_progress_timer(self):
        """Periodic (5s) progress UI update for all active tasks."""
        from app.utils.formatting import format_bytes, format_speed_gui, format_eta, format_progress_pct
        from app.downloader.task_store import get_task as db_get_task
        for task_id in list(self._progress_store.keys()):
            entry = self._progress_store.pop(task_id, None)
            if entry is None:
                continue
            downloaded, total, speed = entry
            dl = int(downloaded) if downloaded is not None else 0
            tot = int(total) if total is not None else None
            self._update_task_row(task_id, dl, tot, speed)
            # Also write latest progress to DB for survival across restarts
            if total is not None and total > 0:
                from app.downloader.task_store import update_task as db_update_task
                db_update_task(task_id, downloaded_bytes=dl, total_bytes=tot)

    def _on_controller_status_changed(self, task_id: str, status: str):
        """Refresh tasks table when a task status changes."""
        self._progress_store.pop(task_id, None)
        self._refresh_tasks()

    def _on_controller_error(self, task_id: str, message: str):
        """Show error from download controller."""
        self._progress_store.pop(task_id, None)
        self._refresh_tasks()

    def _on_controller_finished(self, task_id: str, output_path: str):
        """Task completed."""
        self._progress_store.pop(task_id, None)
        self._refresh_tasks()

    def _on_controller_paused(self, task_id: str):
        """Task paused."""
        self._progress_store.pop(task_id, None)
        self._refresh_tasks()

    def _on_controller_cancelled(self, task_id: str):
        """Task cancelled."""
        self._progress_store.pop(task_id, None)
        self._refresh_tasks()

    # ---- Worker helpers ----

    def _run_worker(self, worker, start_fn):
        """Run a worker in a background thread."""
        thread = QThread()
        worker.moveToThread(thread)
        # Use DirectConnection so the closure runs on the new thread,
        # not queued to the main thread event loop
        thread.started.connect(start_fn, Qt.ConnectionType.DirectConnection)
        if hasattr(worker, "finished"):
            worker.finished.connect(thread.quit)
        if hasattr(worker, "error"):
            worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        self._threads.append((thread, worker))
        thread.finished.connect(lambda: self._cleanup_thread(thread, worker))
        thread.start()

    def _cleanup_thread(self, thread, worker):
        if (thread, worker) in self._threads:
            self._threads.remove((thread, worker))
        worker.deleteLater()

    def _shutdown_threads(self):
        """Safely stop all helper threads. Callable from tests or closeEvent."""
        # Stop heartbeat
        if self._heartbeat_timer.isActive():
            self._heartbeat_timer.stop()

        # Stop backend client
        self._download_controller.stop_all()

        # Then stop remaining helper threads
        for thread, _worker in list(self._threads):
            if thread.isRunning():
                thread.quit()
                thread.wait(3000)

    def closeEvent(self, event):
        # Check for active downloads
        # Check for active downloads via task store
        import asyncio
        downloading = False
        try:
            from app.downloader.task_store import count_tasks
            downloading = count_tasks(status_filter="downloading") > 0 or count_tasks(status_filter="preparing") > 0
        except Exception:
            pass
        if downloading:
            reply = QMessageBox.question(
                self,
                DLG_ACTIVE_DOWNLOADS,
                DLG_ACTIVE_DOWNLOADS_MSG,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._shutdown_threads()
            else:
                event.ignore()
                return
        else:
            self._shutdown_threads()

        super().closeEvent(event)

    # ======== Tab 1: Login / Config ========

    def _init_login_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Server info group
        grp = QGroupBox(GRP_SERVER)
        fl = QFormLayout(grp)

        self.login_server_url = QLineEdit()
        self.login_server_url.setObjectName("server_url_input")
        self.login_server_url.setPlaceholderText(PLACEHOLDER_SERVER)
        fl.addRow(LBL_SERVER_URL, self.login_server_url)

        self.login_username = QLineEdit()
        self.login_username.setObjectName("username_input")
        self.login_username.setPlaceholderText(PLACEHOLDER_USERNAME)
        fl.addRow(LBL_USERNAME, self.login_username)

        self.login_password = QLineEdit()
        self.login_password.setObjectName("password_input")
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password.setPlaceholderText(PLACEHOLDER_PASSWORD)
        fl.addRow(LBL_PASSWORD, self.login_password)

        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton(BTN_LOGIN)
        self.btn_login.setObjectName("login_button")
        self.btn_login.clicked.connect(self._on_login)
        self.btn_ping = QPushButton(BTN_PING)
        self.btn_ping.setObjectName("ping_button")
        self.btn_ping.clicked.connect(self._on_ping)
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_ping)
        btn_layout.addStretch()
        fl.addRow("", btn_layout)

        layout.addWidget(grp)

        # Download directory group
        dir_grp = QGroupBox(GRP_DOWNLOAD_DIR)
        dir_layout = QHBoxLayout(dir_grp)
        self.download_dir_input = QLineEdit()
        self.download_dir_input.setObjectName("download_dir_input")
        self.download_dir_input.setPlaceholderText(PLACEHOLDER_DOWNLOAD_DIR)
        dir_layout.addWidget(self.download_dir_input, 1)

        self.btn_browse_download_dir = QPushButton(BTN_BROWSE)
        self.btn_browse_download_dir.clicked.connect(self._on_browse_download_dir)
        dir_layout.addWidget(self.btn_browse_download_dir)

        self.btn_save_download_dir = QPushButton(BTN_SAVE_DIR)
        self.btn_save_download_dir.clicked.connect(self._on_save_download_dir)
        dir_layout.addWidget(self.btn_save_download_dir)

        layout.addWidget(dir_grp)

        # Config info
        cfg_label = QLabel(f"Config file: {get_config_path_display(self.config_path)}")
        cfg_label.setStyleSheet("color: #888; padding: 4px;")
        layout.addWidget(cfg_label)

        layout.addStretch()
        self.tabs.addTab(tab, TAB_LOGIN)

    def _load_config_to_ui(self):
        if self.config.server_url:
            self.login_server_url.setText(self.config.server_url)
        if self.config.username:
            self.login_username.setText(self.config.username)
        if self.config.download_dir:
            self.download_dir_input.setText(self.config.download_dir)

    def _get_download_dir_from_ui(self) -> str:
        return self.download_dir_input.text().strip()

    def _on_browse_download_dir(self):
        start_dir = self._get_download_dir_from_ui() or ""
        directory = QFileDialog.getExistingDirectory(self, "Choose Download Directory", start_dir)
        if directory:
            self.download_dir_input.setText(directory)

    def _on_save_download_dir(self):
        directory = self._get_download_dir_from_ui()
        if not directory:
            QMessageBox.warning(self, DLG_MISSING_DIR, DLG_MISSING_DIR_MSG)
            return
        self.config.download_dir = directory
        save_config(self.config, self.config_path)
        # Backend reads config from disk on task start
        self.log.append_log("OK", f"Download directory saved: {directory}")

    def _on_login(self):
        server = self.login_server_url.text().strip()
        username = self.login_username.text().strip()
        password = self.login_password.text()

        if not server or not username or not password:
            QMessageBox.warning(self, DLG_MISSING_FIELDS, DLG_MISSING_FIELDS_MSG)
            return

        self.log.append_log("INFO", f"Logging in to {server} as {username}...")
        self.btn_login.setEnabled(False)

        worker = LoginWorker()
        worker.finished.connect(self._on_login_result)
        worker.error.connect(self._on_worker_error)
        self._run_worker(worker, lambda: worker.run(server, username, password, self.config_path))

    def _on_login_result(self, data):
        self.btn_login.setEnabled(True)
        self.log.append_log("OK", f"Logged in as '{data['username']}' (User ID: {data['user_id']})")
        self.status_bar.set_server(data["server_url"])
        self.status_bar.set_user(data["username"])
        self.status_bar.set_status(STATUS_CONNECTED, ok=True)
        self._update_connection_status()

        # Reload config
        self.config = load_config(self.config_path)
        # Backend reads config from disk on task start

        # Auto whoami
        token = get_token(self.config)
        if token:
            self._run_whoami(self.config.server_url, token)

    def _on_ping(self):
        server = self.login_server_url.text().strip()
        if not server:
            QMessageBox.warning(self, DLG_MISSING_SERVER, DLG_MISSING_SERVER_MSG)
            return

        self.log.append_log("INFO", f"Pinging {server}...")
        worker = PingWorker()
        worker.finished.connect(self._on_ping_result)
        worker.error.connect(self._on_worker_error)
        self._run_worker(worker, lambda: worker.run(server))

    def _on_ping_result(self, data):
        name = data.get("server_name", "?")
        version = data.get("version", "")
        msg = f"Server: {name}"
        if version:
            msg += f" v{version}"
        self.log.append_log("OK", msg)
        self.status_bar.set_status(CONN_SERVER_REACHABLE, ok=True)

    # ======== Tab 2: Search ========

    def _init_search_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Search bar
        top_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("movie_search_input")
        self.search_input.setPlaceholderText(PLACEHOLDER_SEARCH)
        self.search_input.returnPressed.connect(self._on_search)
        top_layout.addWidget(self.search_input, 1)

        self.search_limit = QSpinBox()
        self.search_limit.setRange(1, 200)
        self.search_limit.setValue(20)
        top_layout.addWidget(QLabel(LBL_LIMIT))
        top_layout.addWidget(self.search_limit)

        self.btn_search = QPushButton(BTN_SEARCH)
        self.btn_search.setObjectName("movie_search_button")
        self.btn_search.clicked.connect(self._on_search)
        top_layout.addWidget(self.btn_search)

        layout.addLayout(top_layout)

        # Results table
        self.search_table = QTableWidget()
        self.search_table.setObjectName("movie_results_table")
        self.search_table.setColumnCount(4)
        self.search_table.setHorizontalHeaderLabels([COL_ID, COL_TITLE, COL_INFO, COL_TYPE])
        self.search_table.horizontalHeader().setStretchLastSection(True)
        self.search_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.search_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.search_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.search_table.cellDoubleClicked.connect(self._on_search_double_click)
        layout.addWidget(self.search_table)

        self.tabs.addTab(tab, TAB_SEARCH)

    def _on_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        token = get_token(self.config)
        if not token:
            QMessageBox.warning(self, DLG_NOT_LOGGED_IN, DLG_NOT_LOGGED_IN_MSG)
            return

        self.log.append_log("INFO", f"Searching for '{query}'...")
        self.btn_search.setEnabled(False)

        worker = SearchWorker()
        worker.finished.connect(self._on_search_result)
        worker.error.connect(self._on_worker_error)
        self._run_worker(worker, lambda: worker.run(
            self.config.server_url, token, query, self.search_limit.value(),
        ))

    def _on_search_result(self, items):
        self.btn_search.setEnabled(True)
        self.search_table.setRowCount(0)
        self._search_items = list(items)  # cache for type routing

        if not items:
            self.log.append_log("INFO", DLG_NO_SERIES_RESULTS)
            return

        self.log.append_log("OK", f"Found {len(items)} results.")
        self.search_table.setRowCount(len(items))

        for row, item in enumerate(items):
            self.search_table.setItem(row, 0, QTableWidgetItem(item.get("Id", "")))
            from app.core.download_preview import build_item_display_title, format_episode_code
            self.search_table.setItem(row, 1, QTableWidgetItem(build_item_display_title(item)))
            if item.get("Type") == "Episode":
                info = format_episode_code(
                    int(item.get("ParentIndexNumber") or 0),
                    int(item.get("IndexNumber") or 0),
                )
            else:
                info = str(item.get("ProductionYear", ""))
            self.search_table.setItem(row, 2, QTableWidgetItem(info))
            self.search_table.setItem(row, 3, QTableWidgetItem(item.get("Type", "")))

    def _on_search_double_click(self, row, col):
        """Route double-click based on item type.

        Movie     -> Preview tab
        Series    -> Series Browser tab
        Episode   -> Preview tab (with episode metadata)
        Unknown   -> Show info, no crash
        """
        if row < 0 or row >= len(self._search_items):
            return
        item = self._search_items[row]
        item_type = item.get("Type", "")

        if item_type == "Movie":
            self.tabs.setCurrentIndex(3)  # Preview tab
            self.preview_item_id.setText(item.get("Id", ""))
            self._on_preview()
        elif item_type == "Series":
            self._enter_series_browser(item)
        elif item_type == "Episode":
            self.tabs.setCurrentIndex(3)  # Preview tab
            self.preview_item_id.setText(item.get("Id", ""))
            self._on_preview()
        else:
            QMessageBox.information(
                self, DLG_UNKNOWN_TYPE,
                DLG_UNKNOWN_TYPE_MSG.format(item_type=item_type),
            )

    # ======== Tab 3: Preview ========

    def _init_preview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Item ID input + action buttons
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel(LBL_ITEM_ID))
        self.preview_item_id = QLineEdit()
        self.preview_item_id.setObjectName("preview_item_id_input")
        self.preview_item_id.setPlaceholderText("Enter item ID or double-click from Search")
        id_layout.addWidget(self.preview_item_id, 1)
        self.btn_preview = QPushButton(BTN_PREVIEW)
        self.btn_preview.setObjectName("preview_button")
        self.btn_preview.clicked.connect(self._on_preview)
        id_layout.addWidget(self.btn_preview)
        self.btn_download = QPushButton(BTN_DOWNLOAD)
        self.btn_download.setObjectName("preview_download_button")
        self.btn_download.clicked.connect(self._on_download)
        self.btn_download.setEnabled(False)
        id_layout.addWidget(self.btn_download)
        layout.addLayout(id_layout)

        # Media source version selector
        ms_layout = QHBoxLayout()
        ms_layout.addWidget(QLabel("Version:"))
        self.media_source_combo = QComboBox()
        self.media_source_combo.setObjectName("preview_media_source_combo")
        self.media_source_combo.setMinimumWidth(300)
        self.media_source_combo.setEnabled(False)
        self.media_source_combo.setToolTip("Select media version/resolution to download")
        ms_layout.addWidget(self.media_source_combo, 1)
        ms_layout.addStretch()
        layout.addLayout(ms_layout)

        # Details group
        grp = QGroupBox(GRP_PREVIEW)
        gl = QGridLayout(grp)

        self.preview_title = QLabel("--")
        self.preview_size = QLabel("--")
        self.preview_duration = QLabel("--")
        self.preview_container = QLabel("--")
        self.preview_protocol = QLabel("--")
        self.preview_method = QLabel("--")
        self.preview_status = QLabel("--")
        self.preview_reason = QLabel("--")
        self.preview_output = QLabel("--")

        gl.addWidget(QLabel(LBL_PREVIEW_TITLE), 0, 0)
        gl.addWidget(self.preview_title, 0, 1)
        gl.addWidget(QLabel(LBL_PREVIEW_SIZE), 1, 0)
        gl.addWidget(self.preview_size, 1, 1)
        gl.addWidget(QLabel(LBL_PREVIEW_DURATION), 2, 0)
        gl.addWidget(self.preview_duration, 2, 1)
        gl.addWidget(QLabel(LBL_PREVIEW_CONTAINER), 0, 2)
        gl.addWidget(self.preview_container, 0, 3)
        gl.addWidget(QLabel(LBL_PREVIEW_PROTOCOL), 1, 2)
        gl.addWidget(self.preview_protocol, 1, 3)
        gl.addWidget(QLabel(LBL_PREVIEW_METHOD), 2, 2)
        gl.addWidget(self.preview_method, 2, 3)
        gl.addWidget(QLabel(LBL_PREVIEW_STATUS), 3, 0)
        gl.addWidget(self.preview_status, 3, 1)
        gl.addWidget(QLabel(LBL_PREVIEW_REASON), 4, 0)
        gl.addWidget(self.preview_reason, 4, 1, 1, 3)
        gl.addWidget(QLabel(LBL_PREVIEW_OUTPUT), 5, 0)
        gl.addWidget(self.preview_output, 5, 1, 1, 3)

        layout.addWidget(grp)

        layout.addStretch()
        self.tabs.addTab(tab, TAB_PREVIEW)

    def _on_preview(self):
        item_id = self.preview_item_id.text().strip()
        if not item_id:
            return

        token = get_token(self.config)
        if not token:
            QMessageBox.warning(self, DLG_NOT_LOGGED_IN, DLG_NOT_LOGGED_IN_MSG)
            return
        download_dir = self._get_download_dir_from_ui()
        if not download_dir:
            QMessageBox.warning(self, DLG_MISSING_DIR, DLG_MISSING_DIR_MSG)
            return

        self.log.append_log("INFO", f"Previewing item {item_id}...")
        self.btn_preview.setEnabled(False)

        self.preview_title.setText(STR_LOADING)
        self.preview_size.setText("--")
        self.preview_duration.setText("--")
        self.preview_container.setText("--")
        self.preview_protocol.setText("--")
        self.preview_method.setText("--")
        self.preview_status.setText("--")
        self.preview_reason.setText("--")
        self.preview_output.setText("--")

        worker = DryRunWorker()
        worker.finished.connect(self._on_preview_result)
        worker.error.connect(self._on_worker_error)
        self._run_worker(worker, lambda: worker.run(
            item_id, self.config.server_url, token, download_dir,
        ))

    def _on_preview_result(self, result):
        self.btn_preview.setEnabled(True)
        if result.item_type == "Episode":
            from app.core.download_preview import format_episode_code
            code = format_episode_code(result.season_number, result.episode_number)
            title_parts = [p for p in (result.series_name, code, result.title) if p]
            self.preview_title.setText(" - ".join(title_parts))
        else:
            self.preview_title.setText(f"{result.title} ({result.year})" if result.year else result.title)
        self.preview_size.setText(result.size_human)
        self.preview_duration.setText(result.runtime_human)
        self.preview_container.setText(result.container)
        self.preview_protocol.setText(result.protocol)
        self.preview_method.setText(result.method_label)
        status_text = "[OK] Downloadable" if result.can_download else "[FAIL] Cannot download"
        self.preview_status.setText(status_text)
        status_color = "#4ec9b0" if result.can_download else "#f44747"
        self.preview_status.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        self.preview_reason.setText(result.reason)
        self.preview_output.setText(result.output_path)

        # Enable download button if downloadable
        self.btn_download.setEnabled(result.can_download)
        if result.can_download:
            self.btn_download.setStyleSheet("background-color: #4ec9b0; color: #1e1e1e; font-weight: bold;")

        self.log.append_log("OK", f"Preview complete for {result.title}")

        # Fetch media source options for version selection
        self._fetch_media_sources(result.item_id)

    def _fetch_media_sources(self, item_id: str):
        """Fetch PlaybackInfo media sources for version selection."""
        token = get_token(self.config)
        if not token:
            return
        self.media_source_combo.clear()
        self.media_source_combo.addItem("Auto (best)", "")
        self.media_source_combo.setEnabled(False)
        worker = MediaSourcesWorker()
        worker.finished.connect(self._on_media_sources_loaded)
        worker.error.connect(lambda msg: self.log.append_log("WARNING", f"Media sources: {msg}"))
        self._run_worker(worker, lambda: worker.run(
            item_id, self.config.server_url, token))

    def _on_media_sources_loaded(self, options):
        """Populate the media source combo box with available versions."""
        self.media_source_combo.clear()
        self.media_source_combo.addItem("Auto (best)", "")
        if not options:
            self.log.append_log("INFO", "Single media source available.")
            return
        for opt in options:
            self.media_source_combo.addItem(opt["label"], opt["id"])
        self.media_source_combo.setEnabled(True)
        self.media_source_combo.setCurrentIndex(0)
        if len(options) > 1:
            self.log.append_log("INFO", f"{len(options)} media versions available. Select preferred version.")

    def _get_selected_media_source_id(self) -> str:
        """Get the user-selected media_source_id from the combo."""
        if hasattr(self, "media_source_combo") and self.media_source_combo.count() > 0:
            idx = self.media_source_combo.currentIndex()
            if idx >= 0:
                return self.media_source_combo.itemData(idx) or ""
        return ""

    # ---- Download (via DownloadController) ----

    # ---- Download (via DownloadController) ----

    def _on_download(self):
        """Add the preview item to task list (pending). Use task list to start."""
        timing_event("download_click_enter")
        item_id = self.preview_item_id.text().strip()
        if not item_id:
            timing_event("download_click_exit", item_id=item_id, result="missing_item")
            return

        token = get_token(self.config)
        if not token:
            timing_event("download_click_exit", item_id=item_id, result="not_logged_in")
            QMessageBox.warning(self, DLG_NOT_LOGGED_IN, DLG_NOT_LOGGED_IN_MSG)
            return
        download_dir = self._get_download_dir_from_ui()
        if not download_dir:
            timing_event("download_click_exit", item_id=item_id, result="missing_dir")
            QMessageBox.warning(self, DLG_MISSING_DIR, DLG_MISSING_DIR_MSG)
            return

        media_source_id = self._get_selected_media_source_id()
        if media_source_id:
            self.log.append_log("INFO", f"Using selected media source: {media_source_id}")

        # Create pending task via task_store (no auto-start)
        self.log.append_log("INFO", f"Creating pending task for {item_id}...")
        try:
            from app.downloader.task_store import create_task
            task = create_task(
                item_id=item_id,
                title=self.preview_title.text() or item_id,
                media_type="Movie",
                media_source_id=media_source_id,
            )
            if task:
                self.log.append_log("OK", f"Task {task.task_id} created (pending). Go to Tasks tab to start.")
                self.tabs.setCurrentIndex(4)
                self._on_download_created({"task_id": task.task_id}, download_dir)
            else:
                self._on_download_create_error("Failed to create task", item_id)
        except Exception as e:
            self.log.append_log("ERROR", f"Failed to create task: {e}")
            self._on_download_create_error(str(e), item_id)
        timing_event("download_click_exit", item_id=item_id, result="creating")

    def _on_download_created(self, result, download_dir: str):
        """Called when task is created (pending). Switch to Tasks tab."""
        task_id = result.get("task_id", "") if isinstance(result, dict) else ""
        if not task_id:
            self.log.append_log("WARNING", "Task may already exist or failed to create.")
            self.tabs.setCurrentIndex(4)
            self._refresh_tasks()
            return

        self.log.append_log("OK", f"Task {task_id} created (pending).")
        self.tabs.setCurrentIndex(4)
        self._refresh_tasks()

    def _on_download_started(self, task_id: str, result):
        """Called when start_task completes in background."""
        if isinstance(result, dict) and result.get("error"):
            err_msg = result["error"]
            self.log.append_log("ERROR", f"Failed to start task {task_id}: {err_msg}")
            QMessageBox.warning(self, "Start Failed", f"Task {task_id[:8]}... start failed:\n{err_msg}")
            self.tabs.setCurrentIndex(4)
            self._refresh_tasks()
            return
        if not isinstance(result, dict) or result.get("status") != "ok":
            self.log.append_log("ERROR", f"Start unexpected response: task_id={task_id[:8]}..., result={result}")
            self.tabs.setCurrentIndex(4)
            self._refresh_tasks()
            return
        self.log.append_log("OK", f"Task {task_id} is now downloading.")
        self.tabs.setCurrentIndex(4)
        self._refresh_tasks()
    def _on_download_create_error(self, message: str, item_id: str):
        self.log.append_log("ERROR", f"Failed to create task for {item_id}: {message}")
        self.tabs.setCurrentIndex(4)
        self._refresh_tasks()

    def _on_download_start_error(self, task_id: str, message: str):
        self.log.append_log("ERROR", f"Failed to start task {task_id}: {message}")
        QMessageBox.warning(self, "Start Error", f"Failed to start task {task_id[:8]}...:\n{message}")
        self._refresh_tasks()

    # ======== Tab 4: Series Browser ========

    def _init_series_browser_tab(self):
        """Two-level series browser: Level 1 = Series/Seasons, Level 2 = Season Episodes."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # ---- Series search area ----
        search_layout = QHBoxLayout()
        self.series_search_input = QLineEdit()
        self.series_search_input.setObjectName("series_search_input")
        self.series_search_input.setPlaceholderText(PLACEHOLDER_SERIES_SEARCH)
        self.series_search_input.returnPressed.connect(self._on_series_search)
        search_layout.addWidget(self.series_search_input, 1)

        self.btn_series_search = QPushButton(BTN_SERIES_SEARCH)
        self.btn_series_search.setObjectName("series_search_button")
        self.btn_series_search.clicked.connect(self._on_series_search)
        search_layout.addWidget(self.btn_series_search)
        layout.addLayout(search_layout)

        # Series search results table (hidden until search performed)
        self.series_search_table = QTableWidget()
        self.series_search_table.setObjectName("series_results_table")
        self.series_search_table.setColumnCount(3)
        self.series_search_table.setHorizontalHeaderLabels([
            COL_SERIES_NAME, COL_SERIES_YEAR, COL_SERIES_ID,
        ])
        hdr = self.series_search_table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.series_search_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.series_search_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.series_search_table.cellDoubleClicked.connect(self._on_series_search_double_click)
        self.series_search_table.setMaximumHeight(180)
        self.series_search_table.setVisible(False)
        layout.addWidget(self.series_search_table)

        # Stacked widget: Page 0 = Series/Seasons, Page 1 = Season Episodes
        self.series_stack = QStackedWidget()

        # --- Page 0: Series + Season List ---
        page0 = QWidget()
        page0_layout = QVBoxLayout(page0)
        page0_layout.setContentsMargins(0, 0, 0, 0)

        info_layout = QHBoxLayout()
        self.series_browser_title = QLabel(STR_NO_SERIES_LOADED)
        self.series_browser_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #d4d4d4;")
        info_layout.addWidget(self.series_browser_title, 1)
        self.series_browser_status = QLabel(STR_DOUBLE_CLICK_HINT)
        self.series_browser_status.setStyleSheet("color: #888;")
        info_layout.addWidget(self.series_browser_status)
        page0_layout.addLayout(info_layout)

        page0_layout.addWidget(QLabel(LBL_SEASONS))
        self.season_list = QListWidget()
        self.season_list.setObjectName("season_list")
        self.season_list.setMaximumWidth(400)
        self.season_list.currentRowChanged.connect(self._on_season_selected)
        page0_layout.addWidget(self.season_list, 1)

        self.series_stack.addWidget(page0)  # index 0

        # --- Page 1: Season Episodes ---
        page1 = QWidget()
        page1_layout = QVBoxLayout(page1)
        page1_layout.setContentsMargins(0, 0, 0, 0)

        # Back button
        back_layout = QHBoxLayout()
        self.btn_back_to_seasons = QPushButton(BTN_BACK_TO_SEASONS)
        self.btn_back_to_seasons.setObjectName("episode_back_button")
        self.btn_back_to_seasons.clicked.connect(self._on_back_to_seasons)
        back_layout.addWidget(self.btn_back_to_seasons)
        self.season_episode_title = QLabel("")
        self.season_episode_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #d4d4d4;")
        back_layout.addWidget(self.season_episode_title, 1)
        back_layout.addStretch()
        page1_layout.addLayout(back_layout)

        # Episode table with checkboxes
        self.series_episode_table = QTableWidget()
        self.series_episode_table.setObjectName("episode_table")
        self.series_episode_table.setColumnCount(6)
        self.series_episode_table.setHorizontalHeaderLabels([
            "Select", "S", "E", COL_TITLE, COL_ID, "Runtime"
        ])
        hdr2 = self.series_episode_table.horizontalHeader()
        hdr2.setStretchLastSection(True)
        hdr2.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.series_episode_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.series_episode_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        page1_layout.addWidget(self.series_episode_table, 1)

        # Season action buttons
        season_action_layout = QHBoxLayout()

        self.btn_sb_select_season = QPushButton(BTN_SELECT_SEASON)
        self.btn_sb_select_season.setObjectName("episode_select_all_button")
        self.btn_sb_select_season.clicked.connect(lambda: self._set_visible_episodes_checked(True))
        season_action_layout.addWidget(self.btn_sb_select_season)

        self.btn_sb_clear_season = QPushButton(BTN_CLEAR_SEASON)
        self.btn_sb_clear_season.setObjectName("episode_clear_all_button")
        self.btn_sb_clear_season.clicked.connect(lambda: self._set_visible_episodes_checked(False))
        season_action_layout.addWidget(self.btn_sb_clear_season)

        season_action_layout.addStretch()

        self.btn_sb_refresh_episodes = QPushButton(BTN_REFRESH_EPISODES)
        self.btn_sb_refresh_episodes.setObjectName("episode_refresh_button")
        self.btn_sb_refresh_episodes.clicked.connect(self._on_refresh_episodes)
        season_action_layout.addWidget(self.btn_sb_refresh_episodes)

        self.btn_sb_download = QPushButton(BTN_DOWNLOAD_SELECTED)
        self.btn_sb_download.setObjectName("episode_download_selected_button")
        self.btn_sb_download.clicked.connect(self._on_series_browser_download)
        self.btn_sb_download.setStyleSheet("background-color: #0e639c; color: #fff; font-weight: bold; padding: 4px 12px;")
        season_action_layout.addWidget(self.btn_sb_download)

        page1_layout.addLayout(season_action_layout)

        # Status label
        self.sb_episode_status = QLabel("")
        self.sb_episode_status.setStyleSheet("color: #888;")
        page1_layout.addWidget(self.sb_episode_status)

        self.series_stack.addWidget(page1)  # index 1

        layout.addWidget(self.series_stack, 1)
        self.tabs.addTab(tab, TAB_SERIES)

    # ------------------------------------------------------------------
    # Series Browser - Search logic (Stage 10E)
    # ------------------------------------------------------------------

    def _on_series_search(self):
        """Search for Series items directly from the Series Browser tab."""
        query = self.series_search_input.text().strip()
        if not query:
            QMessageBox.information(self, DLG_EMPTY_SERIES_SEARCH, DLG_EMPTY_SERIES_SEARCH)
            return

        token = get_token(self.config)
        if not token:
            QMessageBox.warning(self, DLG_NOT_LOGGED_IN, DLG_NOT_LOGGED_IN_MSG)
            return

        self.log.append_log("INFO", f"Searching series: '{query}'...")
        self.btn_series_search.setEnabled(False)

        worker = SeriesSearchWorker()
        worker.finished.connect(self._on_series_search_result)
        worker.error.connect(self._on_worker_error)
        self._run_worker(worker, lambda: worker.run(
            self.config.server_url, token, query, 30,
        ))

    def _on_series_search_result(self, items):
        """Display Series search results in the series search table."""
        self.btn_series_search.setEnabled(True)
        self.series_search_table.setRowCount(0)
        self._series_search_results = list(items)

        if not items:
            self.log.append_log("INFO", DLG_NO_SERIES_RESULTS)
            self.series_search_table.setVisible(False)
            return

        self.log.append_log("OK", f"Found {len(items)} series.")
        self.series_search_table.setVisible(True)
        self.series_search_table.setRowCount(len(items))

        for row, item in enumerate(items):
            name = item.get("Name", STR_UNKNOWN)
            year = str(item.get("ProductionYear", ""))
            sid = item.get("Id", "")
            self.series_search_table.setItem(row, 0, QTableWidgetItem(name))
            self.series_search_table.setItem(row, 1, QTableWidgetItem(year))
            self.series_search_table.setItem(row, 2, QTableWidgetItem(sid))

    def _on_series_search_double_click(self, row, col):
        """Double-click a Series search result to load its seasons."""
        if row < 0 or row >= len(self._series_search_results):
            return
        item = self._series_search_results[row]
        self._enter_series_browser(item)

    # ------------------------------------------------------------------
    # Series Browser logic
    # ------------------------------------------------------------------

    def _enter_series_browser(self, item: dict):
        """Enter Series Browser for a Series item.

        Clears previous state, stores series info, fetches seasons.
        """
        series_id = item.get("Id", "")
        series_name = item.get("Name", "Unknown Series")
        self._series_browser_series_id = series_id
        self._series_browser_series_name = series_name
        self._series_browser_selected_episode_ids.clear()
        self._series_browser_episode_cache.clear()

        self.series_browser_title.setText(f"{series_name}  (ID: {series_id})")
        self.series_browser_status.setText(STR_LOADING_SEASONS)
        self.sb_episode_status.setText("")
        self.season_list.clear()
        self.series_episode_table.setRowCount(0)
        self.series_stack.setCurrentIndex(0)  # Ensure on Season list page

        self.tabs.setCurrentIndex(2)  # Series Browser tab

        token = get_token(self.config)
        if not token:
            QMessageBox.warning(self, DLG_NOT_LOGGED_IN, DLG_NOT_LOGGED_IN_MSG)
            return

        self.log.append_log("INFO", f"Loading seasons for '{series_name}'...")
        worker = SeriesSeasonsWorker()
        worker.finished.connect(self._on_seasons_loaded)
        worker.error.connect(self._on_worker_error)
        self._run_worker(worker, lambda: worker.run(
            self.config.server_url, token, series_id, series_name,
        ))

    def _on_seasons_loaded(self, data: dict):
        """Populate the season list from worker result."""
        seasons = data.get("seasons", [])
        self.season_list.clear()
        self._series_browser_episode_cache.clear()
        self.series_episode_table.setRowCount(0)

        if not seasons:
            self.series_browser_status.setText(STR_NO_SEASONS)
            self.sb_episode_status.setText(STR_NO_SEASONS_AVAILABLE)
            return

        for s in seasons:
            sn = s.get("season_number", 0)
            name = s.get("name", f"Season {sn}")
            item_id = s.get("item_id", "")
            display = f"{name}  (ID: {item_id})"
            self.season_list.addItem(display)

        self.series_browser_status.setText(f"{len(seasons)}{STR_SEASON_LOADED}")
        self.sb_episode_status.setText(f"{len(seasons)}{STR_CLICK_SEASON}")
        self.log.append_log("OK", f"Loaded {len(seasons)} seasons for '{data.get('series_name', '')}'.")

        # Auto-select first season
        if self.season_list.count() > 0:
            self.season_list.setCurrentRow(0)

    def _on_season_selected(self, row: int):
        """Navigate to Season Episodes page (Level 2) and load episodes in background."""
        if row < 0:
            return

        token = get_token(self.config)
        if not token:
            return

        season_item_text = self.season_list.currentItem().text()
        season_id = ""
        if "(ID: " in season_item_text:
            season_id = season_item_text.rsplit("(ID: ", 1)[1].rstrip(")")

        if not season_id:
            return

        # Record current season
        self._series_browser_current_season_id = season_id

        # Extract season name from list item
        season_name = season_item_text.split("  (ID: ")[0] if "  (ID: " in season_item_text else f"Season {row}"
        self.season_episode_title.setText(f"{self._series_browser_series_name} - {season_name}")

        # Switch to page 1
        self.series_stack.setCurrentIndex(1)

        # Show loading state
        self.series_episode_table.setRowCount(0)
        self.sb_episode_status.setText("Loading episodes...")

        # Load episodes in background worker (non-blocking)
        worker = SeasonEpisodesWorker()
        worker.finished.connect(self._on_episodes_loaded)
        worker.error.connect(self._on_worker_error)
        self._run_worker(worker, lambda: worker.run(
            self.config.server_url, token,
            self._series_browser_series_id, season_id,
        ))

    def _on_back_to_seasons(self):
        """Return to Level 1: Season list."""
        self.series_stack.setCurrentIndex(0)

    def _on_episodes_loaded(self, data: dict):
        """Populate episode table from worker result, restoring checked state."""
        episodes = data.get("episodes", [])
        season_id = data.get("season_id", "")

        # Cache episodes for this season
        self._series_browser_episode_cache[season_id] = episodes

        self._populate_episode_table(episodes)
        self.sb_episode_status.setText(f"{len(episodes)} episodes loaded.")
        self.series_browser_status.setText("Season episodes loaded.")
        self.sb_episode_status.setText(
            f"{len(episodes)}{STR_EPISODE}。{len(self._series_browser_selected_episode_ids)} {STR_EPISODES_LOADED}"
        )
        self.log.append_log("OK", f"Loaded {len(episodes)} episodes for season {season_id}.")

    def _populate_episode_table(self, episodes: list[dict]):
        """Fill the episode table with checkboxes, restoring global selection set."""
        self.series_episode_table.setRowCount(len(episodes))

        for row, ep in enumerate(episodes):
            ep_id = ep.get("item_id", "")

            # Col 0: Checkbox
            select_item = QTableWidgetItem("")
            select_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            select_item.setCheckState(
                Qt.CheckState.Checked if ep_id in self._series_browser_selected_episode_ids
                else Qt.CheckState.Unchecked
            )
            self.series_episode_table.setItem(row, 0, select_item)

            # Col 1: Season number
            self.series_episode_table.setItem(row, 1, QTableWidgetItem(str(ep.get("season_number", 0))))

            # Col 2: Episode number
            self.series_episode_table.setItem(row, 2, QTableWidgetItem(str(ep.get("episode_number", 0))))

            # Col 3: Title
            self.series_episode_table.setItem(row, 3, QTableWidgetItem(ep.get("name", "")))

            # Col 4: Item ID
            self.series_episode_table.setItem(row, 4, QTableWidgetItem(ep_id[:16]))

            # Col 5: Runtime
            ticks = ep.get("runtime_ticks", 0) or 0
            if ticks > 0:
                minutes = int(ticks // 600000000)
                runtime = f"{minutes}min"
            else:
                runtime = "--"
            self.series_episode_table.setItem(row, 5, QTableWidgetItem(runtime))

        # Sync visible check states back to selection set
        self._sync_check_states_to_selection()

    def _set_visible_episodes_checked(self, checked: bool):
        """Set check state for all currently visible episodes."""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.series_episode_table.rowCount()):
            item = self.series_episode_table.item(row, 0)
            if item:
                item.setCheckState(state)
        self._sync_check_states_to_selection()

    def _sync_check_states_to_selection(self):
        """Sync table checkbox states to the global selection set."""
        for row in range(self.series_episode_table.rowCount()):
            select_item = self.series_episode_table.item(row, 0)
            id_item = self.series_episode_table.item(row, 4)
            if not select_item or not id_item:
                continue
            ep_id_full = self._get_episode_id_at_row(row)
            if not ep_id_full:
                continue
            if select_item.checkState() == Qt.CheckState.Checked:
                self._series_browser_selected_episode_ids.add(ep_id_full)
            else:
                self._series_browser_selected_episode_ids.discard(ep_id_full)

        sel = len(self._series_browser_selected_episode_ids)
        self.sb_episode_status.setText(
            f"{self.series_episode_table.rowCount()} visible, {sel} selected overall."
        )

    def _get_episode_id_at_row(self, row: int) -> str:
        """Get the full episode ID for a given table row from the episode cache."""
        season_id = self._current_season_id()
        if season_id and season_id in self._series_browser_episode_cache:
            episodes = self._series_browser_episode_cache[season_id]
            if row < len(episodes):
                return episodes[row].get("item_id", "")
        return ""

    def _current_season_id(self) -> str:
        """Get the currently selected season ID from the season list."""
        if self.season_list.currentItem() is None:
            return ""
        text = self.season_list.currentItem().text()
        if "(ID: " in text:
            return text.rsplit("(ID: ", 1)[1].rstrip(")")
        return ""

    def _all_cached_episode_ids(self) -> list[str]:
        """Return all episode IDs from all cached seasons."""
        ids = []
        for episodes in self._series_browser_episode_cache.values():
            for ep in episodes:
                ids.append(ep.get("item_id", ""))
        return ids

    def _on_refresh_seasons(self):
        """Re-fetch seasons for the current series."""
        series_id = self._series_browser_series_id
        if not series_id:
            return
        token = get_token(self.config)
        if not token:
            QMessageBox.warning(self, DLG_NOT_LOGGED_IN, DLG_NOT_LOGGED_IN_MSG)
            return
        self.log.append_log("INFO", "Refreshing seasons...")
        worker = SeriesSeasonsWorker()
        worker.finished.connect(self._on_seasons_loaded)
        worker.error.connect(self._on_worker_error)
        self._run_worker(worker, lambda: worker.run(
            self.config.server_url, token, series_id, self._series_browser_series_name,
        ))

    def _on_refresh_episodes(self):
        """Re-fetch episodes for the current season."""
        season_id = getattr(self, "_series_browser_current_season_id", "")
        if not season_id:
            return
        token = get_token(self.config)
        if not token:
            QMessageBox.warning(self, DLG_NOT_LOGGED_IN, DLG_NOT_LOGGED_IN_MSG)
            return
        self.log.append_log("INFO", "Refreshing episodes...")
        worker = SeasonEpisodesWorker()
        worker.finished.connect(self._on_episodes_loaded)
        worker.error.connect(self._on_worker_error)
        self._run_worker(worker, lambda: worker.run(
            self.config.server_url, token, self._series_browser_series_id, season_id,
        ))

    def _on_series_browser_download(self):
        """Create and start download tasks for all selected episodes via DownloadController."""
        # Sync check states first
        self._sync_check_states_to_selection()

        selected_ids = list(self._series_browser_selected_episode_ids)
        if not selected_ids:
            QMessageBox.information(self, DLG_NO_EPISODES, DLG_NO_EPISODES_MSG)
            return

        token = get_token(self.config)
        if not token:
            QMessageBox.warning(self, DLG_NOT_LOGGED_IN, DLG_NOT_LOGGED_IN_MSG)
            return
        download_dir = self._get_download_dir_from_ui()
        if not download_dir:
            QMessageBox.warning(self, DLG_MISSING_DIR, DLG_MISSING_DIR_MSG)
            return

        self.btn_sb_download.setEnabled(False)
        self.btn_sb_download.setText(BTN_CREATING_TASKS)
        self.log.append_log("INFO", f"Creating {len(selected_ids)} episode download task(s)...")

        # Build task metadata for each episode (DB reads are fast, fine in main thread)
        tasks_to_create = []
        skipped = 0
        for ep_id in selected_ids:
            ep_meta = self._find_episode_meta(ep_id)
            if ep_meta is None:
                self.log.append_log("WARNING", f"Episode {ep_id} metadata not found in cache. Skipped.")
                skipped += 1
                continue

            from app.core.naming import build_episode_filename
            series_name = ep_meta.get("series_name", self._series_browser_series_name)
            sn = ep_meta.get("season_number", 0)
            en = ep_meta.get("episode_number", 0)
            ep_title = ep_meta.get("name", "")
            display_title = build_episode_filename(series_name, sn, en, ep_title, "mkv")
            if display_title.endswith(".mkv"):
                display_title = display_title[:-4]

            tasks_to_create.append({
                "item_id": ep_id,
                "display_title": display_title,
                "media_type": "Episode",
                "series_id": ep_meta.get("series_id", self._series_browser_series_id),
                "season_id": ep_meta.get("season_id", ""),
                "episode_id": ep_id,
                "season_number": sn,
                "episode_number": en,
                "parent_title": series_name,
            })

        if not tasks_to_create:
            self.btn_sb_download.setEnabled(True)
            self.btn_sb_download.setText(BTN_DOWNLOAD_SELECTED)
            self.log.append_log("WARNING", "No valid episodes to download.")
            return

        # Create tasks in background, then start them
        self._series_create_queue = tasks_to_create
        self._series_created_count = 0
        self._series_created_task_ids = []
        self._series_create_idx = 0
        self._series_download_dir = download_dir
        self._series_create_next()

    def _series_create_next(self):
        """Create next episode task as pending, then proceed to next."""
        if self._series_create_idx >= len(self._series_create_queue):
            # All created
            task_ids = self._series_created_task_ids
            count = len(task_ids)
            self.btn_sb_download.setEnabled(True)
            self.btn_sb_download.setText(BTN_DOWNLOAD_SELECTED)
            skipped = len(self._series_create_queue) - count
            self.log.append_log("OK",
                f"Created {count} episode task(s). Skipped {skipped} duplicate(s).")
            self.sb_episode_status.setText(
                f"Created {count} task(s). Go to Tasks tab to start.")
            if count > 0:
                self.tabs.setCurrentIndex(4)
                self._refresh_tasks()
                self.log.append_log("OK", f"Created {count} pending task(s). Use Tasks tab to start downloads.")
            else:
                self.tabs.setCurrentIndex(4)
                self._refresh_tasks()
            return
        metadata = self._series_create_queue[self._series_create_idx]
        self._series_create_idx += 1
        try:
            from app.downloader.task_store import create_task
            ep_id = metadata["item_id"]
            task = create_task(
                item_id=ep_id,
                title=metadata["display_title"],
                media_type=metadata["media_type"],
                series_id=metadata.get("series_id", ""),
                season_id=metadata.get("season_id", ""),
                episode_id=ep_id,
                season_number=metadata.get("season_number"),
                episode_number=metadata.get("episode_number"),
                parent_title=metadata.get("parent_title", ""),
                display_title=metadata["display_title"],
            )
            self._on_series_task_created({"task_id": task.task_id} if task else {}, metadata)
        except Exception as e:
            self.log.append_log("ERROR", f"Failed to create task for {ep_id}: {e}")
            self._on_series_task_create_error(str(e), metadata)

    def _on_series_task_created(self, result, metadata):
        """Called when a single episode task is created via backend."""
        task_id = result.get("task_id", "") if isinstance(result, dict) else ""
        if task_id:
            self._series_created_task_ids.append(task_id)
            self._series_created_count += 1
        else:
            self.log.append_log("WARNING",
                f"Episode {metadata['item_id']} already has tasks or failed to create.")
        self._series_create_next()

    def _on_series_task_create_error(self, message: str, metadata):
        """Called when a single episode task creation fails."""
        self.log.append_log("ERROR",
            f"Failed to create task for episode {metadata['item_id']}: {message}")
        self._series_create_next()

    def _series_start_next(self):
        """Start next episode download via sync controller call."""
        if self._series_start_idx >= len(self._series_created_task_ids):
            self.tabs.setCurrentIndex(4)
            self._refresh_tasks()
            self.log.append_log("OK", f"Started {self._series_start_count} episode download(s).")
            return
        task_id = self._series_created_task_ids[self._series_start_idx]
        self._series_start_idx += 1
        download_dir = self._series_download_dir
        task = get_task(task_id)
        if task:
            self._download_controller.start_task(
                item_id=task.item_id,
                download_dir=download_dir,
                existing_task_id=task_id,
            )
        self._on_series_task_started({}, task_id)

    def _on_series_task_started(self, result, task_id: str):
        if isinstance(result, dict) and result.get("error"):
            self.log.append_log("ERROR", f"Failed to start episode task {task_id}: {result["error"]}")
        else:
            self._series_start_count += 1
        self._series_start_next()


    def _on_series_task_start_error(self, message: str, task_id: str):
        self.log.append_log("ERROR", f"Failed to start episode task {task_id}: {message}")
        self._series_start_next()

    def _find_episode_meta(self, ep_id: str) -> dict | None:
        """Find episode metadata dict from all cached seasons."""
        for episodes in self._series_browser_episode_cache.values():
            for ep in episodes:
                if ep.get("item_id") == ep_id:
                    return ep
        return None

    # ======== Tab 5: Tasks ========

    def _init_tasks_tab(self):
        """Initialize the Tasks tab with sidebar, table, and detail panel."""
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(4, 4, 4, 4)

        # 1. Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)

        self.btn_start_selected = QPushButton(BTN_START_SELECTED)
        self.btn_start_selected.setObjectName("task_start_button")
        self.btn_start_selected.setToolTip("Start selected pending tasks")
        self.btn_start_selected.clicked.connect(self._on_start_selected)
        toolbar.addWidget(self.btn_start_selected)

        self.btn_pause_selected = QPushButton(BTN_PAUSE_SELECTED)
        self.btn_pause_selected.setObjectName("task_pause_button")
        self.btn_pause_selected.setToolTip("Pause selected downloading tasks")
        self.btn_pause_selected.clicked.connect(self._on_pause_selected)
        toolbar.addWidget(self.btn_pause_selected)

        self.btn_resume_selected = QPushButton(BTN_RESUME_SELECTED)
        self.btn_resume_selected.setObjectName("task_resume_button")
        self.btn_resume_selected.setToolTip("Resume selected paused/failed tasks")
        self.btn_resume_selected.clicked.connect(self._on_resume_selected)
        toolbar.addWidget(self.btn_resume_selected)

        self.btn_cancel_selected = QPushButton(BTN_CANCEL_SELECTED)
        self.btn_cancel_selected.setObjectName("task_cancel_button")
        self.btn_cancel_selected.setToolTip("Cancel selected tasks")
        self.btn_cancel_selected.clicked.connect(self._on_cancel_selected)
        toolbar.addWidget(self.btn_cancel_selected)

        self.btn_delete_selected = QPushButton(BTN_DELETE_SELECTED)
        self.btn_delete_selected.setObjectName("task_delete_button")
        self.btn_delete_selected.setToolTip("Delete selected task records")
        self.btn_delete_selected.clicked.connect(self._on_delete_selected)
        toolbar.addWidget(self.btn_delete_selected)

        self.btn_open_folder = QPushButton(BTN_OPEN_FOLDER)
        self.btn_open_folder.setObjectName("task_open_folder_button")
        self.btn_open_folder.setToolTip("Open folder of selected task")
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        toolbar.addWidget(self.btn_open_folder)

        self.btn_refresh_tasks = QPushButton(BTN_REFRESH_TASKS)
        self.btn_refresh_tasks.setObjectName("task_refresh_button")
        self.btn_refresh_tasks.setToolTip("Refresh task list")
        self.btn_refresh_tasks.clicked.connect(self._refresh_tasks)
        toolbar.addWidget(self.btn_refresh_tasks)

        self.btn_clean_completed = QPushButton(BTN_CLEAN_COMPLETED)
        self.btn_clean_completed.setObjectName("task_clean_completed_button")
        self.btn_clean_completed.setToolTip("Delete all completed task records")
        self.btn_clean_completed.clicked.connect(self._on_clean_completed)
        toolbar.addWidget(self.btn_clean_completed)

        toolbar.addStretch()

        self.tasks_search_input = QLineEdit()
        self.tasks_search_input.setObjectName("task_search_input")
        self.tasks_search_input.setPlaceholderText(PLACEHOLDER_TASK_SEARCH)
        self.tasks_search_input.setMaximumWidth(220)
        self.tasks_search_input.setClearButtonEnabled(True)
        self.tasks_search_input.textChanged.connect(self._on_tasks_search_changed)
        toolbar.addWidget(self.tasks_search_input)

        outer.addLayout(toolbar)

        # 2. Splitter: left sidebar + right panel
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 2a. Left sidebar: status filter
        self.tasks_sidebar = QListWidget()
        self.tasks_sidebar.setObjectName("tasks_sidebar")
        self.tasks_sidebar.setMaximumWidth(200)
        self.tasks_sidebar.setMinimumWidth(100)
        splitter.addWidget(self.tasks_sidebar)

        # 2b. Right side: task table + detail panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)

        # Task table
        self.task_table = QTableWidget()
        self.task_table.setObjectName("task_table")
        self.task_table.setColumnCount(11)
        self.task_table.setHorizontalHeaderLabels([
            COL_TASK_ID, COL_TASK_TITLE, COL_TASK_ITEM_ID, COL_TASK_STATUS,
            COL_TASK_PROGRESS, COL_TASK_DOWNLOADED, COL_TASK_TOTAL,
            COL_TASK_SPEED, COL_TASK_ETA, COL_TASK_UPDATED, COL_TASK_SAVE_PATH,
        ])
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.task_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.task_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setSortingEnabled(True)
        self.task_table.horizontalHeader().setStretchLastSection(True)
        self.task_table.setColumnHidden(0, True)  # hide task_id column
        self.task_table.setColumnHidden(2, True)  # hide item_id column
        self.task_table.setColumnHidden(10, True)  # hide save_path column
        self.task_table.setColumnWidth(1, 200)  # title
        self.task_table.setColumnWidth(3, 80)   # status
        self.task_table.setColumnWidth(4, 70)   # progress
        self.task_table.setColumnWidth(5, 80)   # downloaded
        self.task_table.setColumnWidth(6, 80)   # total
        self.task_table.setColumnWidth(7, 70)   # speed
        self.task_table.setColumnWidth(8, 70)   # eta
        self.task_table.setColumnWidth(9, 120)  # updated
        self.task_table.itemSelectionChanged.connect(self._on_task_selection_changed)
        self.task_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_table.customContextMenuRequested.connect(self._on_task_table_context_menu)
        right_layout.addWidget(self.task_table)

        # Detail panel (stacked widget with overview/error/log pages)
        self.task_detail_stack = QStackedWidget()

        # Detail page 0: Overview
        self.detail_overview = QWidget()
        do_layout = QFormLayout(self.detail_overview)
        do_layout.setContentsMargins(4, 4, 4, 4)
        self.detail_lbl_title = QLabel(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_status = QLabel(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_progress = QLabel("0 %")
        self.detail_lbl_save_path = QLabel(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_filename = QLabel(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_task_id = QLabel(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_item_id = QLabel(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_type = QLabel(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_series_info = QLabel(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_created = QLabel(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_updated = QLabel(DETAIL_LBL_UNKNOWN)
        do_layout.addRow(DETAIL_LBL_TITLE, self.detail_lbl_title)
        do_layout.addRow(DETAIL_LBL_STATUS, self.detail_lbl_status)
        do_layout.addRow(DETAIL_LBL_PROGRESS, self.detail_lbl_progress)
        do_layout.addRow(DETAIL_LBL_SAVE_PATH, self.detail_lbl_save_path)
        do_layout.addRow(DETAIL_LBL_FILENAME, self.detail_lbl_filename)
        do_layout.addRow(DETAIL_LBL_TASK_ID, self.detail_lbl_task_id)
        do_layout.addRow(DETAIL_LBL_ITEM_ID, self.detail_lbl_item_id)
        do_layout.addRow(DETAIL_LBL_TYPE, self.detail_lbl_type)
        do_layout.addRow(DETAIL_LBL_SERIES_INFO, self.detail_lbl_series_info)
        do_layout.addRow(DETAIL_LBL_CREATED, self.detail_lbl_created)
        do_layout.addRow(DETAIL_LBL_UPDATED, self.detail_lbl_updated)
        self.task_detail_stack.addWidget(self.detail_overview)

        # Detail page 1: Error
        self.detail_error_page = QWidget()
        de_layout = QVBoxLayout(self.detail_error_page)
        self.detail_error_text = QLabel(DETAIL_LBL_NO_ERROR)
        self.detail_error_text.setWordWrap(True)
        self.detail_error_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        de_layout.addWidget(self.detail_error_text)
        de_layout.addStretch()
        self.task_detail_stack.addWidget(self.detail_error_page)

        # Detail page 2: Log
        self.detail_log_page = QWidget()
        dl_layout = QVBoxLayout(self.detail_log_page)
        dl_layout.addWidget(self.log)
        self.task_detail_stack.addWidget(self.detail_log_page)

        self.task_detail_stack.setCurrentIndex(0)
        self.task_detail_stack.setMaximumHeight(200)
        right_layout.addWidget(self.task_detail_stack)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([180, 720])

        outer.addWidget(splitter, 1)

        # 3. Populate sidebar status filter items
        self._populate_tasks_sidebar()

        # 4. Initial load
        QTimer.singleShot(100, self._refresh_tasks)
        self.tabs.addTab(widget, TAB_TASKS)

    def _populate_tasks_sidebar(self):
        """Populate sidebar status filter items."""
        # Add filter items
        filters = [
            (FILTER_ALL, SIDEBAR_ALL),
            (FILTER_DOWNLOADING, SIDEBAR_DOWNLOADING),
            (FILTER_PREPARING, SIDEBAR_PREPARING),
            (FILTER_PENDING, SIDEBAR_PENDING),
            (FILTER_PAUSED, SIDEBAR_PAUSED),
            (FILTER_COMPLETED, SIDEBAR_COMPLETED),
            (FILTER_FAILED, SIDEBAR_FAILED),
            (FILTER_CANCELLED, SIDEBAR_CANCELLED),
        ]
        for status_val, label in filters:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, status_val)
            self.tasks_sidebar.addItem(item)
        self.tasks_sidebar.setCurrentRow(0)
        self.tasks_sidebar.currentRowChanged.connect(self._on_sidebar_filter_changed)

    def _on_sidebar_filter_changed(self, row: int):
        """Refresh task list when sidebar filter changes."""
        self._refresh_tasks()

    def _get_selected_task_ids(self) -> list[str]:
        """Get task_ids for all selected rows in the task table."""
        task_ids = []
        for item in self.task_table.selectedItems():
            row = item.row()
            id_item = self.task_table.item(row, 0)
            if id_item is not None:
                tid = id_item.data(Qt.ItemDataRole.UserRole)
                if tid:
                    task_ids.append(tid)
        return list(dict.fromkeys(task_ids))  # deduplicate by row

    def _on_task_selection_changed(self):
        """Update detail panel when task selection changes."""
        task_ids = self._get_selected_task_ids()
        if len(task_ids) == 1:
            self._update_task_detail_panel(task_ids[0])
        else:
            self._clear_task_detail_panel()

    def _update_task_detail_panel(self, task_id: str):
        """Show task details in the detail panel."""
        task = get_task(task_id)
        if task is None:
            self._clear_task_detail_panel()
            return

        self.detail_lbl_title.setText(task.display_title or task.title or DETAIL_LBL_UNKNOWN)
        self.detail_lbl_status.setText(status_text(task.status))
        pct = format_progress_pct(task.downloaded_bytes, task.total_bytes)
        self.detail_lbl_progress.setText(pct)
        self.detail_lbl_save_path.setText(task.save_path or "--")
        self.detail_lbl_filename.setText(
            _os.path.basename(task.save_path) if task.save_path else "--"
        )
        self.detail_lbl_task_id.setText(task.task_id or "--")
        self.detail_lbl_item_id.setText(task.item_id or "--")
        self.detail_lbl_type.setText(status_text(task.media_type) if task.media_type else "--")
        series_info = ""
        if task.parent_title:
            series_info = task.parent_title
            if task.season_number is not None:
                series_info += f" S{task.season_number:02d}"
            if task.episode_number is not None:
                series_info += f"E{task.episode_number:02d}"
        self.detail_lbl_series_info.setText(series_info or DETAIL_LBL_UNKNOWN)
        self.detail_lbl_created.setText(
            format_updated_at(task.created_at) if task.created_at else "--"
        )
        self.detail_lbl_updated.setText(
            format_updated_at(task.updated_at) if task.updated_at else "--"
        )

        # Update error page
        if task.status == "failed" and task.error_message:
            self.detail_error_text.setText(task.error_message)
        else:
            self.detail_error_text.setText(DETAIL_LBL_NO_ERROR)

        self.task_detail_stack.setCurrentIndex(0)

    def _clear_task_detail_panel(self):
        """Reset detail panel to empty state."""
        self.detail_lbl_title.setText(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_status.setText(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_progress.setText("0 %")
        self.detail_lbl_save_path.setText("--")
        self.detail_lbl_filename.setText("--")
        self.detail_lbl_task_id.setText("--")
        self.detail_lbl_item_id.setText("--")
        self.detail_lbl_type.setText("--")
        self.detail_lbl_series_info.setText(DETAIL_LBL_UNKNOWN)
        self.detail_lbl_created.setText("--")
        self.detail_lbl_updated.setText("--")
        self.detail_error_text.setText(DETAIL_LBL_NO_ERROR)

    def _refresh_tasks(self):
        """Reload task list from DB and refresh table rows."""
        # Guard against stale calls after widget destruction
        try:
            _ = self.tasks_sidebar.count()
        except RuntimeError:
            return  # Widget already destroyed, ignore

        tasks = db_list_tasks()

        # Get current sidebar filter
        current_filter = ""
        sidebar_row = self.tasks_sidebar.currentRow()
        if sidebar_row >= 0:
            item = self.tasks_sidebar.item(sidebar_row)
            if item is not None:
                current_filter = item.data(Qt.ItemDataRole.UserRole) or ""

        # Get search text
        search_text = self.tasks_search_input.text().strip().lower()

        # Filter tasks
        if current_filter and current_filter != FILTER_ALL:
            tasks = [t for t in tasks if t.status == current_filter]
        if search_text:
            tasks = [
                t for t in tasks
                if search_text in (t.title or "").lower()
                or search_text in (t.display_title or "").lower()
                or search_text in (t.item_id or "").lower()
                or search_text in (t.task_id or "").lower()
            ]

        # Update sidebar counts
        self._update_sidebar_counts()

        # Populate table
        self.task_table.setRowCount(0)
        self.task_table.setSortingEnabled(False)
        self._task_row_index.clear()

        for row_idx, task in enumerate(tasks):
            self.task_table.insertRow(row_idx)
            # Column 0: task_id (hidden)
            id_item = QTableWidgetItem(task.task_id)
            id_item.setData(Qt.ItemDataRole.UserRole, task.task_id)
            self.task_table.setItem(row_idx, 0, id_item)
            # Column 1: title
            title = task.display_title or task.title or ""
            self.task_table.setItem(row_idx, 1, QTableWidgetItem(title))
            # Column 2: item_id (hidden)
            self.task_table.setItem(row_idx, 2, QTableWidgetItem(task.item_id or ""))
            # Column 3: status
            status_str = status_text(task.status)
            status_item = QTableWidgetItem(status_str)
            self.task_table.setItem(row_idx, 3, status_item)
            # Column 4: progress
            pct = format_progress_pct(task.downloaded_bytes, task.total_bytes)
            self.task_table.setItem(row_idx, 4, QTableWidgetItem(pct))
            # Column 5: downloaded
            dl_str = format_bytes(task.downloaded_bytes) if task.downloaded_bytes else "0 B"
            self.task_table.setItem(row_idx, 5, QTableWidgetItem(dl_str))
            # Column 6: total
            tot_str = format_bytes(task.total_bytes) if task.total_bytes else "?"
            self.task_table.setItem(row_idx, 6, QTableWidgetItem(tot_str))
            # Column 7: speed
            self.task_table.setItem(row_idx, 7, QTableWidgetItem("--"))
            # Column 8: eta
            self.task_table.setItem(row_idx, 8, QTableWidgetItem("--"))
            # Column 9: updated
            updated_str = format_updated_at(task.updated_at) if task.updated_at else "--"
            self.task_table.setItem(row_idx, 9, QTableWidgetItem(updated_str))
            # Column 10: save_path (hidden)
            self.task_table.setItem(row_idx, 10, QTableWidgetItem(task.save_path or ""))

            # Cache row index
            self._task_row_index[task.task_id] = row_idx

        self.task_table.setSortingEnabled(True)

    def _update_sidebar_counts(self):
        """Update status counts in sidebar labels."""
        tasks = db_list_tasks()
        all_count = len(tasks)
        counts: dict[str, int] = {}
        for t in tasks:
            counts[t.status] = counts.get(t.status, 0) + 1

        for row in range(self.tasks_sidebar.count()):
            item = self.tasks_sidebar.item(row)
            if item is None:
                continue
            status_val = item.data(Qt.ItemDataRole.UserRole) or ""
            if status_val == FILTER_ALL:
                item.setText(f"{SIDEBAR_ALL} ({all_count})")
            else:
                cnt = counts.get(status_val, 0)
                # Find the label text from constants
                label_map = {
                    FILTER_DOWNLOADING: SIDEBAR_DOWNLOADING,
                    FILTER_PREPARING: SIDEBAR_PREPARING,
                    FILTER_PENDING: SIDEBAR_PENDING,
                    FILTER_PAUSED: SIDEBAR_PAUSED,
                    FILTER_COMPLETED: SIDEBAR_COMPLETED,
                    FILTER_FAILED: SIDEBAR_FAILED,
                    FILTER_CANCELLED: SIDEBAR_CANCELLED,
                }
                label = label_map.get(status_val, status_val)
                item.setText(f"{label} ({cnt})")

    def _update_task_row(self, task_id: str, downloaded: int, total: int | None, speed: float):
        """Update a single task row with latest progress."""
        row = self._task_row_index.get(task_id)
        if row is None or row < 0 or row >= self.task_table.rowCount():
            # Row index stale - rebuild table and retry
            self._refresh_tasks()
            row = self._task_row_index.get(task_id)
            if row is None:
                return

        pct = format_progress_pct(downloaded, total)
        dl_str = format_bytes(downloaded)
        tot_str = format_bytes(total) if total else "?"
        spd_str = format_speed_gui(speed) if speed > 0 else "--"
        eta_str = "--"
        if speed > 0 and total and total > downloaded:
            eta_sec = (total - downloaded) / speed
            eta_str = format_eta(eta_sec)

        # Update only the cell values that change
        self.task_table.item(row, 4).setText(pct)
        self.task_table.item(row, 5).setText(dl_str)
        self.task_table.item(row, 6).setText(tot_str)
        self.task_table.item(row, 7).setText(spd_str)
        self.task_table.item(row, 8).setText(eta_str)
        self.task_table.item(row, 9).setText(format_updated_at(None))

    def _get_download_dir_from_sidebar(self) -> str:
        """Get download directory from config or UI."""
        cfg = load_config(self.config_path)
        if cfg.download_dir:
            return cfg.download_dir
        return self._get_download_dir_from_ui()

    # ==== Task toolbar button handlers ====

    def _set_task_action_buttons_enabled(self, enabled: bool):
        """Enable or disable task action buttons to prevent double-click."""
        for attr in ("btn_start_selected", "btn_pause_selected", "btn_resume_selected",
                     "btn_cancel_selected", "btn_delete_selected"):
            btn = getattr(self, attr, None)
            if btn is not None:
                btn.setEnabled(enabled)

    def _start_or_resume_task(self, task_id: str, download_dir: str, reason: str = ""):
        """Start or resume a task via sync controller call.
        
        Args:
            task_id: The task to start/resume.
            download_dir: Download directory.
            reason: Log label (e.g. "start", "resume").
        """
        task = get_task(task_id)
        if task is None:
            self.log.append_log("WARNING", f"{reason.capitalize()}: task {task_id[:8]}... not found")
            return
        status = task.status
        self.log.append_log("INFO", f"{reason.capitalize()} request: task_id={task_id[:8]}... status={status}")
        if status in ("pending", "paused", "failed"):
            self._download_controller.start_task(
                item_id=task.item_id,
                download_dir=download_dir,
                existing_task_id=task_id,
            )
            self._on_task_action_done(task_id, {}, reason)
        else:
            self.log.append_log("INFO", f"{reason.capitalize()} skipped: task {task_id[:8]}... is {status}")

    def _on_start_selected(self):
        """Start selected pending/paused/failed tasks."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            QMessageBox.information(self, DLG_NO_SELECTION, DLG_NO_SELECTION_MSG)
            return
        download_dir = self._get_download_dir_from_ui()
        if not download_dir:
            download_dir = self._get_download_dir_from_sidebar()
        if not download_dir:
            QMessageBox.warning(self, DLG_MISSING_DIR, DLG_MISSING_DIR_MSG)
            return

        for tid in task_ids:
            task = get_task(tid)
            if task is None:
                continue
            if task.status not in ("pending", "paused", "failed"):
                continue
            self.log.append_log("INFO", f"Starting task {tid[:8]}...")
            # Direct sync call to controller
            self._download_controller.start_task(
                item_id=task.item_id,
                download_dir=download_dir,
                existing_task_id=tid,
            )
            self._on_task_action_done(tid, {}, "start")

    def _on_pause_selected(self):
        """Pause selected downloading tasks."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            return
        for tid in task_ids:
            task = get_task(tid)
            if task is None or task.status != "downloading":
                continue
            self.log.append_log("INFO", f"Pausing task {tid[:8]}...")
            self._download_controller.pause_task(tid)
            self._on_task_action_done(tid, {}, "pause")

    def _on_resume_selected(self):
        """Resume selected paused tasks."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            return
        download_dir = self._get_download_dir_from_ui()
        if not download_dir:
            download_dir = self._get_download_dir_from_sidebar()
        if not download_dir:
            QMessageBox.warning(self, DLG_MISSING_DIR, DLG_MISSING_DIR_MSG)
            return
        for tid in task_ids:
            task = get_task(tid)
            if task is None or task.status != "paused":
                continue
            self.log.append_log("INFO", f"Resuming task {tid[:8]}...")
            self._download_controller.resume_task(tid, download_dir)
            self._on_task_action_done(tid, {}, "resume")

    def _on_cancel_selected(self):
        """Cancel selected tasks."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            return
        for tid in task_ids:
            task = get_task(tid)
            if task is None or task.status in ("completed", "cancelled"):
                continue
            self.log.append_log("INFO", f"Cancelling task {tid[:8]}...")
            self._download_controller.cancel_task(tid)
            self._on_task_action_done(tid, {}, "cancel")

    def _on_task_action_done(self, task_id: str, result, action: str):
        """Generic handler for task action completion."""
        if isinstance(result, dict) and result.get("error"):
            self.log.append_log("ERROR", f"{action} failed for {task_id[:8]}...: {result['error']}")
        else:
            self.log.append_log("OK", f"{action} success for {task_id[:8]}...")
        self._refresh_tasks()

    def _on_task_action_error(self, task_id: str, message: str, action: str):
        """Generic handler for task action error."""
        self.log.append_log("ERROR", f"{action} error for {task_id[:8]}...: {message}")
        self._refresh_tasks()

    def _on_delete_selected(self):
        """Delete selected task records."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            return
        # Check if any are active
        active = False
        for tid in task_ids:
            task = get_task(tid)
            if task and task.status in ("downloading", "preparing"):
                active = True
                break
        if active:
            reply = QMessageBox.question(
                self, DLG_DELETE_TITLE, DLG_DELETE_ACTIVE,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        reply = QMessageBox.question(
            self, DLG_DELETE_TITLE, DLG_DELETE_MSG,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for tid in task_ids:
            db_delete_task(tid)
        self.log.append_log("INFO", f"Deleted {len(task_ids)} task(s)")
        self._refresh_tasks()

    def _on_open_folder(self):
        """Open the folder containing the selected task's download."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            QMessageBox.information(self, DLG_NO_SELECTION, DLG_NO_SELECTION_MSG)
            return
        task = get_task(task_ids[0])
        if task is None or not task.save_path:
            QMessageBox.information(self, DLG_NO_PATH, DLG_NO_PATH_MSG)
            return
        folder = _os.path.dirname(task.save_path)
        if not _os.path.isdir(folder):
            QMessageBox.warning(self, DLG_PATH_NOT_FOUND, DLG_PATH_NOT_FOUND_MSG)
            return
        try:
            _os.startfile(folder)
        except Exception as e:
            QMessageBox.warning(self, DLG_OPEN_FOLDER_ERROR, str(e))

    def _on_clean_completed(self):
        """Delete all completed task records."""
        tasks = db_list_tasks()
        completed = [t for t in tasks if t.status == "completed"]
        if not completed:
            QMessageBox.information(self, DLG_CLEAN_TITLE, DLG_CLEAN_NONE)
            return
        reply = QMessageBox.question(
            self, DLG_CLEAN_TITLE, DLG_CLEAN_MSG,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for t in completed:
            db_delete_task(t.task_id)
        self.log.append_log("INFO", f"Cleaned {len(completed)} completed task(s)")
        self._refresh_tasks()

    def _on_tasks_search_changed(self, text: str):
        """Filter task list by search text."""
        self._refresh_tasks()

    def _on_task_table_context_menu(self, pos):
        """Right-click context menu for task table."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            return
        menu = QMenu(self)
        task = get_task(task_ids[0])
        status = task.status if task else ""

        if status in ("pending", "paused", "failed"):
            action_start = menu.addAction(MENU_START)
            action_start.triggered.connect(self._on_start_selected)
        if status == "downloading":
            action_pause = menu.addAction(MENU_PAUSE)
            action_pause.triggered.connect(self._on_pause_selected)
        if status == "paused":
            action_resume = menu.addAction(MENU_RESUME)
            action_resume.triggered.connect(self._on_resume_selected)
        if status not in ("completed", "cancelled"):
            action_cancel = menu.addAction(MENU_CANCEL)
            action_cancel.triggered.connect(self._on_cancel_selected)

        menu.addSeparator()
        action_delete = menu.addAction(MENU_DELETE)
        action_delete.triggered.connect(self._on_delete_selected)
        action_open = menu.addAction(MENU_OPEN_FOLDER)
        action_open.triggered.connect(self._on_open_folder)

        menu.addSeparator()
        action_copy_title = menu.addAction(MENU_COPY_TITLE)
        action_copy_title.triggered.connect(self._on_copy_task_title)
        action_copy_path = menu.addAction(MENU_COPY_PATH)
        action_copy_path.triggered.connect(self._on_copy_task_path)
        action_show_error = menu.addAction(MENU_SHOW_ERROR)
        action_show_error.triggered.connect(self._on_show_error)

        menu.exec(self.task_table.viewport().mapToGlobal(pos))

    def _on_show_error(self):
        """Show error message for selected task."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            QMessageBox.information(self, DLG_NO_ERROR, DLG_NO_ERROR_MSG)
            return
        task = get_task(task_ids[0])
        if task is None or not task.error_message:
            QMessageBox.information(self, DLG_NO_ERROR, DLG_NO_ERROR_MSG)
            return
        QMessageBox.warning(self, f"{MENU_SHOW_ERROR} - {task.title}", task.error_message)

    def _on_copy_task_title(self):
        """Copy task title to clipboard."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            return
        task = get_task(task_ids[0])
        if task is None:
            return
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(task.title)
        self.log.append_log("OK", f"Copied title: {task.title}")

    def _on_copy_task_path(self):
        """Copy task save path to clipboard."""
        task_ids = self._get_selected_task_ids()
        if not task_ids:
            return
        task = get_task(task_ids[0])
        if task is None or not task.save_path:
            return
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(task.save_path)
        self.log.append_log("OK", f"Copied path: {task.save_path}")

    def _on_worker_error(self, message: str):
        """Handle worker error signal with sensitive info redaction."""
        from app.utils.redaction import redact_sensitive
        redacted = redact_sensitive(message)
        self.log.append_log("ERROR", redacted)
