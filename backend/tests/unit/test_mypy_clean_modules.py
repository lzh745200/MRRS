# -*- coding: utf-8 -*-
"""模块级 mypy「零错误」守卫 + runtime_secrets 路径契约回归。

## 为什么

仓库 mypy 基线是 **1391 errors**（棘轮只保不增加）。批 2 开始按模块收紧：
先挑「被 core.config 传递依赖、错误数小」的两个模块清零 ——

1. `app/core/logging_config.py`：`file_handler` 先赋 Timed 再赋 Rotating，mypy 按首赋值
   推断成 Timed 后把 else 分支判冲突（真实类型契约不一致）；
2. `app/utils/runtime_secrets.py`：`_atomic_write_json(path: Path)` 却被传 `str`、
   `_load_secrets_file(secrets_file: str)` 却被传 `Path` —— 函数契约自相矛盾。

本文件锁住这两点：谁再把签名改回去、或换回冲突的 handler 变量，测试立即变红。
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
CLEAN_MODULES = ["app/core/logging_config.py", "app/utils/runtime_secrets.py"]


class TestMypyCleanModules:
    def test_selected_modules_have_zero_mypy_errors(self):
        if importlib.util.find_spec("mypy") is None:
            pytest.skip("mypy 未安装（本地可选依赖；CI static-analysis 作业会跑全量）")

        proc = subprocess.run(
            [sys.executable, "-m", "mypy", *CLEAN_MODULES, "--ignore-missing-imports"],
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert proc.returncode == 0, (
            "mypy 在这两个已收紧的模块上发现错误（说明类型契约被改回去了）：\n"
            + (proc.stdout or "")[-3000:]
        )


class TestRuntimeSecretsPathContract:
    """`str` 与 `Path` 两种入参必须都可用（曾被 mypy 抓出混用）。"""

    def test_atomic_write_and_load_accept_both_str_and_path(self, tmp_path):
        from app.utils import runtime_secrets

        as_path = tmp_path / "secrets_path.json"
        runtime_secrets._atomic_write_json(as_path, {"SECRET_KEY": "k1"})
        loaded, usable = runtime_secrets._load_secrets_file(as_path)
        assert usable is True and loaded["SECRET_KEY"] == "k1"

        as_str = str(tmp_path / "secrets_str.json")
        runtime_secrets._atomic_write_json(as_str, {"SECRET_KEY": "k2"})
        assert json.loads(Path(as_str).read_text(encoding="utf-8"))["SECRET_KEY"] == "k2"
        loaded2, usable2 = runtime_secrets._load_secrets_file(as_str)
        assert usable2 is True and loaded2["SECRET_KEY"] == "k2"

    def test_persist_accepts_path(self, tmp_path, monkeypatch):
        from app.utils import runtime_secrets

        target = tmp_path / "persisted.json"
        runtime_secrets._persist_runtime_secrets(target, {}, "a" * 40, "b" * 40)

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["SECRET_KEY"] == "a" * 40
        assert payload["CSRF_SECRET_KEY"] == "b" * 40
