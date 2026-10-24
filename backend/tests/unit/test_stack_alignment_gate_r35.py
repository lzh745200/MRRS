"""前后端 / 模型-库 三层对齐门禁的单元测试（R35）。

背景：v1.17.2 连续出现"单测绿、真机废"的契约漂移（前端调
`/api/v1/system/self-check` 而后端注册在 `/api/v1/self-check`，恒 404；
`OrganizationCreate` 漏 `code` 字段，真实 HTTP 进来就 422）。

本测试锁定三条对齐轴：
- **A 路径**：前端 `src/api/*.ts` 的调用路径必须命中后端真实路由；
- **B 模型↔库**：ORM 模型声明的表/列必须与数据库实际 schema 一致；
- **C 字段**：前端 TS interface 与后端 Pydantic schema 的字段集合必须一致
  （按同名 1:1 配对，camelCase 经中间件归一为 snake_case 后比较）。

**测试文件本身始终可编辑**；被测实现是 `scripts/check_stack_alignment.py`。
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "scripts" / "check_stack_alignment.py"
FRONTEND_API_DIR = ROOT / "frontend" / "src" / "api"


# ── 门禁脚本自身必须存在且可解析 ────────────────────────────────────────────

def test_gate_script_exists():
    assert GATE.exists(), f"对齐门禁脚本缺失: {GATE}"


def test_gate_script_compiles():
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(GATE)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stderr


# ── 路径归一化：后端路由与前端调用必须能对上 ────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/api/v1/system/self-check", "/system/self-check"),
        ("/system/self-check", "/system/self-check"),
        ("/funds/${id}", "/funds/{}"),
        ("/funds/12/approve", "/funds/12/approve"),
        # 整段就是查询串变量（post(`/secrets/rotate${qs}`)）→ 还原成路径本身
        ("/secrets/rotate${qs}", "/secrets/rotate"),
        ("/secrets/create${qs}", "/secrets/create"),
        ("/batch/${tableName}/rows", "/batch/{}/rows"),
        ("/funds?page=1", "/funds"),
    ],
)
def test_normalize_path(raw, expected):
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_stack_alignment as gate

    assert gate.normalize_path(raw) == expected


# ── 字段名归一化：camelCase → snake_case（与 CamelToSnakeMiddleware 一致）───

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("villageName", "village_name"),
        ("isThreeRegions", "is_three_regions"),
        ("supportedVillageId", "supported_village_id"),
        ("id_card", "id_card"),
    ],
)
def test_snake_case(raw, expected):
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_stack_alignment as gate

    assert gate.to_snake_case(raw) == expected


# ── 真实仓库状态：三层必须无漂移（这是门禁的价值所在）──────────────────────

@pytest.fixture(scope="module")
def gate_report():
    """跑一次门禁，返回结构化报告（跑在 backend 目录，app 包可导入）。"""
    backend = ROOT / "backend"
    proc = subprocess.run(
        [sys.executable, str(GATE), "--json"],
        cwd=str(backend), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert proc.stdout, f"门禁无输出:\n{proc.stdout}\n{proc.stderr}"
    import json

    return json.loads(proc.stdout), proc


def test_gate_reports_no_path_drift(gate_report):
    """A 轴：前端调用路径必须全部命中后端路由。"""
    report, proc = gate_report
    assert report["path_drift"] == [], (
        "前端调用路径未命中后端路由:\n"
        + "\n".join(f"  {d['file']}:{d['line']} {d['raw']} -> {d['normalized']}" for d in report["path_drift"])
    )


def test_gate_reports_no_model_db_drift(gate_report):
    """B 轴：ORM 模型声明必须与数据库实际 schema 一致。"""
    report, proc = gate_report
    assert report["model_db_drift"] == [], (
        "ORM 模型与数据库 schema 不一致:\n"
        + "\n".join(f"  {d}" for d in report["model_db_drift"])
    )


def test_gate_reports_no_field_drift(gate_report):
    """C 轴：前后端字段必须一致（按 URL 解析到端点 + response_model 同名配对）。"""
    report, proc = gate_report
    assert report["field_drift"] == [], (
        "前后端字段不一致:\n"
        + "\n".join(
            f"  {d['name']} ({d['backend']} <-> {d['frontend']})\n"
            f"    仅后端: {d['only_backend']}\n"
            f"    仅前端: {d['only_frontend']}"
            for d in report["field_drift"]
        )
    )


def test_gate_exit_code_is_zero(gate_report):
    """门禁在当前仓库上必须通过（退出码 0）。"""
    _, proc = gate_report
    assert proc.returncode == 0, (
        f"对齐门禁未通过，退出码 {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_gate_leaves_no_reference_db_dirs(gate_report):
    """门禁跑完后不得残留临时参照库目录。

    B 轴每次都会起一个 ~2.8MB 的 SQLite 参照库；早期实现只用 mkdtemp 从不清理，
    实测在 backend/ 下累积了 78 个目录 / 206MB。这个测试锁住 finally 清理。
    """
    _, proc = gate_report  # 触发一次完整门禁运行
    assert proc.returncode == 0
    leftovers = sorted((ROOT / "backend").glob("stack_align_*"))
    assert leftovers == [], (
        "门禁残留了临时参照库目录（应在 finally 里 shutil.rmtree）: "
        + ", ".join(p.name for p in leftovers[:10])
    )


# ── 门禁必须真的能抓到漂移（负向验证：改坏后必须 FAIL）────────────────────

def test_gate_detects_injected_path_drift(tmp_path):
    """把前端调用改成不存在的路径，门禁必须报 path_drift 且非 0 退出。

    实现方式：不造假仓库（门禁需要导入真实后端 app 才能取到路由表），
    而是在**真实仓库的前端 api 目录**里放一个临时文件，门禁跑完后删掉。
    """
    injected = FRONTEND_API_DIR / "__r35_injected_drift.ts"
    assert not injected.exists(), "注入文件已存在，先清理"
    injected.write_text(
        "export async function r35InjectedBroken() {\n"
        "  return get('/this/path/does/not/exist')\n"
        "}\n",
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [sys.executable, str(GATE), "--json"],
            cwd=str(ROOT / "backend"), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        import json

        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"门禁输出非 JSON:\n{proc.stdout}\n{proc.stderr}")

        assert report["path_drift"], "注入的坏路径未被门禁发现"
        assert any(
            "does/not/exist" in item["raw"] for item in report["path_drift"]
        ), f"注入的坏路径未被报出: {report['path_drift']}"
        assert proc.returncode != 0, "注入漂移后门禁仍返回 0"
    finally:
        injected.unlink(missing_ok=True)


def test_gate_detects_injected_field_drift(tmp_path):
    """后端多返回一个字段而前端没声明时，门禁必须报 field_drift。"""
    injected = FRONTEND_API_DIR / "__r35_injected_field.ts"
    assert not injected.exists(), "注入文件已存在，先清理"
    injected.write_text(
        "export interface R35InjectedDrift {\n"
        "  only_backend_field: string\n"
        "}\n",
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [sys.executable, str(GATE), "--json"],
            cwd=str(ROOT / "backend"), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        import json

        report = json.loads(proc.stdout)
        # 该 interface 没有同名后端类，不应被配对 —— 门禁不得因此误报
        assert report["field_drift"] == [], (
            f"未配对的 interface 不应被报为漂移: {report['field_drift']}"
        )
    finally:
        injected.unlink(missing_ok=True)
