"""`scripts/scan_mojibake.py` 门禁的回归测试（2026-10-26 体检后追加）。

## 为什么补这组测试

体检时发现两个真实缺口，二者都不是"扫描逻辑写错"，而是"守卫没被执行/误报导致
被无视"：

1. **误报让守卫失去可信度**：`frontend/logs-*.txt`（运行时日志，正常含 NUL 字节，
   且已被 .gitignore 忽略）让 `--check` 恒返回 1。本机 pre-commit 钩子又没安装，
   于是"扫描失败"与"提交照样过"长期并存 —— 守卫等于不存在。
2. **扫描自身会崩**：`os.path.getsize` 在 try 之外，扫描期间被并发 pytest 删除的
   临时库（`backend/backup_snapshot_*.db-journal`）让它直接抛 FileNotFoundError，
   本该是"报告损坏"的守卫自己变成崩溃源。

本文件同时钉住两件事：**被忽略的本地产物不再误报**、**未跟踪且未忽略的损坏仍必红**
——后者是负向用例，防止有人为了"变绿"把守卫削弱成空转。另外校验它真的接进了 CI。

测试工作副本放在仓库内的隐藏目录 `.scan-mojibake-tests/`：本机的 python 子进程
只能写工作区（%TEMP% 被沙箱拦下，`tempfile.gettempdir()` 会退回仓库根），而扫描器
本来就跳过 `.` 开头的目录，因此隐藏目录里的样本不会污染真实仓库的扫描结果。
"""

import importlib.util
import os
import pathlib
import re
import runpy
import shutil
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "scan_mojibake.py"

# 隐藏目录：os.walk 的 `not d.startswith('.')` 过滤会跳过它，真实仓库扫描不受影响
WORKSPACE_ROOT = REPO_ROOT / ".scan-mojibake-tests"

IMMEDIATE_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _suspect_chars():
    """从门禁脚本自身取出可疑字集合，避免测试文件里出现乱码字样本（会自伤扫描）。"""
    source = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"SUSPECT = set\('([^']+)'\)", source)
    assert match, "scan_mojibake.py 的 SUSPECT 定义形态变了，测试需同步"
    return match.group(1)


SUSPECT_CHARS = _suspect_chars()
# 双编样本：只用可疑字拼，保证跨"每文件 ≥8 次、单行 ≥3 次"两道阈值
MOJIBAKE_SAMPLE = SUSPECT_CHARS[:12] + "\n"

# NUL 样本（CodeCheck flake8 崩溃的同款形态）
NUL_BYTES = b"sourcemap\x00\x00garbage\n"


@pytest.fixture()
def workspace():
    """仓库内隐藏目录下的独立工作副本，用完即删。"""
    WORKSPACE_ROOT.mkdir(exist_ok=True)
    path = pathlib.Path(tempfile.mkdtemp(prefix="ws-", dir=str(WORKSPACE_ROOT)))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        try:
            WORKSPACE_ROOT.rmdir()
        except OSError:
            pass


def _run_scan(cwd):
    """以子进程方式在指定目录跑真实脚本（脚本按 cwd 扫描 '.'）。"""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=IMMEDIATE_ENV,
    )


def _git_init(path):
    """建一个最小 git 工作副本；git 不可用时直接失败，而不是静默退化成全量扫描。"""
    proc = subprocess.run(
        ["git", "init", "-q"],
        cwd=str(path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=IMMEDIATE_ENV,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    check = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=IMMEDIATE_ENV,
    )
    assert check.returncode == 0, check.stdout + check.stderr


class TestIgnoredArtifactsDoNotFail:
    def test_gitignored_runtime_log_with_nul_passes(self, workspace):
        """被 .gitignore 忽略的运行时日志含 NUL 属正常现象，不得判红。

        形态与真实的 `frontend/logs-v1173-fe.txt` 一致：文件在**非跳过**目录下，
        仅靠 .gitignore 排除；`logs/` 整目录名会被 SKIP_DIRS 跳过，测不出问题。
        """
        _git_init(workspace)
        (workspace / ".gitignore").write_text("frontend/logs-*.txt\n", encoding="utf-8")
        (workspace / "frontend").mkdir()
        (workspace / "frontend" / "logs-v1173-fe.txt").write_bytes(NUL_BYTES)
        (workspace / "app.py").write_text("print('ok')\n", encoding="utf-8")

        proc = _run_scan(workspace)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "NUL-byte files" not in proc.stdout


class TestVanishedFileTolerance:
    def test_file_deleted_between_listing_and_read_does_not_crash(self, workspace, monkeypatch, capsys):
        """扫描期间文件消失（并发 pytest 的临时库/日志）不得让守卫崩溃。"""
        (workspace / "boom.txt").write_text("hello\n", encoding="utf-8")
        (workspace / "ok.txt").write_text("world\n", encoding="utf-8")
        monkeypatch.chdir(workspace)
        monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--check"])

        real_getsize = os.path.getsize

        def fake_getsize(path):
            if os.path.basename(str(path)) == "boom.txt":
                raise FileNotFoundError(2, "No such file or directory", str(path))
            return real_getsize(path)

        monkeypatch.setattr(os.path, "getsize", fake_getsize)

        # 当前实现会抛 FileNotFoundError（红）；修复后应正常收尾且不判红
        runpy.run_path(str(SCRIPT), run_name="__main__")
        out = capsys.readouterr().out
        assert "OK" in out


class TestStillCatchesCorruption:
    def test_untracked_nul_file_is_rejected(self, workspace):
        """负向用例：未被忽略的损坏文件必须仍被判红（防"为变绿而削弱守卫"）。"""
        _git_init(workspace)
        (workspace / ".gitignore").write_text("frontend/logs-*.txt\n", encoding="utf-8")
        (workspace / "broken.py").write_bytes(b"x = 1\x00\n")

        proc = _run_scan(workspace)
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "broken.py" in proc.stdout

    def test_mojibake_file_is_rejected(self, workspace):
        """负向用例：GBK↔UTF-8 双编文本必须仍被判红。"""
        _git_init(workspace)
        (workspace / ".gitignore").write_text("frontend/logs-*.txt\n", encoding="utf-8")
        (workspace / "notes.md").write_text(MOJIBAKE_SAMPLE, encoding="utf-8")

        proc = _run_scan(workspace)
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "mojibake suspects: 1" in proc.stdout


class TestRepositoryPasses:
    def test_real_repository_passes(self):
        """真实仓库当前状态必须通过（否则 CI 会红，本用例会先红）。

        注意：这是唯一需要全仓扫描的用例，Windows 上耗时约 2 分钟。
        """
        proc = _run_scan(REPO_ROOT)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "[scan_mojibake --check] OK" in proc.stdout


class TestCiWiring:
    def test_scan_is_wired_into_ci(self):
        """门禁必须真的接进 CI —— 本机 pre-commit 钩子未安装时它是唯一执法点。"""
        workflow = (REPO_ROOT / ".github" / "workflows" / "pr-checks.yml").read_text(
            encoding="utf-8"
        )
        assert "scan_mojibake.py --check" in workflow


class TestModuleContract:
    def test_script_is_stdlib_only(self):
        """守卫脚本不允许引入第三方依赖：CI 在无后端依赖的作业里跑它。"""
        source = SCRIPT.read_text(encoding="utf-8")
        spec = importlib.util.spec_from_file_location("scan_mojibake_mod", SCRIPT)
        assert spec and spec.loader  # 至少可定位（不执行，避免真的扫全仓）
        for forbidden in ("import yaml", "import requests", "from fastapi"):
            assert forbidden not in source
