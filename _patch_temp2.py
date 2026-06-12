path = r"E:\embyD\app\gui\main_window.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# PATCH 2: Replace _on_pause_selected through _on_cancel_selected
old_2_start = "    def _on_pause_selected(self):"
old_2_end_marker = "    def _on_cancel_selected(self):"

new_2_lines = [
    "    def _on_pause_selected(self):",
    "        task_ids = self._get_selected_task_ids()",
    "        if not task_ids:",
    "            return",
    "        self._set_task_action_buttons_enabled(False)",
    "        for tid in task_ids:",
    "            task = get_task(tid)",
    "            if task is None:",
    "                self.log.append_log(\"WARNING\", f\"Pause: task {tid[:8]}... not found\")",
    "                continue",
    "            if task.status == \"downloading\":",
    "                self.log.append_log(\"INFO\", f\"Pause request: task_id={tid[:8]}...\")",
    "                worker = AsyncBackendWorker()",
    "                worker.finished.connect(lambda r, t=tid: self._on_pause_done(t, r))",
    "                worker.error.connect(lambda msg, t=tid: self._on_pause_error(t, msg))",
    "                self._run_worker(worker, lambda: worker.run_async(",
    "                    self._backend_client.pause_task, tid))",
    "        self._set_task_action_buttons_enabled(True)",
    "        self._refresh_tasks()",
    "",
    "    def _on_pause_done(self, task_id: str, result):",
    "        self.log.append_log(\"OK\", f\"Task {task_id} paused.\")",
    "        self._refresh_tasks()",
    "",
    "    def _on_pause_error(self, task_id: str, message: str):",
    "        self.log.append_log(\"ERROR\", f\"Failed to pause task {task_id}: {message}\")",
    "        QMessageBox.warning(self, \"Pause Error\", f\"Failed to pause task {task_id[:8]}...:\\n{message}\")",
    "        self._refresh_tasks()",
    "",
    "    def _on_resume_selected(self):",
    "        task_ids = self._get_selected_task_ids()",
    "        if not task_ids:",
    "            return",
    "        download_dir = self._get_download_dir_from_ui()",
    "        if not download_dir:",
    "            QMessageBox.warning(self, DLG_MISSING_DIR, DLG_MISSING_DIR_MSG)",
    "            return",
    "        self._set_task_action_buttons_enabled(False)",
    "        for tid in task_ids:",
    "            self._start_or_resume_task(tid, download_dir, reason=\"resume\")",
    "        self._set_task_action_buttons_enabled(True)",
    "        self._refresh_tasks()",
    "",
    "    def _on_resume_done(self, task_id: str, result):",
    "        if isinstance(result, dict) and result.get(\"error\"):",
    "            self.log.append_log(\"ERROR\", f\"Resume failed: task_id={task_id[:8]}..., error={result['error']}\")",
    "            QMessageBox.warning(self, \"Resume Failed\", f\"Task {task_id[:8]}... resume failed:\\n{result['error']}\")",
    "            self._refresh_tasks()",
    "            return",
    "        if isinstance(result, dict) and result.get(\"status\") == \"ok\":",
    "            self.log.append_log(\"OK\", f\"Resume success: task_id={task_id[:8]}...\")",
    "            QTimer.singleShot(3000, lambda tid=task_id: self._verify_task_started(tid))",
    "        self._refresh_tasks()",
    "",
    "    def _on_resume_error(self, task_id: str, message: str):",
    "        self.log.append_log(\"ERROR\", f\"Resume error: task_id={task_id[:8]}..., error={message}\")",
    "        QMessageBox.warning(self, \"Resume Error\", f\"Failed to resume task {task_id[:8]}...:\\n{message}\")",
    "        self._refresh_tasks()",
    "",
    "    def _start_or_resume_task(self, task_id: str, download_dir: str, reason: str = \"start\"):",
    "        \"\"\"Unified start/resume logic for a single task.",
    "",
    "        - pending -> calls backend start_task",
    "        - paused/failed -> calls backend resume_task",
    "        \"\"\"",
    "        task = get_task(task_id)",
    "        if task is None:",
    "            self.log.append_log(\"WARNING\", f\"{reason.capitalize()}: task {task_id[:8]}... not found in DB\")",
    "            return",
    "",
    "        status = task.status",
    "        self.log.append_log(\"INFO\", f\"{reason.capitalize()} request: task_id={task_id[:8]}... status={status}\")",
    "",
    "        if status == \"pending\":",
    "            worker = AsyncBackendWorker()",
    "            worker.finished.connect(lambda r, tid=task_id: self._on_resume_done(tid, r))",
    "            worker.error.connect(lambda msg, tid=task_id: self._on_resume_error(tid, msg))",
    "            self._run_worker(worker, lambda tid=task_id, dd=download_dir: worker.run_async(",
    "                self._backend_client.start_task, tid, dd))",
    "        elif status in (\"paused\", \"failed\"):",
    "            worker = AsyncBackendWorker()",
    "            worker.finished.connect(lambda r, tid=task_id: self._on_resume_done(tid, r))",
    "            worker.error.connect(lambda msg, tid=task_id: self._on_resume_error(tid, msg))",
    "            self._run_worker(worker, lambda tid=task_id, dd=download_dir: worker.run_async(",
    "                self._backend_client.resume_task, tid, dd))",
    "        else:",
    "            self.log.append_log(\"INFO\", f\"{reason.capitalize()} skipped: task {task_id[:8]}... is {status}\")",
    "",
    "    def _set_task_action_buttons_enabled(self, enabled: bool):",
    "        \"\"\"Enable or disable task action buttons to prevent double-click.\"\"\"",
    "        if hasattr(self, \"btn_start_selected\"):",
    "            self.btn_start_selected.setEnabled(enabled)",
    "        if hasattr(self, \"btn_resume_selected\"):",
    "            self.btn_resume_selected.setEnabled(enabled)",
    "        if hasattr(self, \"btn_pause_selected\"):",
    "            self.btn_pause_selected.setEnabled(enabled)",
    "        if hasattr(self, \"btn_cancel_selected\"):",
    "            self.btn_cancel_selected.setEnabled(enabled)",
    "        if hasattr(self, \"btn_delete_selected\"):",
    "            self.btn_delete_selected.setEnabled(enabled)",
    "",
    "    def _on_cancel_selected(self):",
]

new_2 = "\n".join(new_2_lines) + "\n"

idx_start = content.find(old_2_start)
idx_end = content.find(old_2_end_marker)
if idx_start >= 0 and idx_end > idx_start:
    print(f"Found region: {idx_start} to {idx_end}")
    content = content[:idx_start] + new_2 + content[idx_end + len(old_2_end_marker):]
    print("PATCH 2 applied")
else:
    print(f"PATCH 2 FAILED: start={idx_start}, end={idx_end}")
    # Try to find
    alt = content.find("def _on_pause_selected(self):")
    alt2 = content.find("def _on_cancel_selected(self):")
    print(f"  alt start={alt}, alt end={alt2}")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("File saved")
