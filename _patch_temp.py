path = r"E:\embyD\app\gui\main_window.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# PATCH 1: Replace _on_start_selected through _verify_task_started
old_1_start = "    def _on_start_selected(self):"
old_1_end_marker = "    def _on_start_finished(self, count: int):"

new_1_lines = [
    "    def _on_start_selected(self):",
    "        task_ids = self._get_selected_task_ids()",
    "        if not task_ids:",
    "            return",
    "        download_dir = self._get_download_dir_from_ui()",
    "        if not download_dir:",
    "            QMessageBox.warning(self, DLG_MISSING_DIR, DLG_MISSING_DIR_MSG)",
    "            return",
    "",
    "        self._set_task_action_buttons_enabled(False)",
    "",
    "        for tid in task_ids:",
    "            self._start_or_resume_task(tid, download_dir, reason=\"start\")",
    "",
    "        self._set_task_action_buttons_enabled(True)",
    "        self._refresh_tasks()",
    "",
    "    def _on_start_ready(self, task_id: str, item_id: str, download_dir: str):",
    "        self.log.append_log(\"INFO\", f\"Start request: task_id={task_id[:8]}...\")",
    "        worker = AsyncBackendWorker()",
    "        worker.finished.connect(lambda r, tid=task_id: self._on_single_start_done(tid, r))",
    "        worker.error.connect(lambda msg, tid=task_id: self._on_single_start_error(tid, msg))",
    "        self._run_worker(worker, lambda tid=task_id, dd=download_dir: worker.run_async(",
    "            self._backend_client.start_task, tid, dd))",
    "",
    "    def _on_single_start_done(self, task_id: str, result):",
    "        if isinstance(result, dict) and result.get(\"error\"):",
    "            self.log.append_log(\"ERROR\", f\"Start failed: task_id={task_id[:8]}..., error={result['error']}\")",
    "            QMessageBox.warning(self, \"Start Failed\", f\"Task {task_id[:8]}... start failed:\\n{result['error']}\")",
    "            self._refresh_tasks()",
    "            return",
    "        if not isinstance(result, dict) or result.get(\"status\") != \"ok\":",
    "            self.log.append_log(\"ERROR\", f\"Start unexpected response: task_id={task_id[:8]}..., result={result}\")",
    "            self._refresh_tasks()",
    "            return",
    "        self.log.append_log(\"OK\", f\"Start success: task_id={task_id[:8]}...\")",
    "        QTimer.singleShot(3000, lambda tid=task_id: self._verify_task_started(tid))",
    "",
    "    def _on_single_start_error(self, task_id: str, message: str):",
    "        self.log.append_log(\"ERROR\", f\"Start error: task_id={task_id[:8]}..., error={message}\")",
    "        QMessageBox.warning(self, \"Start Error\", f\"Failed to start task {task_id[:8]}...:\\n{message}\")",
    "        task = get_task(task_id)",
    "        if task is None:",
    "            self.log.append_log(\"ERROR\", f\"Task {task_id[:8]}... not found in DB - may be wrong task_id\")",
    "        elif task.status == \"pending\":",
    "            self.log.append_log(\"WARNING\", \"Task still pending after start error\")",
    "        self._refresh_tasks()",
    "",
    "    def _verify_task_started(self, task_id: str):",
    "        \"\"\"Check if a task actually left pending state after start was called.\"\"\"",
    "        task = get_task(task_id)",
    "        if task is None:",
    "            self.log.append_log(\"WARNING\", f\"Task {task_id[:8]}... not found during verification\")",
    "        elif task.status == \"pending\":",
    "            self.log.append_log(\"WARNING\", f\"Task {task_id[:8]}... still pending 3s after start - backend may not have started download\")",
    "        else:",
    "            self.log.append_log(\"DEBUG\", f\"Task {task_id[:8]}... status is now: {task.status}\")",
    "        self._refresh_tasks()",
    "",
    "    def _on_start_finished(self, count: int):",
]

new_1 = "\n".join(new_1_lines) + "\n"

# Find the region to replace
idx_start = content.find(old_1_start)
idx_end = content.find(old_1_end_marker)
if idx_start >= 0 and idx_end > idx_start:
    print(f"Found region: {idx_start} to {idx_end}")
    content = content[:idx_start] + new_1 + content[idx_end + len(old_1_end_marker):]
    print("PATCH 1 applied")
else:
    print(f"PATCH 1 FAILED: start={idx_start}, end={idx_end}")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("File saved")
