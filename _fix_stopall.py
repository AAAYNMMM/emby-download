import re
with open("app/gui/download_controller.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '    def stop_all(self):\n        """Stop all active download tasks."""\n        for task_id in list(self._active.keys()):\n            self.cancel_task(task_id)\n        for task_id, entry in self._active.items():\n            if entry["thread"].isRunning():\n                entry["thread"].quit()\n                entry["thread"].wait(2000)\n        self._active.clear()\n        self._pending_queue.clear()'

new = '    def stop_all(self):\n        """Stop all active download tasks."""\n        for task_id in list(self._active.keys()):\n            self.cancel_task(task_id)\n        from shiboken6 import isValid\n        for task_id, entry in list(self._active.items()):\n            thread = entry.get("thread")\n            if thread is None:\n                continue\n            if not isValid(thread):\n                continue\n            if thread.isRunning():\n                thread.quit()\n                thread.wait(2000)\n        self._active.clear()\n        self._pending_queue.clear()'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/gui/download_controller.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("OK")
else:
    print("Pattern not found")
