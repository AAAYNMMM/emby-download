"""
Stage 6 verification tests.
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.downloader.task_store import create_task, get_task, update_task, list_tasks, delete_task, DownloadTask

def test_task_crud():
    """Test create, read, update, delete of a task."""
    result = create_task("item-1", title="Test Movie", save_path=r"C:\Downloads\test.mkv")
    task_id = result.task_id
    assert task_id is not None
    task = get_task(task_id)
    assert task is not None
    assert task.item_id == "item-1"
    assert task.status == "pending"
    update_task(task_id, status="downloading")
    updated = get_task(task_id)
    assert updated.status == "downloading"
    delete_task(task_id)
    assert get_task(task_id) is None
    print("[OK] Task CRUD works")

def test_task_initial_state():
    result = create_task("item-init", title="Init Test", save_path=r"C:\Downloads\init.mkv")
    task = get_task(result.task_id)
    assert task.status == "pending"
    assert task.downloaded_bytes == 0
    delete_task(result.task_id)
    print("[OK] Task initial state is pending")

def test_get_method_icon_ascii():
    from app.core.download_capability import get_method_icon
    assert isinstance(get_method_icon("direct"), str)
    print("[OK] get_method_icon ascii works")

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cmd_tasks_without_login():
    pass

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cmd_resume_without_login():
    pass

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cmd_download_without_login():
    pass

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cli_tasks_help():
    pass

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cli_tasks_options():
    pass

def test_download_task_dataclass():
    dt = DownloadTask(task_id="t1", item_id="i1", title="Test", save_path=r"C:\t.mkv")
    assert dt.task_id == "t1"
    assert dt.status == "pending"
    print("[OK] DownloadTask dataclass works")

def test_import_task_store():
    from app.downloader import task_store
    assert hasattr(task_store, "create_task")
    assert hasattr(task_store, "get_task")
    print("[OK] task_store module importable")
