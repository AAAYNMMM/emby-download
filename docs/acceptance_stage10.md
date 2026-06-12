# EmbyD Stage 10 验收报告

## 测试环境
- Emby 服务器版本：_______________
- Emby 服务器地址：_______________
- 测试网速：_______________________
- 测试账号 A（有下载权限）：_______
- 测试账号 B（无下载权限）：_______
- 测试日期：_______________________
- 测试人：_________________________

---

## CLI 验收结果

| # | 测试项 | 操作步骤 | 预期结果 | 实际结果 | 通过 |
|---|--------|----------|----------|----------|------|
| 1 | doctor | `embyd doctor` | 所有模块 [OK]，配置/Token/服务器信息正确 | | |
| 2 | config show | `embyd config show` | server_url/username 已配置，token_encrypted 显示 *** | | |
| 3 | server ping | `embyd server ping` | 显示 ServerName + Version | | |
| 4 | login (A) | `embyd login --server <url> --username <A>` | [OK] 登录成功，token 保存 | | |
| 5 | whoami (A) | `embyd server whoami` | 显示 Username/ID/Policy(Download=true) | | |
| 6 | libraries | `embyd libraries` | 至少列出 1 个 movies 类型库 | | |
| 7 | search | `embyd search "Inception" --limit 5` | 返回 <=5 条结果，含 ID/Title/Year/Type | | |
| 8 | info | `embyd info <item_id> --verbose` | 显示电影详情 + MediaSources + Bitrate/Stream 标志 | | |
| 9 | dry-run | `embyd download <item_id> --dry-run` | 显示 [DRY-RUN] 预览，不实际下载 | | |
| 10 | download | `embyd download <item_id>` | tqdm 进度条，完成后 [OK] | | |
| 11 | tasks | `embyd tasks` | Status=completed，大小/进度正确 | | |
| 12 | resume | Ctrl+C 中断后 `embyd resume <task_id>` | 从断点继续下载 | | |
| 13 | metadata | `embyd download <item_id> --with-all` | 生成 .nfo + .srt 文件 | | |
| 14 | login (B) | `embyd login` 无权限账号 | [OK] 登录成功 | | |
| 15 | info (B) | `embyd info <item_id>` | Download: [X] NOT Available | | |
| 16 | 404 | `embyd download fake_id` | [ERROR] Resource not found | | |

### CLI 失败详情

| # | 失败描述 | 根因 | 解决方案 |
|---|----------|------|----------|
| | | | |

---

## GUI 验收结果

| # | 测试项 | 操作步骤 | 预期结果 | 实际结果 | 通过 |
|---|--------|----------|----------|----------|------|
| 1 | 启动 | `python -m app.gui.app` | 窗口出现，深色主题 | | |
| 2 | Login | 输入 URL/用户名/密码 → Login | 状态栏: Connected(绿)，日志: [OK] Logged in | | |
| 3 | Ping | 点击 Ping | 日志: [OK] Server: xxx v4.x | | |
| 4 | Whoami | 登录后自动触发 | 日志: Authenticated + Policy | | |
| 5 | Search | 搜索 "Inception" → Search | 表格有结果，界面不卡顿 | | |
| 6 | 双击预览 | 双击搜索结果行 | 自动切到 Preview，详情填充 | | |
| 7 | Dry-Run | Preview 页预览 | Title/Size/Duration/Method 正确，Download 按钮可用 | | |
| 8 | Download | 点击 Download | 进度条 + 速度标签，完成后消失 | | |
| 9 | 不卡顿 | 下载中切换到 Tasks tab | 可操作，任务表显示 downloading | | |
| 10 | 错误场景 | 无效 URL → Ping | QMessageBox 显示错误详情 | | |
| 11 | 未登录 | 未登录 → Search | QMessageBox "Not Logged In" | | |
| 12 | 任务查看 | Tasks tab | filter 切换正确 | | |

### GUI 失败详情

| # | 失败描述 | 根因 | 解决方案 |
|---|----------|------|----------|
| | | | |

---

## 断点续传验收

| # | 测试项 | 操作 | 结果 | 通过 |
|---|--------|------|------|------|
| 1 | CLI 中断 | Ctrl+C 中断下载 | 任务 status=paused，.part 文件存在 | |
| 2 | CLI resume | `embyd resume <task_id>` | 从断点继续，完成后 status=completed | |
| 3 | GUI 中断 | 关闭下载中窗口 | 任务 status=paused | |
| 4 | GUI 恢复 | 重新启动后查看 Tasks | 任务状态正确 | |

---

## 元数据验收

| # | 文件类型 | `--with-all` 后生成 | 通过 |
|---|----------|---------------------|------|
| 1 | NFO | `{movie}.nfo` 包含 title/year/genre/actor | |
| 2 | Subtitles | `{movie}.chi.srt` 等 | |

---

## Token 安全验证

| # | 检查项 | 方法 | 结果 | 通过 |
|---|--------|------|------|------|
| 1 | config show | `embyd config show` | token_encrypted 显示 *** | |
| 2 | 日志输出 | 检查 console 输出 | token 未出现在任何日志行 | |
| 3 | 配置 JSON | 检查 embyd_config.json | token_encrypted 是密文 | |

---

## 发现的问题

| # | 问题描述 | 严重程度 | 状态 | 解决方案 |
|---|----------|----------|------|----------|
| | | | 待修复/已修复/不修复 | |

---

## 结论

### CLI 通过情况
- [ ] 全部 16 项通过
- [ ] 部分通过（___ 项失败）
- [ ] 未测试

### GUI 通过情况
- [ ] 全部 12 项通过
- [ ] 部分通过（___ 项失败）
- [ ] 未测试

### 最终结论
- [ ] CLI 全链路验收通过
- [ ] GUI 全链路验收通过
- [ ] 断点续传通过
- [ ] 元数据下载通过
- [ ] Token 安全通过
- [ ] 建议进入下一阶段
