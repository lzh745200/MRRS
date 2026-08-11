#!/usr/bin/env python
"""
帮扶管理信息系统 - 后端服务启动入口
用于 PyInstaller 打包时作为入口脚本
"""

import os
import sys
import socket
import logging
from pathlib import Path

# ── 关键修复：Windows 中文系统的控制台默认 GBK 编码，无法输出 Unicode 字符 ──
# 必须在任何 print() 之前执行，否则 PyInstaller 打包后在 GBK 环境会崩溃
try:
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
# 备用方案：如果 reconfigure 不可用（Python < 3.7 或缓冲区问题），用环境变量强制
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# ── 关键修复：PyInstaller 无控制台模式（windowed）下 sys.stdout/stderr 为 None ──
# Uvicorn logging 配置会调用 sys.stderr.isatty()，None 没有该方法导致崩溃。
# 修复：将 None 替换为日志文件 writer（优先）或 devnull，确保错误可追踪。
_NONE_STREAM_FIXED = False


def _get_fallback_stream():
    """获取 fallback 输出流：优先写入日志文件，不可写则用 devnull"""
    _log_dir = os.environ.get("LOG_DIR", "")
    if _log_dir:
        try:
            os.makedirs(_log_dir, exist_ok=True)
            return open(os.path.join(_log_dir, "startup.log"), "a", encoding="utf-8")
        except Exception:
            pass
    return open(os.devnull, "w")


if sys.stdout is None:
    sys.stdout = _get_fallback_stream()
    _NONE_STREAM_FIXED = True
if sys.stderr is None:
    sys.stderr = _get_fallback_stream()
    _NONE_STREAM_FIXED = True
if _NONE_STREAM_FIXED:
    # 延迟输出——此时 stderr 刚修复，print 才安全
    print("[FIX] PyInstaller 无控制台模式：stdout/stderr 已重定向到日志文件", flush=True)

# PyInstaller 打包后, 确保能正确找到 app 模块
if getattr(sys, 'frozen', False):
    # 运行在 PyInstaller 打包环境中
    base_dir = os.path.dirname(sys.executable)
    os.chdir(base_dir)
    # 关键修复：PyInstaller 打包后 app 目录在 _MEIPASS 中，
    # 必须将 _MEIPASS 添加到 sys.path 才能正确导入
    if hasattr(sys, '_MEIPASS'):
        meipass_dir = sys._MEIPASS
        if meipass_dir not in sys.path:
            sys.path.insert(0, meipass_dir)
        # 同时确保 exe 所在目录在 sys.path（用于数据文件）
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 开发模式：切换工作目录到 backend/，确保 get_data_path() 等
    # 使用 Path.cwd() 的函数始终解析到正确的项目目录。
    # 这防止了从不同目录启动时创建多个 runtime_secrets.json 副本。
    os.chdir(base_dir)
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)


def _check_python_arch():
    """检查 Python 架构 — 64-bit Windows 上使用 32-bit Python 性能显著下降"""
    import struct
    bits = struct.calcsize("P") * 8
    if bits == 32 and sys.platform == 'win32':
        # 检查是否在 64-bit OS 上
        import platform
        machine = platform.machine().lower()
        if machine in ('amd64', 'x86_64', 'arm64'):
            print("[WARN] 检测到 32-bit Python 运行在 64-bit Windows 上")
            print("  性能将显著下降（加密操作慢 2-5x，内存操作慢 30%+）")
            print(f"  当前: {sys.executable}")
            # 检查 64-bit Python 是否可用
            possible_paths = [
                r'C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe',
                r'C:\Python311\python.exe',
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    print(f"  建议使用: {p}")
                    break
            print("  或通过 .venv\\Scripts\\python start.py 启动（64-bit）")
        else:
            print("[INFO] 32-bit Python on 32-bit OS — this is expected")
    else:
        print(f"[OK] Python {bits}-bit — optimal")


def _check_vcruntime():
    """检查 VC++ 运行时 DLL 是否可用（仅 Windows）"""
    if sys.platform != 'win32':
        return
    import ctypes
    dlls_to_check = ['vcruntime140', 'vcruntime140_1', 'msvcp140']
    missing = []
    for dll_name in dlls_to_check:
        try:
            ctypes.WinDLL(dll_name)
        except OSError:
            missing.append(dll_name + '.dll')
    if missing:
        print(f"[WARN] 缺少 VC++ 运行时 DLL: {', '.join(missing)}")
        print("  请安装 Visual C++ 2015-2022 Redistributable (x64)")
        print("  下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        # 不退出，让后续启动尝试继续（PyInstaller 打包可能自带了这些 DLL）
    else:
        print("[OK] VC++ 运行时 DLL 检查通过")


def _check_port_available(host: str, port: int) -> bool:
    """检查端口是否可用，不可用时尝试终止旧后端进程并等待释放"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
        return True
    except OSError:
        sock.close()

    print(f"[WARN] 端口 {port} 已被占用，尝试终止占用进程...")
    if sys.platform != 'win32':
        print(f"  请手动释放端口 {port} 后重试")
        return False

    # 查找占用端口的进程
    import subprocess
    import time as _time
    old_pids = []
    try:
        result = subprocess.run(
            ['netstat', '-aon'],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
        )
        for line in result.stdout.splitlines():
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                pid = parts[-1] if parts else None
                if pid and pid.isdigit():
                    old_pids.append(int(pid))
                break
    except Exception:
        pass

    if not old_pids:
        print(f"  无法确定占用进程，请手动释放端口 {port}")
        return False

    # 安全策略：只自动终止本项目开发模式的残留后端（python.exe），
    # 绝不强杀打包版桌面应用的后端（assistance-backend.exe）或其他无关进程——
    # 否则会中断正在运行的桌面应用（Electron 虽会自动重启，但会打断用户操作）。
    _DEV_BACKEND_NAMES = {"python.exe", "python3.exe", "pythonw.exe", "python311.exe"}
    _PACKAGED_BACKEND_NAMES = {"assistance-backend.exe", "assistance-backend"}

    for pid in old_pids:
        try:
            name_result = subprocess.run(
                ['tasklist', '/fi', f'PID eq {pid}', '/fo', 'csv', '/nh'],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
            )
            proc_info = name_result.stdout.strip() if name_result.stdout.strip() else f"PID {pid}"
            # tasklist CSV 首字段为映像名: "python.exe","1234",...
            proc_name = ""
            if '"' in proc_info:
                proc_name = proc_info.split('"')[1].strip().lower()
            if proc_name in _PACKAGED_BACKEND_NAMES:
                print(
                    f"  检测到打包版桌面应用正在运行（{proc_info}），"
                    "为避免中断应用，请先退出桌面应用后再启动开发后端"
                )
                return False
            if proc_name and proc_name not in _DEV_BACKEND_NAMES:
                print(
                    f"  端口 {port} 被非本项目进程占用（{proc_info}），"
                    "为安全起见不自动终止，请手动释放端口后重试"
                )
                return False
            print(f"  终止本项目残留后端进程: {proc_info}")
            subprocess.run(
                ['taskkill', '/PID', str(pid), '/F'],
                capture_output=True, timeout=10
            )
        except Exception as e:
            print(f"  终止进程 {pid} 失败: {e}")

    # 等待端口释放（最多 5 秒）
    for _ in range(10):
        _time.sleep(0.5)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
            sock.close()
            print(f"[OK] 端口 {port} 已释放")
            return True
        except OSError:
            sock.close()

    print(f"[ERROR] 端口 {port} 仍被占用，请手动终止后重试")
    return False


def _ensure_dirs():
    """确保运行时所需的目录存在（打包后首次运行时创建）"""
    dirs = [
        os.environ.get("UPLOAD_DIR", "./uploads"),
        os.environ.get("CACHE_DIR", "./data/cache"),
        os.environ.get("EXPORT_DIR", "./exports"),
    ]
    # 从 LOG_FILE 提取日志目录
    log_file = os.environ.get("LOG_FILE", "./logs/app.log")
    dirs.append(os.path.dirname(log_file))

    # 从 DATABASE_URL 提取数据库目录
    db_url = os.environ.get("DATABASE_URL", "sqlite:///./data/rural_revitalization.db")
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            dirs.append(db_dir)

    for d in dirs:
        if d:
            os.makedirs(d, exist_ok=True)


def _check_database_integrity():
    """启动时执行 SQLite PRAGMA integrity_check（每24h一次），异常时尝试从最近备份恢复"""
    import sqlite3
    import time

    db_url = os.environ.get("DATABASE_URL", "sqlite:///./data/rural_revitalization.db")
    if not db_url.startswith("sqlite"):
        return

    db_path = db_url.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        print(f"数据库文件不存在，将在启动时自动创建: {db_path}")
        return

    # 每 24h 检查一次完整性（避免每次启动都跑全表扫描）
    _integrity_stamp = Path(db_path + ".integrity_check")
    if _integrity_stamp.exists():
        try:
            age = time.time() - _integrity_stamp.stat().st_mtime
            if age < 86400:  # 24h
                print(f"[OK] 数据库完整性检查跳过（上次检查: {age / 3600:.1f}h 前）")
                return
        except OSError:
            pass

    try:
        conn = sqlite3.connect(db_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()

        if result and result[0] == "ok":
            print("[OK] 数据库完整性检查通过")
            _integrity_stamp.touch()  # 记录检查时间
        else:
            print(f"[WARN] 数据库完整性检查异常: {result}")
            _try_restore_from_backup(db_path)
    except Exception as e:
        print(f"[ERROR] 数据库完整性检查失败: {e}")
        _try_restore_from_backup(db_path)


def _try_restore_from_backup(db_path: str):
    """尝试从最近的备份文件恢复数据库，无备份时删除损坏文件并让应用自动创建空库"""
    import glob
    import shutil

    backup_dir = os.environ.get("BACKUP_DIR", "./backups")
    backups = []
    if os.path.exists(backup_dir):
        # 查找最近的 .db 或 .db.gz 备份文件
        backups = sorted(
            glob.glob(os.path.join(backup_dir, "*.db")) +
            glob.glob(os.path.join(backup_dir, "*.db.gz")),
            key=os.path.getmtime,
            reverse=True,
        )

    # 先备份损坏文件
    corrupted_path = db_path + ".corrupted"
    try:
        shutil.copy2(db_path, corrupted_path)
        print(f"[INFO] 损坏的数据库已保存为: {corrupted_path}")
    except Exception as e:
        print(f"[WARN] 备份损坏文件失败: {e}")

    if backups:
        latest_backup = backups[0]
        print(f"[INFO] 尝试从备份恢复: {latest_backup}")
        try:
            if latest_backup.endswith(".gz"):
                import gzip
                with gzip.open(latest_backup, 'rb') as f_in:
                    with open(db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(latest_backup, db_path)
            print("[OK] 数据库已从备份恢复")
            return
        except Exception as e:
            print(f"[ERROR] 从备份恢复失败: {e}")

    # 无备份或备份恢复失败：删除损坏文件，让应用启动时自动创建空库
    print("[INFO] 无可用备份，将删除损坏数据库并自动创建空库")
    try:
        os.remove(db_path)
        # 同时删除 SQLite WAL/SHM 文件
        for suffix in ('-wal', '-shm'):
            wal_path = db_path + suffix
            if os.path.exists(wal_path):
                os.remove(wal_path)
        print("[OK] 损坏数据库已删除，应用启动时将自动创建新数据库")
    except Exception as e:
        print(f"[ERROR] 删除损坏数据库失败: {e}, 请手动删除: {db_path}")


def _setup_fallback_connection_reset_handler():
    """回退方案：简单的 loop 异常处理器。

    当 win_proactor_fix 模块导入失败时使用。此方法仅设置当前运行中
    或缓存的 loop 的处理器，不如 win_proactor_fix 的 Policy 级别方案全面。
    """
    import asyncio

    def _silence_connection_reset(loop, context):
        exc = context.get("exception")
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        message = context.get("message", "")
        if isinstance(message, str) and "connection reset" in message.lower():
            return
        loop.default_exception_handler(context)

    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(_silence_connection_reset)
        print("[OK] 回退 ConnectionResetError 处理器已设置 (runtime loop)")
    except RuntimeError:
        # 无运行时 loop — 在最后一个可能的时机设置
        pass


def _verify_frontend_assets():
    """启动前校验前端静态资源完整性。

    检测 resources/frontend/index.html 是否存在，以及其引用的所有
    JS/CSS 文件是否真实存在。缺失或 hash 不匹配 → 拒绝启动并打印修复指引。
    纯 API 模式（无前端目录）下跳过校验。
    """
    import os
    import subprocess
    import sys as _sys

    # 查找前端目录（复用 static_files.py 的逻辑）
    frontend_dir = None
    candidates = [
        os.environ.get("FRONTEND_DIST_PATH", ""),
    ]
    # PyInstaller 冻结模式：exe 位于 resources/backend/assistance-backend.exe，
    # 前端位于 resources/frontend/，即 exe 同级的 ../frontend（Electron 通过
    # FRONTEND_DIST_PATH 环境变量注入，此处为兜底查找）。
    if getattr(_sys, "frozen", False):
        _exe_dir = os.path.dirname(os.path.abspath(_sys.executable))
        candidates.extend([
            os.path.join(_exe_dir, "..", "frontend"),
            os.path.join(_exe_dir, "frontend"),
            os.path.join(_exe_dir, "..", "resources", "frontend"),
        ])
    else:
        candidates.extend([
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "frontend"),
        ])
    for candidate in candidates:
        if candidate and os.path.isfile(os.path.join(candidate, "index.html")):
            frontend_dir = os.path.abspath(candidate)
            break

    if not frontend_dir:
        print("[WARN] 前端静态资源未找到，启动后仅提供 API 服务")
        print("  如需前端界面，请执行: cd frontend && npm run build")
        return  # 允许纯 API 模式启动

    # PyInstaller 冻结模式下审计脚本不在打包中，跳过深度校验
    if getattr(_sys, "frozen", False):
        print("[OK] 前端静态资源已找到（冻结模式跳过深度校验）")
        return

    # 调用审计脚本的核心校验逻辑（优先进程内调用，失败退回子进程）
    try:
        # 进程内调用：更快，无需路径解析/超时/编码处理
        import importlib.util as _importlib_util
        _audit_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "scripts", "audit_static_assets.py",
        )
        _spec = _importlib_util.spec_from_file_location("audit_static_assets", _audit_script)
        if _spec and _spec.loader:
            _audit_module = _importlib_util.module_from_spec(_spec)
            _spec.loader.exec_module(_audit_module)
            exit_code = _audit_module.audit(frontend_dir, quick=True)
            if exit_code != 0:
                print("=" * 60)
                print("[FATAL] 前端静态资源完整性校验失败，拒绝启动！")
                print("=" * 60)
                print("修复步骤:")
                print("  1. cd frontend && npm run build")
                print(r"  2. Windows: call scripts\build\sync-frontend-dist.bat")
                print("     Linux:   bash scripts/build/sync-frontend-dist.sh")
                print("  3. 重新启动后端")
                print("=" * 60)
                _sys.exit(1)
            else:
                print("[OK] 前端静态资源完整性校验通过")
        else:
            raise ImportError("无法加载审计模块")
    except Exception:
        # 回退到子进程方式（兼容 PyInstaller 打包场景）
        try:
            _audit_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "scripts", "audit_static_assets.py",
            )
            result = subprocess.run(
                [_sys.executable, _audit_script, "--dir", frontend_dir, "--quick"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
            if result.returncode != 0:
                print("=" * 60)
                print("[FATAL] 前端静态资源完整性校验失败，拒绝启动！")
                print("=" * 60)
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                print("修复步骤:")
                print("  1. cd frontend && npm run build")
                print(r"  2. Windows: call scripts\build\sync-frontend-dist.bat")
                print("     Linux:   bash scripts/build/sync-frontend-dist.sh")
                print("  3. 重新启动后端")
                print("=" * 60)
                _sys.exit(1)
            else:
                print("[OK] 前端静态资源完整性校验通过")
        except FileNotFoundError:
            print("[WARN] 审计脚本未找到，跳过静态资源校验")
        except Exception as e:
            print(f"[WARN] 静态资源校验执行异常: {e}，跳过校验继续启动")


def main():
    import uvicorn

    print("=" * 50)
    print("帮扶管理信息系统 - 后端服务启动中")
    print("=" * 50)

    # ── 预检：Python 架构 + VC++ 运行时 DLL ──
    _check_python_arch()
    _check_vcruntime()

    # ── 关键修复：Windows ProactorEventLoop ConnectionResetError ──
    # 必须在任何 asyncio 操作之前应用，使用三层纵深防御：
    #   Layer 1: Monkey-patch ProactorBasePipeTransport._call_connection_lost
    #   Layer 2: 替换全局 EventLoopPolicy，所有新 loop 自动继承异常处理器
    #   Layer 3: 对当前运行时 loop 设置异常处理器
    # 修复后 uvicorn 创建的每个事件循环都自动包含安全处理器。
    if sys.platform == "win32":
        try:
            from app.utils.win_proactor_fix import apply_windows_proactor_fix

            applied = apply_windows_proactor_fix()
            if applied:
                print("[OK] Windows ProactorEventLoop ConnectionResetError 修复已应用")
        except Exception as e:
            print(f"[WARN] ProactorEventLoop 修复应用失败: {e}")
            # 回退：设置简单的异常处理器作为最低限度保护
            _setup_fallback_connection_reset_handler()

    _ensure_dirs()
    from app.utils.runtime_secrets import ensure_runtime_secrets  # noqa: E402
    print("  初始化安全密钥...", flush=True)
    ensure_runtime_secrets()
    print("  检查数据库...", flush=True)
    _check_database_integrity()

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))

    # 检查端口可用性（仅作为诊断信息，不阻止启动）
    if not _check_port_available(host, port):
        print(f"  提示：端口 {port} 被占用，服务可能无法正常监听")
        print("  请关闭占用该端口的程序后重试")

    print(f"\n正在启动后端服务: http://{host}:{port}")
    print(f"API 文档: http://{host}:{port}/docs")

    # ── 麒麟模式：延迟自动打开系统浏览器 ──
    if os.environ.get("KYLIN_MODE", "false").lower() == "true":
        _auto_open_browser(host, port)

    # PyInstaller 环境下必须使用直接引用的 app 对象，
    # 字符串 "app.main:app" 依赖 importlib 动态导入，在冻结环境中会失败。
    from app.main import app  # noqa: E402

    # ── 启动前静态资源完整性校验 ──
    _verify_frontend_assets()

    # ── 过滤 304 静态资源日志噪音 ──
    class _Skip304Filter(logging.Filter):
        def filter(self, record):
            msg = record.getMessage()
            return "304" not in msg and "login-bg" not in msg and "badges" not in msg

    _uvicorn_access = logging.getLogger("uvicorn.access")
    _uvicorn_access.addFilter(_Skip304Filter())

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )


def _auto_open_browser(host: str, port: int):
    """麒麟模式：延迟 3 秒后自动打开系统浏览器。

    优先使用 webbrowser 标准库，失败时回退到 xdg-open。
    仅在 KYLIN_MODE=true 时由 main() 调用。
    """
    import subprocess
    import threading
    import time
    import webbrowser

    def _open():
        time.sleep(3)  # 等待 Uvicorn 完成启动
        url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}"
        print(f"[Kylin] 正在打开浏览器: {url}")
        try:
            webbrowser.open(url)
            return
        except Exception as e:
            print(f"[Kylin] webbrowser.open 失败: {e}，尝试 xdg-open...")

        try:
            subprocess.Popen(["xdg-open", url], start_new_session=True)
        except Exception as e2:
            print(f"[Kylin] xdg-open 也不可用: {e2}")
            print(f"[Kylin] 请手动打开浏览器访问: {url}")

    threading.Thread(target=_open, daemon=True).start()


if __name__ == "__main__":
    main()
