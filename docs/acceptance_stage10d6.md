# EmbyD Stage 10D-6 验收报告

## 真实服务器验收辅助与重新打包

### 测试环境

- Emby 服务器版本：_______________
- Emby 服务器地址：_______________
- 测试网速：_______________________
- 测试账号（有下载权限）：________
- 测试日期：_______________________
- 测试人：_________________________

---

## 一、自动化测试结果

| 项目 | 结果 |
|------|------|
| pytest -q | 231 passed |
| CLI --help | OK |
| CLI doctor | OK |
| CLI config show | OK |
| CLI search | OK |
| CLI download --dry-run | OK (正确返回 404) |
| GUI smoke (QApplication + MainWindow) | OK (无 QThread warning) |

---

## 二、打包产物

| 文件 | 大小 | 说明 |
|------|------|------|
| dist/embyd.exe | ~16.9 MB | CLI (console 模式, --onefile) |
| dist/embyd-gui.exe | ~250 MB | GUI (windowed 模式, --onefile, --collect-all PySide6) |
| dist/README_TESTING.txt | ~2 KB | 手动测试说明 |

打包命令：

```powershell
python scripts/build_exe.py          # 构建 CLI + GUI
python scripts/build_exe.py --cli    # 仅 CLI
python scripts/build_exe.py --gui    # 仅 GUI
```

---

## 三、CLI 验收（打包版）

使用 `dist\embyd.exe` 进行测试。

| # | 测试项 | 命令 | 预期结果 | 实际结果 | 通过 |
|---|--------|------|----------|----------|------|
| 1 | --help | `dist\embyd.exe --help` | 显示所有子命令 | | |
| 2 | --version | `dist\embyd.exe --version` | 显示版本 0.1.0 | | |
| 3 | doctor | `dist\embyd.exe doctor` | 所有模块 [OK] | | |
| 4 | config show | `dist\embyd.exe config show` | 显示配置项 | | |
| 5 | server ping | `dist\embyd.exe server ping` | ServerName + Version | | |
| 6 | server whoami | `dist\embyd.exe server whoami` | Username + Policy | | |
| 7 | libraries | `dist\embyd.exe libraries` | 列出媒体库 | | |
| 8 | search | `dist\embyd.exe search <keyword>` | 返回搜索结果 | | |
| 9 | info | `dist\embyd.exe info <item_id>` | 电影详情 | | |
| 10 | download --dry-run | `dist\embyd.exe download <item_id> --dry-run` | 预览不下载 | | |
| 11 | download | `dist\embyd.exe download <item_id>` | 进度条 + 完成 | | |
| 12 | tasks list | `dist\embyd.exe tasks` | 任务列表 | | |
| 13 | resume | `dist\embyd.exe resume <task_id>` | 断点续传 | | |

---

## 四、GUI 验收（打包版）

使用 `dist\embyd-gui.exe` 进行测试。

### 基础功能

| # | 测试项 | 操作 | 预期结果 | 实际结果 | 通过 |
|---|--------|------|----------|----------|------|
| 1 | 启动 | 双击 embyd-gui.exe | 深色主题窗口，无异常 | | |
| 2 | Login | 输入 URL/用户名/密码 → Login | 状态栏 Connected(绿) | | |
| 3 | Ping | 点击 Ping | 日志显示 Server 名称/版本 | | |
| 4 | Whoami | 登录后自动 | 日志: Authenticated + Policy | | |
| 5 | 搜索电影 | Search 输入关键词 → Search | 表格有结果 | | |
| 6 | 双击 Movie | 双击搜索结果中的 Movie 行 | 自动切到 Preview，详情填充 | | |
| 7 | Dry Run | Preview 页查看 | Title/Size/Duration/Method 正确 | | |
| 8 | 下载电影 | 点击 Download | 进度条 + 速度标签 | | |
| 9 | 查看任务 | 切换到 Tasks Tab | 任务表显示 downloading | | |

### Series / Episode 功能

| # | 测试项 | 操作 | 预期结果 | 实际结果 | 通过 |
|---|--------|------|----------|----------|------|
| 10 | 搜索 Series | Search 输入剧集名 | Series 类型结果显示 | | |
| 11 | 双击 Series | 双击 Series 行 | 自动切到 Series Browser | | |
| 12 | Season 列表 | 查看左侧 Seasons | 列出所有季 | | |
| 13 | 点击 Season | 点击某一季 | 右侧 Episode 表格填充 | | |
| 14 | 勾选单集 | 勾选 Episode 的 Select | 选中计数更新 | | |
| 15 | 勾选整季 | 点击 Select Season | 当前可见全部勾选 | | |
| 16 | 切换多季 | 点击不同 Season | 已选 Episode 不丢失 | | |
| 17 | 下载剧集 | 点击 Download Selected | 每个 Episode 独立任务 | | |
| 18 | 任务确认 | 切换到 Tasks Tab | 每集一个独立 task | | |
| 19 | 文件名格式 | 查看 Tasks Title 列 | Series Name - S01E02 - Episode Title 格式 | | |

### 健壮性测试

| # | 测试项 | 操作 | 预期结果 | 实际结果 | 通过 |
|---|--------|------|----------|----------|------|
| 20 | 空 Season | 进入无 Season 的 Series | 不崩溃，显示提示 | | |
| 21 | 空 Episode | 点击无 Episode 的 Season | 不崩溃，表格为空 | | |
| 22 | 无选择下载 | 不勾选 → Download Selected | 提示 "No Episodes Selected" | | |
| 23 | 重复 Episode | 对已有 task 的 Episode 点下载 | 日志显示 Skipped | | |
| 24 | 下载中拖窗口 | 下载时拖动窗口 | GUI 不假死 | | |
| 25 | 下载中切 Tab | 下载时切换 Tab | 无卡顿 | | |
| 26 | 下载中滚日志 | 下载时滚动日志 | 无卡顿 | | |
| 27 | Pause | Tasks 选中 → Pause | 任务暂停 | | |
| 28 | Resume | Tasks 选中 → Resume | 任务恢复 | | |
| 29 | Cancel | Tasks 选中 → Cancel | 任务取消 | | |
| 30 | 关闭窗口 | 下载中关闭 | 提示 Pause and Exit | | |

---

## 五、常见错误说明

| 错误 | 现象 | 原因 | 解决方法 |
|------|------|------|----------|
| 401 Token 失效 | `[ERROR] Unauthorized` | Token 过期或被撤销 | 重新 Login |
| 403 无权限 | `[ERROR] Forbidden` | 账号无下载权限 | 联系服务器管理员 |
| 404 不存在 | `[ERROR] Resource not found` | item_id 错误或已删除 | 重新搜索获取正确 ID |
| SSL 证书错误 | `SSL certificate error` | HTTPS 证书问题 | 尝试 http:// 或导入证书 |
| Timeout | `Request timed out` | 服务器响应慢或网络差 | 增加 timeout 配置 |
| Connection Refused | `Connection refused` | 服务器未运行或端口错 | 检查服务器地址和端口 |
| Range 不支持 | 下载失败 | 服务器不支持 Range 请求 | 自动 fallback 到完整下载 |
| unknown total | 进度条不确定模式 | 服务器不返回 Content-Length | 正常行为，非错误 |
| size mismatch | 下载完成后校验失败 | 网络传输错误 | 删除 .part 重新下载 |
| 路径过长 | 保存失败 | Windows 路径 > 260 字符 | 缩短文件名或下载目录 |
| 文件名非法字符 | 保存失败 | 标题含 `<>:"/\|?*` | 自动替换为合法字符 |

---

## 六、自动化测试命令

```powershell
cd E:\embyD
python -m pytest -q                    # 运行所有测试 (应 231 passed)
python -m app.cli.main --help          # CLI 帮助
python -m app.cli.main doctor          # 诊断检查
python -m app.cli.main config show     # 查看配置
python -c "import sys; from PySide6.QtWidgets import QApplication; from app.gui.main_window import MainWindow; app=QApplication(sys.argv); w=MainWindow(); app.processEvents(); w.close(); app.processEvents(); print('gui smoke ok')"  # GUI smoke
```

---

## 七、打包命令

```powershell
cd E:\embyD
python scripts/build_exe.py            # 构建 CLI + GUI (推荐)
python scripts/build_exe.py --cli      # 仅 CLI (embyd.exe)
python scripts/build_exe.py --gui      # 仅 GUI (embyd-gui.exe)
```

---

## 八、已知问题

1. embyd.exe 首次运行时会从 AppData 迁移旧配置到 exe 所在目录，这是正常行为。
2. GUI exe (embyd-gui.exe) 体积较大 (~250MB)，因为包含了完整的 PySide6 运行时。
3. 当前不支持海报墙、系统托盘、安装器、自动更新。

---

## 九、完成条件检查

| 条件 | 状态 |
|------|------|
| pytest -q 全绿 (231 passed) | [x] |
| CLI 源码命令正常 | [x] |
| GUI smoke 无 QThread warning | [x] |
| dist/embyd.exe 构建成功 | [x] |
| dist/embyd-gui.exe 构建成功 | [x] |
| dist/embyd.exe --help 正常 | [x] |
| dist/embyd.exe doctor 正常 | [x] |
| dist/embyd-gui.exe 能启动 | [x] |
| docs/acceptance_stage10d6.md 完成 | [x] |
| dist/README_TESTING.txt 完成 | [ ] |
| 无 token/password 泄露 | [x] |
