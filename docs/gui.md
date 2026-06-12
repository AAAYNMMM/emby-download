# EmbyD GUI Guide

EmbyD GUI is a PySide6 desktop client for authorized Emby downloads.

## Start From Source

```powershell
python -m app.gui.app
```

## Start Packaged GUI

```powershell
dist\embyd-gui.exe
```

## First Login

1. Open the Login tab.
2. Enter the Emby server URL, username, and password.
3. Click Login.
4. Choose a download directory in the Download Directory field. Click Save if you want to reuse it.
5. After login, use Ping and the automatic whoami check to confirm the server and account policy.

Passwords are not written to the GUI log. Tokens are stored through the existing encrypted config flow and are redacted from visible log text.

The config file is stored next to the running program:
- Source run: current project directory.
- Packaged run: the same directory as `embyd-gui.exe`.

## Search And Preview

1. Open the Search tab and enter a movie or episode title.
2. Double-click a result to move it into the Preview tab.
3. Click Preview to run the shared dry-run core logic.
4. Confirm method, size, output path, and whether the item is downloadable.

If there are no results, no token, or no download directory, the GUI should show a clear message instead of crashing.

## Download And Tasks

1. Run Preview first.
2. If the item is downloadable, click Download.
3. Watch the progress bar and speed label.
4. Use Pause to stop the current download and keep the `.part` file.
5. Use Continue to resume from the `.part` file.
6. Open the Tasks tab and click Refresh to inspect task state.

## Episodes Batch Download

1. Open the Series tab.
2. Search by series name.
3. Select a season and choose episodes.
4. Click Download Selected.

## Common Errors

| Error | Meaning | Action |
|---|---|---|
| 401 Unauthorized | Token invalid or expired | Login again |
| 403 Forbidden | Account lacks permission | Ask the server admin to enable access/download |
| 404 Not Found | Item ID is invalid or removed | Search again |
| SSL error | Certificate or HTTPS problem | Fix certificate or use correct URL |
| Timeout | Server/network is slow | Check network |
| Connection refused | Server not reachable | Verify Emby is running and URL is correct |
