# -*- coding: utf-8 -*-
"""F2 覆盖率豁免 ratchet 检查器的回归（`scripts/check_pragma_reasons.py`）。

背景：《架构评估整改配套约定》F2 条规定"`# pragma: no cover` 必须同行注明理由，
无理由视同违规"，但该规则此前零执行力（实测 backend/app 170 处 pragma 中
128 处无理由）。本文件锁定检查器本身的行为：

1. **只认注释里的 pragma**：字符串/文档串里出现 `"# pragma: no cover"`
   （检查器自身的实现行与 help 文案即是）不得被误判 —— 自检时实测报过 2 处假阳性；
2. **理由判定**：`— 说明` / `: 说明` / 后跟 `# 说明` 均算有理由；裸 pragma 算违规；
3. **ratchet 语义**：默认只查新增/修改行（含未跟踪新文件），存量裸 pragma 不阻断，
   但 `--max-bare` 上限超标即失败；基线不可用时**报错退出**（不静默通过），
   除非显式 `--allow-missing-base`。
"""

import importlib.util
import io
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "check_pragma_reasons.py"

_spec = importlib.util.spec_from_file_location("check_pragma_reasons", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class TestReasonDetection:
    @pytest.mark.parametrize(
        "line",
        [
            "    except Exception:  # pragma: no cover — 仅防御性兜底",
            "    except Exception:  # pragma: no cover - defensive",
            "    except Exception:  # pragma: no cover: 不可达分支",
            "    except Exception:  # pragma: no cover  # 线程内异常注入成本过高",
        ],
    )
    def test_reasoned_pragma_ok(self, line):
        assert mod.has_reason(line) is True

    @pytest.mark.parametrize(
        "line",
        [
            "    except Exception:  # pragma: no cover",
            "    except Exception:  # pragma: no cover ",
            "    except Exception:  # pragma: no cover —",
        ],
    )
    def test_bare_pragma_flagged(self, line):
        assert mod.has_reason(line) is False

    def test_line_without_pragma_is_irrelevant(self):
        assert mod.has_reason("x = 1") is True


class TestCommentOnlyDetection:
    def test_string_literal_is_not_a_pragma(self, tmp_path):
        """字符串里的标记不算豁免（否则检查器会误报自己）。"""
        probe = tmp_path / "probe.py"
        probe.write_text(
            'MARKER = "# pragma: no cover"\n'
            'HELP = "检查 # pragma: no cover 是否带理由"\n',
            encoding="utf-8",
        )
        assert list(mod._pragma_comments(str(probe))) == []

    def test_real_comment_is_detected(self, tmp_path):
        probe = tmp_path / "probe.py"
        probe.write_text(
            "def f():\n"
            "    return 1  # pragma: no cover — 说明\n",
            encoding="utf-8",
        )
        found = list(mod._pragma_comments(str(probe)))
        assert found and found[0][0] == 2

    def test_syntax_error_falls_back_to_line_scan(self, tmp_path):
        """语法错误的文件不能把检查器带崩：退回行扫描。"""
        probe = tmp_path / "broken.py"
        probe.write_text("def f(:\n    x  # pragma: no cover\n", encoding="utf-8")
        found = list(mod._pragma_comments(str(probe)))
        assert found and found[0][0] == 2


class TestRepoWideScan:
    def test_repo_has_pragmas_and_they_are_counted(self):
        # 用绝对路径：pytest 的 CWD 是 backend/，相对路径 "backend/app" 会扫不到
        rows = list(mod.iter_pragma_lines([str(ROOT / "backend" / "app")]))
        assert len(rows) > 50  # 仓库确实大量使用豁免
        # 每行都必须是注释内容，不能是整行源码
        assert all("# pragma: no cover" in comment for _p, _n, comment in rows)

    def test_max_bare_ceiling_fails_loudly(self):
        """上限设为 0 必然超标 → 退出码 1（证明该门禁真的会拦）。"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--max-bare", "0"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert result.returncode == 1
        assert "::error::" in result.stdout

    def test_missing_base_is_not_silent(self):
        """基线不可用且未允许缺失 → 退出码 2（绝不静默通过）。"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff-base", "no-such-ref-xyz"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert result.returncode == 2

    def test_missing_base_allowed_warns_and_passes(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff-base", "no-such-ref-xyz",
             "--allow-missing-base", "--max-bare", "100000"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert result.returncode == 0
        assert "WARNING" in result.stdout

    def test_new_bare_pragma_in_working_tree_is_detected(self, tmp_path):
        """工作区新增的裸 pragma 必须被 --diff-base 命中（含未跟踪文件）。

        基线用 **HEAD** 而非 HEAD~1：`git diff HEAD` 比的是"HEAD → 工作区"，
        在有未提交改动时必然有内容，因此在 CI 的浅克隆（fetch-depth=1，没有
        HEAD~1）与本地完整克隆下**结果一致** —— 首版用 HEAD~1 导致 Linux CI
        直接失败（`无可用 diff 基线`），这里固化正确用法。
        """
        probe = ROOT / "scripts" / "_pragma_probe_tmp.py"
        probe.write_text(
            "def probe():  # pragma: no cover\n    return 1\n", encoding="utf-8"
        )
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--diff-base", "HEAD"],
                capture_output=True, text=True, cwd=str(ROOT),
            )
            assert result.returncode == 1, result.stdout
            assert "_pragma_probe_tmp.py" in result.stdout
        finally:
            probe.unlink(missing_ok=True)
