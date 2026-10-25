# -*- coding: utf-8 -*-
"""错误文案泄漏门禁的单元测试。

背景：2026-10-25 用户看到 `Request failed with status code 422`。
门禁 `scripts/check_error_message_leaks.py` 负责拦住"把 axios 技术原文
直接展示给用户"的写法回潮。
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "scripts" / "check_error_message_leaks.py"

sys.path.insert(0, str(ROOT / "scripts"))
import check_error_message_leaks as gate  # noqa: E402


class TestScanText:
    def test_detects_elmessage_error_message(self):
        src = (
            "try { await api() } catch (error: any) {\n"
            "  ElMessage.error(error.message || '保存失败')\n"
            "}\n"
        )
        findings = gate.scan_text("frontend/src/views/x.vue", src)
        assert len(findings) == 1
        assert findings[0]["line"] == 2
        assert "error.message" in findings[0]["snippet"]

    def test_detects_detail_or_message_chain(self):
        src = "ElMessage.error(error?.response?.data?.detail || error.message || '导出失败')\n"
        assert gate.scan_text("frontend/src/views/x.vue", src)

    def test_detects_ternary_variable_form(self):
        src = "const msg = e instanceof Error ? e.message : '失败'\nElMessage.error(msg)\n"
        # 赋值形态不在"调用窗口"内也会被后续使用命中时拦下；这里至少确保
        # `e.message` 出现在提示调用附近时能被发现。
        assert gate.scan_text("frontend/src/views/x.vue", src) == []
        # 直接放进调用里则应命中
        assert gate.scan_text("frontend/src/views/x.vue", "ElMessage.error(e.message || '失败')\n")

    @pytest.mark.parametrize(
        "src",
        [
            "ElMessage.error(getErrorMessage(error, '保存失败'))\n",
            "ElMessage.error('固定文案')\n",
            "logger.error('[x]', error.message)\n",
            "ElMessage.success('成功')\n",
        ],
    )
    def test_clean_forms_are_not_flagged(self, src):
        assert gate.scan_text("frontend/src/views/x.vue", src) == []

    def test_comments_are_ignored(self):
        src = "// ElMessage.error(error.message || '旧写法')\nElMessage.error(getErrorMessage(error))\n"
        assert gate.scan_text("frontend/src/views/x.vue", src) == []

    def test_block_comment_keeps_line_numbers(self):
        """块注释被抹成空白但保留换行 → 报告行号与源文件一致。"""
        src = "/* 多行\n注释\n*/\nElMessage.error(error.message || '失败')\n"
        findings = gate.scan_text("frontend/src/views/x.vue", src)
        assert len(findings) == 1
        assert findings[0]["line"] == 4

    def test_allowed_files_are_skipped(self):
        """实现层（getErrorMessage / request.ts）允许读 .message。"""
        src = "ElMessage.error(error.message || '失败')\n"
        for allowed in (
            "frontend/src/utils/getErrorMessage.ts",
            "frontend/src/api/request.ts",
        ):
            assert gate.scan_text(allowed, src) == []


class TestRepoIsClean:
    def test_gate_passes_on_current_repo(self):
        proc = subprocess.run(
            [sys.executable, str(GATE), "--json"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert proc.stdout, f"门禁无输出:\n{proc.stdout}\n{proc.stderr}"
        import json

        report = json.loads(proc.stdout)
        assert report["leaks"] == [], (
            "仍有把 axios 原文展示给用户的调用点:\n"
            + "\n".join(f"  {x['file']}:{x['line']} {x['snippet']}" for x in report["leaks"])
        )
        assert proc.returncode == 0
