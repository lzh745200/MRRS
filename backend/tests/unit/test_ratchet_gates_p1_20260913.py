"""P-1/P-2/P-3 棘轮门禁自测（遗留风险治理计划 2026-09-13）。

每个门禁两件事：
1. 合成样本上能**抓到**违规（防"门禁写了但从不报警"）；
2. 在真实仓库上跑 main() 必须 exit 0（防门禁对既有代码恒红，或被静默放宽）。
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_dir_replace  # noqa: E402
import check_os_exit  # noqa: E402
import check_scheduler_registration  # noqa: E402
import check_subprocess_encoding  # noqa: E402
import check_unbounded_read  # noqa: E402
import check_upload_endpoints  # noqa: E402


class TestOsExitGate:
    def test_detects_os_exit(self):
        hits = check_os_exit.scan_text("app/x.py", "import os\nos._exit(0)\n")
        assert len(hits) == 1 and "os._exit(0)" in hits[0]

    def test_ignores_mention_in_comment_and_string(self):
        src = '# 历史用 os._exit(0) 绕过 lifespan\nMSG = "os._exit(0)"\n'
        assert check_os_exit.scan_text("app/x.py", src) == []

    def test_honours_inline_exemption(self):
        src = "os._exit(0)  # nosec:os-exit 测试替身\n"
        assert check_os_exit.scan_text("app/x.py", src) == []

    def test_real_tree_is_clean(self):
        assert check_os_exit.main() == 0


class TestSubprocessEncodingGate:
    def test_detects_text_without_encoding(self):
        src = "import subprocess\nsubprocess.run(['x'], text=True)\n"
        assert len(check_subprocess_encoding.scan_text("tests/t.py", src)) == 1

    def test_passes_with_encoding(self):
        src = "subprocess.run(['x'], text=True, encoding='utf-8')\n"
        assert check_subprocess_encoding.scan_text("tests/t.py", src) == []

    def test_passes_without_text_flag(self):
        src = "subprocess.run(['x'], capture_output=True)\n"
        assert check_subprocess_encoding.scan_text("tests/t.py", src) == []

    def test_real_tree_is_clean(self):
        assert check_subprocess_encoding.main() == 0


class TestDirReplaceGate:
    def test_detects_copytree_without_dirs_exist_ok(self):
        src = (
            "shutil.rmtree(dst, ignore_errors=True)\n"
            "shutil.copytree(src, dst)\n"
        )
        hits = check_dir_replace.scan_text("app/x.py", src)
        assert len(hits) == 1 and "dirs_exist_ok" in hits[0]

    def test_passes_with_dirs_exist_ok(self):
        src = (
            "shutil.rmtree(dst, ignore_errors=True)\n"
            "shutil.copytree(src, dst, dirs_exist_ok=True)\n"
        )
        assert check_dir_replace.scan_text("app/x.py", src) == []

    def test_real_tree_is_clean(self):
        assert check_dir_replace.main() == 0


class TestUnboundedReadGate:
    def test_detects_zip_member_read(self):
        src = 'def f(zf):\n    return zf.read("manifest.json")\n'
        assert len(check_unbounded_read.scan_text("app/x.py", src)) == 1

    def test_detects_whole_file_read(self):
        src = "async def f(upload):\n    return await upload.read()\n"
        assert len(check_unbounded_read.scan_text("app/x.py", src)) == 1

    def test_passes_for_bounded_read(self):
        src = "async def f(fh):\n    return await fh.read(1024)\n"
        assert check_unbounded_read.scan_text("app/x.py", src) == []

    def test_passes_when_guard_used_in_same_function(self):
        src = (
            "def f(zf):\n"
            "    ensure_zip_within_limit(zf)\n"
            '    return zf.read("manifest.json")\n'
        )
        assert check_unbounded_read.scan_text("app/x.py", src) == []

    def test_honours_inline_exemption(self):
        src = "async def f(fh):\n    return await fh.read()  # nosec:unbounded-read 测试替身\n"
        assert check_unbounded_read.scan_text("app/x.py", src) == []

    def test_real_tree_is_clean(self):
        assert check_unbounded_read.main() == 0


class TestUploadEndpointGate:
    def test_detects_unguarded_upload_handler(self):
        src = (
            "from fastapi import UploadFile\n"
            "async def handler(file: UploadFile):\n"
            "    return await file.read()\n"
        )
        hits = check_upload_endpoints.scan_text("app/api/x.py", src)
        assert len(hits) == 1 and "handler" in hits[0]

    def test_passes_with_limit_helper(self):
        src = (
            "from fastapi import UploadFile\n"
            "async def handler(file: UploadFile):\n"
            "    return await read_upload_with_limit(file, 1024)\n"
        )
        assert check_upload_endpoints.scan_text("app/api/x.py", src) == []

    def test_passes_with_bounded_chunk_loop(self):
        src = (
            "from fastapi import UploadFile\n"
            "async def handler(file: UploadFile):\n"
            "    chunk = await file.read(1024 * 1024)\n"
        )
        assert check_upload_endpoints.scan_text("app/api/x.py", src) == []

    def test_passes_with_same_file_delegation(self):
        src = (
            "from fastapi import UploadFile\n"
            "async def _stream(file: UploadFile, path):\n"
            "    chunk = await file.read(1024)\n"
            "async def handler(file: UploadFile):\n"
            "    return await _stream(file, 'p')\n"
        )
        assert check_upload_endpoints.scan_text("app/api/x.py", src) == []

    def test_real_tree_is_clean(self):
        assert check_upload_endpoints.main() == 0


class TestSchedulerRegistrationGate:
    def test_detects_new_timer_outside_allowlist(self):
        src = "import threading\nthreading.Timer(5, job).start()\n"
        assert len(check_scheduler_registration.scan_text("app/services/new_job.py", src)) == 1

    def test_allowlisted_module_passes(self):
        src = "import threading\nthreading.Timer(5, job).start()\n"
        assert check_scheduler_registration.scan_text("app/main.py", src) == []

    def test_honours_inline_exemption(self):
        src = "threading.Timer(1, job)  # nosec:scheduler-registration 一次性\n"
        assert check_scheduler_registration.scan_text("app/services/x.py", src) == []

    def test_real_tree_is_clean(self):
        assert check_scheduler_registration.main() == 0
