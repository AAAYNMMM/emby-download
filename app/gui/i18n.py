"""
GUI Chinese localization constants.

All user-visible GUI text is defined here so that it can be easily
reviewed and updated.  CLI output is deliberately kept in ASCII to
avoid Windows GBK encoding issues.
"""

from __future__ import annotations

# ============================================================================
# Tab names
# ============================================================================

TAB_LOGIN = "登录 / 配置"
TAB_SEARCH = "电影"
TAB_PREVIEW = "预览"
TAB_SERIES = "剧集"
TAB_TASKS = "任务"
TAB_LOGS = "日志"  # not a real tab; log widget is always visible

# ============================================================================
# Login / Config tab
# ============================================================================

GRP_SERVER = "服务器连接"
LBL_SERVER_URL = "服务器地址:"
LBL_USERNAME = "用户名:"
LBL_PASSWORD = "密码:"
BTN_LOGIN = "登录"
BTN_PING = "测试连接"
BTN_WHOAMI = "当前用户"
GRP_DOWNLOAD_DIR = "下载目录"
BTN_BROWSE = "浏览…"
BTN_SAVE_DIR = "保存"
PLACEHOLDER_SERVER = "http://192.168.1.100:8096"
PLACEHOLDER_USERNAME = "your_username"
PLACEHOLDER_PASSWORD = "password"
PLACEHOLDER_DOWNLOAD_DIR = "下载前请先选择下载目录"

# ============================================================================
# Search tab
# ============================================================================

PLACEHOLDER_SEARCH = "搜索电影或剧集…"
LBL_LIMIT = "数量:"
BTN_SEARCH = "搜索"

# Search result table headers
COL_ID = "ID"
COL_TITLE = "标题"
COL_INFO = "信息"
COL_TYPE = "类型"

# ============================================================================
# Preview tab
# ============================================================================

LBL_ITEM_ID = "项目ID:"
BTN_PREVIEW = "预览"
BTN_DOWNLOAD = "添加到任务"
GRP_PREVIEW = "下载预览"
LBL_PREVIEW_TITLE = "标题:"
LBL_PREVIEW_SIZE = "大小:"
LBL_PREVIEW_DURATION = "时长:"
LBL_PREVIEW_CONTAINER = "容器:"
LBL_PREVIEW_PROTOCOL = "协议:"
LBL_PREVIEW_METHOD = "方式:"
LBL_PREVIEW_STATUS = "状态:"
LBL_PREVIEW_REASON = "原因:"
LBL_PREVIEW_OUTPUT = "输出:"

# ============================================================================
# Series Browser tab
# ============================================================================

LBL_SERIES_TITLE = "未加载剧集"
LBL_SERIES_HINT = "在搜索结果中双击剧集，或在下方搜索"
LBL_SEASONS = "季:"
BTN_REFRESH_SEASONS = "刷新季"
BTN_REFRESH_EPISODES = "刷新集数"
BTN_SELECT_ALL_VISIBLE = "全选当前页"
BTN_CLEAR_VISIBLE = "清除当前页"
BTN_SELECT_SEASON = "选择整季"
BTN_CLEAR_SEASON = "清除整季"
BTN_DOWNLOAD_SELECTED = "添加到任务"
BTN_CREATING_TASKS = "创建任务中…"

# Series search area (new in Stage 10E)
PLACEHOLDER_SERIES_SEARCH = "搜索剧集"
BTN_SERIES_SEARCH = "搜索剧集"
LBL_SERIES_RESULTS = "剧集搜索结果"

# Series search result columns
COL_SERIES_NAME = "剧名"
COL_SERIES_YEAR = "年份"
COL_SERIES_ID = "剧集ID"

# ============================================================================
# Tasks tab
# ============================================================================

LBL_FILTER = "筛选:"
BTN_REFRESH_TASKS = "刷新"
BTN_START_SELECTED = "开始"
BTN_PAUSE_SELECTED = "暂停"
BTN_RESUME_SELECTED = "继续"
BTN_CANCEL_SELECTED = "取消"
BTN_DELETE_SELECTED = "删除记录"
BTN_OPEN_FOLDER = "打开文件夹"
BTN_SHOW_ERROR = "查看错误"
BTN_CLEAN_COMPLETED = "清理已完成"
PLACEHOLDER_TASK_SEARCH = "筛选任务标题 / Item ID"

# Tasks table headers (Stage 10F reduced set)
COL_TASK_ID = "任务ID"
COL_TASK_TITLE = "标题"
COL_TASK_ITEM_ID = "项目ID"
COL_TASK_STATUS = "状态"
COL_TASK_PROGRESS = "进度"
COL_TASK_DOWNLOADED = "已下载"
COL_TASK_TOTAL = "总大小"
COL_TASK_SPEED = "速度"
COL_TASK_ETA = "剩余时间"
COL_TASK_UPDATED = "更新时间"
COL_TASK_SAVE_PATH = "保存路径"
COL_TASK_LAST_ERROR = "最近错误"

# Task table Stage 10F compact columns
COL_TASK10F_TITLE = "标题"
COL_TASK10F_STATUS = "状态"
COL_TASK10F_PROGRESS = "进度"
COL_TASK10F_SIZE = "已下载 / 总大小"
COL_TASK10F_SPEED = "速度"
COL_TASK10F_ETA = "剩余时间"
COL_TASK10F_UPDATED = "更新时间"

# Filter options
FILTER_ALL = "全部"
FILTER_PENDING = "等待中"
FILTER_PREPARING = "准备中"
FILTER_DOWNLOADING = "下载中"
FILTER_PAUSED = "已暂停"
FILTER_COMPLETED = "已完成"
FILTER_FAILED = "失败"
FILTER_CANCELLED = "已取消"

# Sidebar filter labels with count template
SIDEBAR_ALL = "全部"
SIDEBAR_DOWNLOADING = "下载中"
SIDEBAR_PREPARING = "准备中"
SIDEBAR_PENDING = "等待中"
SIDEBAR_PAUSED = "已暂停"
SIDEBAR_COMPLETED = "已完成"
SIDEBAR_FAILED = "失败"
SIDEBAR_CANCELLED = "已取消"

# Detail panel tabs
DETAIL_TAB_OVERVIEW = "任务详情"
DETAIL_TAB_ERROR = "错误信息"
DETAIL_TAB_LOG = "日志"

# Detail panel labels
DETAIL_LBL_TITLE = "标题:"
DETAIL_LBL_STATUS = "状态:"
DETAIL_LBL_PROGRESS = "进度:"
DETAIL_LBL_SAVE_PATH = "保存路径:"
DETAIL_LBL_FILENAME = "文件名:"
DETAIL_LBL_TASK_ID = "Task ID:"
DETAIL_LBL_ITEM_ID = "Item ID:"
DETAIL_LBL_TYPE = "类型:"
DETAIL_LBL_SERIES_INFO = "剧集信息:"
DETAIL_LBL_CREATED = "创建时间:"
DETAIL_LBL_UPDATED = "更新时间:"
DETAIL_LBL_NO_ERROR = "没有错误信息"
DETAIL_LBL_UNKNOWN = "未知"

# Empty state
EMPTY_TASKS_TITLE = "暂无下载任务"
EMPTY_TASKS_HINT = "请在电影或剧集页面选择内容后点击下载"
EMPTY_TASKS_BTN = "去搜索"

# Delete confirmation
DLG_DELETE_TITLE = "删除任务记录"
DLG_DELETE_MSG = "只删除任务记录，不会删除已下载文件。\n\n是否继续？"
DLG_DELETE_ACTIVE = "任务正在下载中，请先暂停或取消后再删除。"
DLG_DELETED = "已删除 {count} 条任务记录。"

# Clean completed
DLG_CLEAN_TITLE = "清理已完成任务"
DLG_CLEAN_MSG = "将删除所有状态为「已完成」的任务记录。\n不会删除已下载的文件。\n\n是否继续？"
DLG_CLEAN_RESULT = "已清理 {count} 条已完成任务记录。"
DLG_CLEAN_NONE = "没有可清理的已完成任务。"

# Connection status (Stage 10F)
CONN_NOT_CONFIGURED = "未配置"
CONN_NOT_VERIFIED = "未验证"
CONN_SERVER_REACHABLE = "服务器可达"
CONN_TOKEN_EXPIRED = "登录失效"

# Right-click menu additions
MENU_START = "开始"
MENU_COPY_TITLE = "复制标题"
MENU_COPY_PATH = "复制保存路径"

# ============================================================================
# Status texts (displayed in Tasks table & status bar)
# ============================================================================

STATUS_PENDING = "等待中"
STATUS_PREPARING = "准备中"
STATUS_DOWNLOADING = "下载中"
STATUS_PAUSED = "已暂停"
STATUS_COMPLETED = "已完成"
STATUS_FAILED = "失败"
STATUS_CANCELLED = "已取消"
STATUS_UNKNOWN = "未知"

def status_text(status: str) -> str:
    """Translate a status string to Chinese for GUI display."""
    mapping = {
        "pending": STATUS_PENDING,
        "preparing": STATUS_PREPARING,
        "downloading": STATUS_DOWNLOADING,
        "paused": STATUS_PAUSED,
        "completed": STATUS_COMPLETED,
        "failed": STATUS_FAILED,
        "cancelled": STATUS_CANCELLED,
    }
    return mapping.get(status, STATUS_UNKNOWN)

# ============================================================================
# Right-click context menu
# ============================================================================

MENU_PAUSE = "暂停"
MENU_RESUME = "继续"
MENU_CANCEL = "取消"
MENU_DELETE = "删除"
MENU_OPEN_FOLDER = "打开文件夹"
MENU_SHOW_ERROR = "查看错误"
MENU_REFRESH = "刷新"
MENU_EXPORT_LOG = "导出日志…"
MENU_CLEAR_LOG = "清空"

# ============================================================================
# Dialog / message box texts
# ============================================================================

DLG_MISSING_FIELDS = "信息不完整"
DLG_MISSING_FIELDS_MSG = "请填写服务器地址、用户名和密码。"
DLG_NOT_LOGGED_IN = "未登录"
DLG_NOT_LOGGED_IN_MSG = "请先登录。"
DLG_MISSING_DIR = "缺少下载目录"
DLG_MISSING_DIR_MSG = "请先选择下载目录。"
DLG_MISSING_SERVER = "缺少服务器地址"
DLG_MISSING_SERVER_MSG = "请先输入服务器地址。"
DLG_NO_SELECTION = "未选择"
DLG_NO_SELECTION_MSG = "请先选择一个或多个任务。"
DLG_SELECT_ONE = "请选择一个任务。"
DLG_NOT_FOUND = "未找到"
DLG_NOT_FOUND_MSG = "任务 {task_id} 未找到。"
DLG_NO_PATH = "无保存路径"
DLG_NO_PATH_MSG = "该任务没有记录保存路径。"
DLG_PATH_NOT_FOUND = "路径不存在"
DLG_PATH_NOT_FOUND_MSG = "目录不存在:\n{directory}"
DLG_NO_ERROR = "无错误"
DLG_NO_ERROR_MSG = "没有记录错误。"
DLG_UNKNOWN_TYPE = "未知类型"
DLG_UNKNOWN_TYPE_MSG = "项目类型 '{item_type}' 不支持下载。\n仅支持 Movie、Series 和 Episode 类型。"
DLG_ACTIVE_DOWNLOADS = "有活动的下载任务"
DLG_ACTIVE_DOWNLOADS_MSG = (
    "当前有正在进行的下载任务。请选择:\n\n"
    "暂停并退出: 暂停所有下载并退出。\n"
    "保持运行: 不要关闭，让下载继续运行。"
)
DLG_RESUME_CANCELLED = "恢复已取消的任务"
DLG_RESUME_CANCELLED_MSG = (
    "任务 {task_id} 已被取消。将其恢复为等待中?\n"
    "文件: {title}"
)
DLG_NO_EPISODES = "未选择剧集"
DLG_NO_EPISODES_MSG = "请先选择一个或多个剧集。"
DLG_NO_RESULTS = "没有找到结果。"
DLG_NO_SERIES_RESULTS = "没有找到剧集"
DLG_EMPTY_SERIES_SEARCH = "请输入剧集名称"
DLG_OPEN_FOLDER_ERROR = "无法打开文件夹"

# ============================================================================
# Status bar
# ============================================================================

STATUS_NOT_CONNECTED = "未连接"
STATUS_CONNECTED = "已连接"

# ============================================================================
# Log levels (already ASCII, but keep for completeness)
# ============================================================================

# Window title
WINDOW_TITLE = "EmbyD - Emby 下载客户端"

# ============================================================================
# Misc
# ============================================================================

STR_LOADING = "加载中…"
STR_UNKNOWN = "未知"
STR_STARTING = "启动中…"
STR_NO_SERIES_LOADED = "未加载剧集"
STR_DOUBLE_CLICK_HINT = "在搜索结果中双击剧集"
STR_LOADING_SEASONS = "加载季…"
STR_LOADING_EPISODES = "加载剧集…"
STR_NO_SEASONS = "没有找到季。"
STR_NO_SEASONS_AVAILABLE = "无可用的季。"
STR_CLICK_SEASON = " 个季。点击季以查看剧集。"
STR_SEASON_LOADED = " 个季已加载。"
STR_EPISODES_LOADED = " 剧集。共选中 "
STR_EPISODE = " 剧集"

BTN_BACK_TO_SEASONS = "<= 返回季列表"
