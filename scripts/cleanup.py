"""
系统磁盘清理工具

帮扶管理信息系统 — 定期清理缓存和临时文件，防止磁盘空间耗尽。

用法:
    python scripts/cleanup.py              # 预览模式（仅显示将清理的内容）
    python scripts/cleanup.py --execute    # 执行清理
    python scripts/cleanup.py --schedule   # 安装 Windows 计划任务（每周日 3:00 AM）
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRY_RUN = True
TOTAL_FREED = 0


def size_fmt(size_bytes: int) -> str:
    """Human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_dir_size(path: Path) -> int:
    """Get total size of a directory, returning 0 if it doesn't exist."""
    if not path.exists():
        return 0
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def clean_dir(path: Path, description: str) -> int:
    """Remove directory contents, return bytes freed."""
    size = get_dir_size(path)
    if size == 0:
        if not DRY_RUN:
            print(f"  [SKIP] {description}: empty or missing ({path})")
        return 0

    print(f"  {'[DRY]' if DRY_RUN else '[DEL]'} {description}: {size_fmt(size)} ({path})")
    if not DRY_RUN:
        try:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
            elif path.is_file():
                path.unlink(missing_ok=True)
        except OSError as e:
            print(f"    WARNING: {e}")
    return size


def clean_pattern(root: Path, pattern: str, description: str) -> int:
    """Remove all directories matching pattern, return bytes freed."""
    total = 0
    dirs_to_clean = list(root.rglob(pattern))
    for d in dirs_to_clean:
        size = get_dir_size(d)
        if size > 0:
            total += size
            print(f"  {'[DRY]' if DRY_RUN else '[DEL]'} {description}: {size_fmt(size)} ({d.relative_to(PROJECT_ROOT)})")
            if not DRY_RUN:
                shutil.rmtree(d, ignore_errors=True)
    return total


def main():
    global DRY_RUN, TOTAL_FREED

    parser = argparse.ArgumentParser(description="系统磁盘清理工具")
    parser.add_argument("--execute", action="store_true", help="实际执行清理（默认为预览模式）")
    parser.add_argument("--schedule", action="store_true", help="安装 Windows 计划任务")
    args = parser.parse_args()

    if args.schedule:
        install_scheduled_task()
        return

    DRY_RUN = not args.execute

    if DRY_RUN:
        print("=" * 60)
        print("  预览模式 — 使用 --execute 实际执行清理")
        print("=" * 60)
    else:
        print("=" * 60)
        print("  执行清理中...")
        print("=" * 60)

    print()

    # ── Python 缓存 ──
    TOTAL_FREED += clean_pattern(PROJECT_ROOT / "backend", "__pycache__", "Python bytecode cache")
    TOTAL_FREED += clean_pattern(PROJECT_ROOT / "backend", ".pytest_cache", "pytest cache")

    # ── Node.js 缓存 ──
    TOTAL_FREED += clean_dir(PROJECT_ROOT / "frontend" / "node_modules" / ".cache", "npm cache (in node_modules)")

    # ── Git 垃圾回收 ──
    git_dir = PROJECT_ROOT / ".git"
    if git_dir.exists() and not DRY_RUN:
        import subprocess
        print("  [GIT] Running git gc...")
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "gc", "--auto", "--quiet"], check=False)
        print("  [GIT] Done")

    # ── pip 缓存 ──
    if not DRY_RUN:
        import subprocess
        print("  [PIP] Cleaning pip cache...")
        subprocess.run([sys.executable, "-m", "pip", "cache", "purge"], check=False, capture_output=True)
        print("  [PIP] Done")

    # ── Windows Temp（仅清理 7 天前的文件） ──
    if sys.platform == "win32":
        temp_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Temp"
        if temp_dir.exists():
            cutoff = datetime.now().timestamp() - 7 * 86400
            deleted = 0
            try:
                items = list(temp_dir.iterdir())
            except (OSError, PermissionError):
                items = []
            for item in items:
                try:
                    if item.stat().st_mtime < cutoff:
                        deleted += 1
                        if not DRY_RUN:
                            if item.is_dir():
                                shutil.rmtree(item, ignore_errors=True)
                            else:
                                item.unlink(missing_ok=True)
                except OSError:
                    pass
            if deleted > 0:
                print(f"  {'[DRY]' if DRY_RUN else '[DEL]'} Windows Temp (7d+ old): {deleted} files/dirs")

    # ── 项目数据备份清理（保留最近 7 天） ──
    data_dir = PROJECT_ROOT / "backend" / "data"
    if data_dir.exists():
        # zip 备份文件
        backup_pattern = "backup_*.zip"
        backups = sorted(data_dir.glob(backup_pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if len(backups) > 7:
            old = backups[7:]
            for b in old:
                print(f"  {'[DRY]' if DRY_RUN else '[DEL]'} Old backup: {b.name}")
                TOTAL_FREED += b.stat().st_size
                if not DRY_RUN:
                    b.unlink(missing_ok=True)

        # DB 快照文件（保留最近 3 个）
        snapshots = sorted(data_dir.glob("rural_revitalization.db.snapshot_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if len(snapshots) > 3:
            for s in snapshots[3:]:
                print(f"  {'[DRY]' if DRY_RUN else '[DEL]'} Old DB snapshot: {s.name}")
                TOTAL_FREED += s.stat().st_size
                if not DRY_RUN:
                    s.unlink(missing_ok=True)

        # DB 恢复前备份（保留最近 2 个）
        restore_baks = sorted(data_dir.glob("rural_revitalization_before_restore_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        if len(restore_baks) > 2:
            for r in restore_baks[2:]:
                print(f"  {'[DRY]' if DRY_RUN else '[DEL]'} Old restore backup: {r.name}")
                TOTAL_FREED += r.stat().st_size
                if not DRY_RUN:
                    r.unlink(missing_ok=True)

        # 测试数据库残留
        test_db = data_dir / "test_integration.db"
        if test_db.exists():
            TOTAL_FREED += test_db.stat().st_size
            if not DRY_RUN:
                test_db.unlink(missing_ok=True)
            print(f"  {'[DRY]' if DRY_RUN else '[DEL]'} Test DB residual: {test_db.name}")

    # ── 日志轮转（.archive 文件，90天前的） ──
    log_dir = PROJECT_ROOT / "backend" / "logs"
    if log_dir.exists():
        cutoff = datetime.now().timestamp() - 90 * 86400
        for log_file in log_dir.iterdir():
            try:
                if log_file.stat().st_mtime < cutoff:
                    print(f"  {'[DRY]' if DRY_RUN else '[DEL]'} Old log: {log_file.name}")
                    TOTAL_FREED += log_file.stat().st_size
                    if not DRY_RUN:
                        log_file.unlink(missing_ok=True)
            except OSError:
                pass

    print()
    print("=" * 60)
    if DRY_RUN:
        print(f"  可释放: {size_fmt(TOTAL_FREED)}")
        print(f"  执行: python scripts/cleanup.py --execute")
    else:
        print(f"  已释放: {size_fmt(TOTAL_FREED)}")
    print("=" * 60)


def _resolve_pythonw() -> str:
    """计划任务使用的解释器绝对路径（优先无控制台的 pythonw.exe）。

    计划任务以干净环境启动，PATH 里可能没有 python（本机实测指向已删除的 32 位
    安装），因此**不得**写裸 `pythonw`/`python` —— 必须用当前解释器的绝对路径，
    否则计划任务注册成功但每次执行都失败（静默不可复现）。
    """
    exe = Path(sys.executable)
    if sys.platform == "win32":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(exe)


def install_scheduled_task():
    """安装 Windows 计划任务：每周日凌晨 3 点自动清理。"""
    if sys.platform != "win32":
        print("计划任务仅支持 Windows")
        return

    script_path = Path(__file__).resolve()
    task_name = "MRRMS_Cleanup"
    interpreter = _resolve_pythonw()
    # /tr 参数内的可执行文件与脚本路径必须带引号（路径含空格时 schtasks 才能正确解析）
    command = (
        f'schtasks /create /tn "{task_name}" '
        f'/tr "\\"{interpreter}\\" \\"{script_path}\\" --execute" '
        f'/sc weekly /d SUN /st 03:00 /f'
    )

    print(f"创建计划任务: {task_name}")
    print(f"命令: {command}")
    result = os.system(command)
    if result == 0:
        print(f"✅ 计划任务已创建: {task_name}（每周日 3:00 AM）")
        print(f"   查看: schtasks /query /tn {task_name}")
    else:
        print(f"❌ 创建失败 (exit code {result})，请以管理员身份运行")


if __name__ == "__main__":
    main()
