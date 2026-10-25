"""分页上限门禁（`backend/scripts/check_pagination_cap.py`）的回归测试。

覆盖三件事：
1. 门禁**能红**：裸 `page_size: int = 20` 必须被抓到；`le=500 > MAX_PAGE_SIZE` 也必须被抓到。
2. 门禁**能绿**：`le=MAX_PAGE_SIZE` / `le=100`（更严格）都算合规。
3. 真实仓库当前状态通过，`MAX_PAGE_SIZE` 与前端调用习惯一致（200）。

为什么盯这个：离线单机里 `page_size` 无上限不是"慢一点"，而是一次实例化上千 ORM 对象
（含加密 PII 列），Electron 侧拿到超大 JSON 会卡死 —— 现场表现是"点一下列表就白屏"。
2026-10-25 排查发现 4 处裸 int 声明与 1 处 le=500，本测试锁住它们不再复发。
"""

import importlib.util
import pathlib

import pytest

# backend/tests/unit/test_pagination_cap_gate.py
# parents[0]=unit, [1]=tests, [2]=backend, [3]=仓库根
BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
SCRIPT = BACKEND_ROOT / "scripts" / "check_pagination_cap.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_pagination_cap_mod", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load()


def _make_api(tmp_path: pathlib.Path, source: str) -> pathlib.Path:
    root = tmp_path / "backend"
    api = root / "app" / "api" / "v1"
    api.mkdir(parents=True)
    (root / "app" / "core").mkdir(parents=True)
    (root / "app" / "core" / "constants.py").write_text("MAX_PAGE_SIZE = 200\n", encoding="utf-8")
    (api / "sample.py").write_text(source, encoding="utf-8")
    return root


class TestGateCanFail:
    def test_bare_page_size_is_flagged(self, mod, tmp_path):
        root = _make_api(tmp_path, "def f(\n    page_size: int = 20,\n):\n    pass\n")
        problems = mod.scan(root, 200)
        assert problems and "没有上限" in problems[0]

    def test_cap_above_max_is_flagged(self, mod, tmp_path):
        root = _make_api(
            tmp_path,
            "def f(\n    page_size: int = Query(20, ge=1, le=500),\n):\n    pass\n",
        )
        problems = mod.scan(root, 200)
        assert problems and "超过 MAX_PAGE_SIZE" in problems[0]

    def test_missing_api_dir_reports_clearly(self, mod, tmp_path):
        problems = mod.scan(tmp_path, 200)
        assert problems and "找不到" in problems[0]


class TestGateCanPass:
    def test_constant_reference_is_compliant(self, mod, tmp_path):
        root = _make_api(
            tmp_path,
            "def f(\n    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),\n):\n    pass\n",
        )
        assert mod.scan(root, 200) == []

    def test_stricter_literal_is_compliant(self, mod, tmp_path):
        root = _make_api(
            tmp_path,
            "def f(\n    page_size: int = Query(20, ge=1, le=100),\n):\n    pass\n",
        )
        assert mod.scan(root, 200) == []


class TestRealRepository:
    def test_repository_passes_gate(self):
        proc = __import__("subprocess").run(
            [__import__("sys").executable, str(SCRIPT), "--root", str(BACKEND_ROOT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_max_page_size_matches_frontend_usage(self, mod):
        """上限必须是 200：前端有 21 处 `page_size: 200`，设成 100 会直接 422。"""
        assert mod._max_page_size(BACKEND_ROOT / "app" / "core" / "constants.py") == 200

    def test_previously_unbounded_endpoints_now_have_cap(self):
        for rel in (
            "app/api/v1/machine_code.py",
            "app/api/v1/organization.py",
            "app/api/v1/auth/users.py",
            "app/api/v1/feedback.py",
            "app/api/v1/messages.py",
        ):
            text = (BACKEND_ROOT / rel).read_text(encoding="utf-8")
            assert "MAX_PAGE_SIZE" in text, f"{rel} 未引用 MAX_PAGE_SIZE（分页上限缺失）"
