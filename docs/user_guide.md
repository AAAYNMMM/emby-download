# EmbyD User Guide

**CLI 控制功能已移除，EmbyD 现在仅作为 GUI 客户端使用。**

## Installation

### Prerequisites
- Python 3.10+
- Windows 10/11

### Setup

```powershell
git clone <repo_url>
cd embyD
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Quick Start (GUI)

### 1. Start the GUI

From source:

```powershell
python -m app.gui.app
```

From packaged build:

```powershell
dist\embyd-gui.exe
```

### 2. Login to Emby Server

In the Login tab of the GUI:
1. Enter Emby Server URL
2. Enter username
3. Enter password
4. Click Login

The access token will be saved securely. Configuration is stored in `embyd_config.json` next to the running program. Download tasks are stored in `tasks.db`.

### 3. Search for Media

1. Go to the Search tab
2. Enter a movie or episode title
3. Click Search
4. Double-click a result to enter Preview

### 4. Preview and Download

1. In the Preview tab, review media details, size, and download method
2. Select a version if multiple MediaSources are available
3. Click Download
4. The file will be saved to your configured download directory

### 5. Task Management

1. Go to the Tasks tab
2. View all download tasks with progress and status
3. Pause / Resume / Cancel individual tasks
4. Clean up completed tasks

## Troubleshooting

### "No permission or server does not support downloads"
Check your Emby server user settings. The admin must enable "Allow download" for your account.

### "Failed to authenticate"
Verify your username and password. Check that the server URL is correct.

### Download fails mid-way
Use the Resume button in the Tasks tab. The `.part` file will be used for continuation.

### Speed is slow
Increase chunk_size in the config file.
