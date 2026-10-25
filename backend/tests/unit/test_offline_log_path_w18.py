"""W18-offline P0-1 回归：打包态不得覆盖 Electron 注入的日志路径。

缺陷（.scratch/w18-deep-probe/02-offline-runtime.md P0-1）
  config.Settings 在 sys.frozen 时无条件把 LOG_FILE 改写为
  {data_dir}/logs/app.log（LOCALAPPDATA/bumofu-assistance/...），而 Electron
  主进程经环境变量注入的是 userData/logs/app.log。结果：诊断包、修复引导页、
  文档四处全部指向不存在的日志 —— 现场首次装机失败时唯一的自助通道失效。

修复口径：仅当 LOG_FILE 仍是相对默认值（./logs/app.log）时才改写；
Electron 注入的绝对路径一律尊重。

实现说明：路径改写逻辑在 Settings.__init__ 内联执行，无法在构造后再触发；
因此这里用「构造参数」驱动同一分支 —— 传入绝对 LOG_DIR/LOG_FILE 模拟 Electron
注入，断言构造完成后值未被改写。
"""
import os
import sys

import pytest


def _make_settings(**kwargs):
    from app.core.config import Settings

    return Settings(**kwargs)


INJECTED_DIR = r"C:\\Users\\u\\AppData\\Roaming\\Assistance-Management-Information-System\\logs"
INJECTED_FILE = INJECTED_DIR + r"\\app.log"


class TestFrozenLogPath:
    def test_absolute_log_file_is_respected_when_frozen(self, monkeypatch):
        """核心缺陷回归：Electron 注入的绝对路径必须原样保留（打包态）。

        原先用 skipif 跳过开发机，等于这条**核心回归永远只在 CI 打包环境**才验证，
        本地改动无法自查。改为在测试内 monkeypatch sys.frozen=True ——
        Settings 构造期读的就是该标志，与真实打包态走同一分支。
        """
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        s = _make_settings(LOG_DIR=INJECTED_DIR, LOG_FILE=INJECTED_FILE)
        assert s.LOG_DIR == INJECTED_DIR
        assert s.LOG_FILE == INJECTED_FILE

    def test_absolute_log_file_untouched_in_dev(self):
        """开发机（非 frozen）注入的绝对路径同样不被改写。"""
        s = _make_settings(LOG_DIR=INJECTED_DIR, LOG_FILE=INJECTED_FILE)
        assert s.LOG_FILE == INJECTED_FILE

    def test_relative_default_is_rewritten_when_frozen(self):
        """打包态下相对默认值仍要改写到数据目录（保持既有安装行为）。"""
        s = _make_settings(LOG_DIR="./logs", LOG_FILE="./logs/app.log")
        if getattr(sys, "frozen", False):
            assert not s.LOG_FILE.startswith("./")
            assert not s.LOG_DIR.startswith("./")
        else:
            # 开发机：frozen 分支不触发，相对值保留（现有行为）
            assert s.LOG_FILE == "./logs/app.log"

    def test_electron_injection_shape_matches_env_contract(self):
        """契约锁：Electron main.js 注入的 LOG_FILE 是绝对路径（path.join 产物）。

        若未来 Electron 端改成相对路径，config 的新守卫（startswith("./")）
        会把它误改写 —— 该用例会让契约漂移显形。
        """
        import io

        import app.core.config as cfg_mod

        core_dir = os.path.dirname(os.path.abspath(cfg_mod.__file__))       # backend/app/core
        backend_dir = os.path.dirname(os.path.dirname(core_dir))            # backend
        repo_root = os.path.dirname(backend_dir)                            # repo
        main_js = os.path.join(repo_root, "electron", "main.js")
        assert os.path.exists(main_js), f"electron/main.js not found at {main_js}"
        src = io.open(main_js, encoding="utf-8").read()
        # Electron 注入 LOG_FILE 用 path.join(logsDir, ...) —— logsDir 出自 getUserDataPath()
        assert "LOG_FILE: path.join(logsDir" in src
        assert "getUserDataPath" in src

    def test_config_guard_only_rewrites_relative(self):
        """config 源码必须含新守卫：LOG_FILE 仅在相对时才改写。"""
        import io

        from app.core import config as cfg_mod

        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(cfg_mod.__file__))),
            "core", "config.py",
        )
        src = io.open(src_path, encoding="utf-8").read()
        # 新守卫存在：LOG_FILE 改写嵌套在 startswith("./") 判断内
        assert 'self.LOG_FILE.startswith("./")' in src
