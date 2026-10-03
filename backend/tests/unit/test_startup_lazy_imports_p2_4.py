"""P2-4 启动优化：重依赖不进 import 期（行为级契约测试）。

背景（2026-10-03 实测）
-----------------------
`import app.main`（冷启动路径：app 创建 + 中间件 + 路由注册）阶段，openpyxl 的
导入累计 **~760ms**（其中 numpy ~197ms，经 `openpyxl.compat.numbers` 连带引入），
是冷启动路径上最值得推迟的一笔开销。

本轮曾出现过「以为已经惰性化、实际并没有」的回退：`supported_village.py` 已把
openpyxl 移入端点内，但另有 6 个模块仍在模块级 `import openpyxl`，导致
openpyxl 依旧在 import 期被加载 —— 单点惰性化收益为 **0**。

因此本文件用**行为级**断言（而非源码文本扫描）守护该契约：
任何一处新增/回退的模块级重依赖导入都会让 `test_startup_path_loads_no_heavy_dependency` 失败。

与 `test_map_lazy_cache_p2_4.py` 互补：那份守 map 的 diskcache 惰性**构造**，
本份守「重依赖不进 import 期」这一更上游的前提。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

# 冷启动路径上不允许出现的重依赖（按实测耗时排序：openpyxl ~760ms 含 numpy ~197ms）
_FORBIDDEN_AT_STARTUP = ("openpyxl", "numpy", "pandas", "matplotlib", "reportlab")

_CHILD_SNIPPET = (
    "import json, sys\n"
    "import app.main  # 冷启动路径（与生产同样的一次性导入）\n"
    "loaded = [m for m in json.loads(sys.argv[1]) if m in sys.modules]\n"
    "print('LOADED=' + json.dumps(loaded))\n"
)


def _child_env(tmpdir: str) -> dict:
    """构造子进程环境：UTF-8 + backend 上 sys.path + 数据目录隔离到 tmpdir。

    与 `scripts/measure_startup.py::_child_env` 同口径，保证子进程是干净冷启动，
    且不会污染真实仓库数据目录。
    """
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("ENVIRONMENT", "test")
    env.setdefault("SECRET_KEY", "test-secret-key-for-ci")
    env["BUMOFU_BACKEND_DIR_OVERRIDE"] = tmpdir
    env["BUMOFU_DEV_MODE"] = "1"
    return env


class TestHeavyDepsNotOnStartupPath:
    """冷启动路径不得引入重依赖（P2-4 的核心契约）。"""

    def test_startup_path_loads_no_heavy_dependency(self, tmp_path):
        """全新解释器 import app.main 后，重依赖一个都不应在 sys.modules 中。

        失败即说明某模块又回到了 import 期加载 openpyxl/numpy 等 —— 冷启动白白慢
        ~760ms（这类回退无法靠单点惰性化修补，必须找到全部模块级导入点）。
        """
        proc = subprocess.run(
            [sys.executable, "-c", _CHILD_SNIPPET, json.dumps(list(_FORBIDDEN_AT_STARTUP))],
            cwd=str(BACKEND_DIR),
            env=_child_env(str(tmp_path)),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        assert proc.returncode == 0, f"子进程启动失败：{proc.stderr[-2000:]}"

        loaded = None
        for line in proc.stdout.splitlines():
            if line.startswith("LOADED="):
                loaded = json.loads(line[len("LOADED=") :])
        assert loaded is not None, f"未取到子进程结论：{proc.stdout[-2000:]}"
        assert loaded == [], f"冷启动路径引入了重依赖（应改为函数内惰性导入）：{loaded}"


class TestExcelTemplateStylesLazy:
    """Excel 模板样式对象：首次使用时才构造，且跨调用复用（不重复创建）。"""

    def test_styles_built_on_first_use(self, monkeypatch):
        """样式对象在真正生成模板前不存在，生成后进入模块全局。"""
        from app.services import excel_template_service as mod

        # 模拟"尚未构造"的初始状态（正常情况下本进程内可能已被其它用例构造过）
        monkeypatch.delitem(mod.__dict__, "_title_font", raising=False)
        assert "_title_font" not in vars(mod)

        mod.ExcelTemplateService().generate_village_template()

        assert "_title_font" in vars(mod)
        assert "_title_fill" in vars(mod)

    def test_styles_reused_across_calls(self):
        """第二次生成模板复用同一批样式对象（守住"复用避免重复创建"的语义）。"""
        from app.services import excel_template_service as mod

        svc = mod.ExcelTemplateService()
        svc.generate_village_template()
        first_title_font = vars(mod)["_title_font"]
        first_center_align = vars(mod)["_center_align"]

        svc.generate_project_template()

        assert vars(mod)["_title_font"] is first_title_font
        assert vars(mod)["_center_align"] is first_center_align
