# EmbyD - Emby Download Client for Windows

EmbyD 是一个 Windows 平台的 Emby 下载客户端，用于在获得服务端授权的前提下，将你有权限访问的 Emby 电影/剧集下载到本地。

> **重要声明**
>
> 这是一个**授权下载工具**。它不会绕过权限、不会伪造凭证、不会规避服务端限制。
> 如果 Emby 服务端没有给你的账号下载/直流访问权限，程序会明确提示"无权限或服务器不支持"，
> 而不会尝试绕过。

## 功能特性

- 输入 Emby 服务器地址、用户名、密码登录
- 搜索电影和剧集单集、查看媒体详情
- 获取 PlaybackInfo / MediaSource 信息
- 判断下载能力（原文件下载 / Direct Stream）
- 单文件下载 + 进度显示
- 下载暂停/继续 + 断点续传（HTTP Range）
- 失败重试（3次 + 指数退避）
- 下载任务记录存储（SQLite）
- 基础文件命名清理
- 图形用户界面 (PySide6)
- 剧集单集搜索与 GUI 批量下载

## 快速开始

### 环境要求

- Windows 7+
- Python 3.10+

### 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 启动 GUI

```powershell
python -m app.gui.app
```

### 打包为独立 exe

```powershell
python scripts/build_exe.py
```

输出：`dist\embyd-gui.exe`

### 使用说明

1. **启动** `embyd-gui.exe`（或 `python -m app.gui.app`）
2. **配置服务器和账号** — 在登录页输入 Emby 服务器地址、用户名、密码，点击登录
3. **搜索电影** — 切换到搜索页，输入关键词搜索
4. **预览** — 双击搜索结果查看详情和下载能力
5. **选择版本** — 如有多个 MediaSource 可选择不同分辨率
6. **下载** — 点击下载按钮，文件将保存到设置的下载目录
7. **任务管理** — 在任务页可暂停/继续/取消下载

配置文件 `embyd_config.json` 和任务库 `tasks.db` 保存在软件当前所在目录。

## 项目结构

```
embyD/
├── app/                    # 主应用模块
│   ├── config/            # 配置管理
│   ├── core/              # 核心业务逻辑（Emby API、认证、PlaybackInfo）
│   ├── downloader/        # 下载器实现（Range 断点续传）
│   ├── gui/               # GUI 模块（PySide6）
│   ├── metadata/          # 文件命名清理
│   ├── storage/           # 数据库与持久化
│   └── utils/             # 通用工具
├── tests/                 # 测试
├── docs/                  # 文档
└── scripts/               # 构建辅助脚本
```

## 技术栈

- Python 3.10+
- GUI: PySide6
- HTTP: requests + aiohttp
- 存储: SQLite
- 加密: cryptography
- Token 安全存储: keyring

## GitHub 安全说明

提交到 GitHub 前请注意：

- 不要提交 `.env.local`（包含真实账号密码）
- 不要提交 `embyd_config.json`（包含真实 token）
- 不要提交 `tasks.db`（包含下载记录）
- 不要提交 `dist/`（构建产物）
- 不要提交 `.venv/`（虚拟环境）
- 不要提交 `*.log`（日志）
- 不要提交下载的视频文件

## 许可证

MIT
