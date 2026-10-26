#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R35 三层对齐门禁 —— 前端接口层 ↔ 后端路由/Pydantic ↔ 数据库 schema

## 为什么需要

v1.17.2 连续出现"单测绿、真机废"的契约漂移：

* 前端调 ``/api/v1/system/self-check``，后端注册在 ``/api/v1/self-check`` → 恒 404；
* ``OrganizationCreate`` 漏 ``code`` 字段 → 真实 HTTP 进来就 422。

单测用 MagicMock 传 ``data`` 不会暴露这类问题 —— 只有**把三层放在一起比**才能。

## 三条对齐轴

| 轴 | 比什么 | 数据源 |
|---|---|---|
| **A 路径** | 前端 ``src/api/*.ts`` 的调用路径 vs 后端真实路由 | 导入 ``app.main`` 取路由表 |
| **B 模型↔库** | ORM 模型声明的表/列 vs **alembic upgrade head 后的空库** | 临时目录起空库跑迁移 |
| **C 字段** | 前端 TS interface vs 后端 Pydantic schema | AST 解析 + 模块内作用域解析 |

B 轴**固定用"迁移到 head 的临时库"**作为基线，不读本机开发库 ——
否则本地库的脏数据会让门禁结果漂移，CI 也跑不了。

C 轴只对「后端类名与前端 interface 名**完全相同**、且各自在全局**唯一**」的
配对生效；同名不同义的配对（如 ``AggregateQuery`` / ``MonitorSnapshot`` / ``Fund``）
一律不配对、不报错。

## 用法

    python scripts/check_stack_alignment.py            # 人读格式，退出码 0=通过 1=有漂移
    python scripts/check_stack_alignment.py --json     # 机器读 JSON（供单测断言）

CI 调用方式：在 ``backend/`` 目录下运行（``app`` 包需要可导入）。
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND_API = ROOT / "frontend" / "src" / "api"
FRONTEND_TYPES = ROOT / "frontend" / "src" / "types"

# ── 归一化工具 ──────────────────────────────────────────────────────────────

# 后端路径参数 {village_id} 与前端模板段 ${id}
_PATH_PARAM_RE = re.compile(r"\{[^}/]+\}")
_TEMPLATE_RE = re.compile(r"\$\{[^}]*\}")


def normalize_path(raw: str) -> str:
    """把前后端路径归一到同一形态，便于比对。

    步骤：剥离查询串 → 模板段 ``${x}`` 与路径参数 ``{x}`` 统一成 ``{}``
    → 去掉 ``/api/v1`` 前缀 → 去掉尾斜杠。

    注：``${qs}`` 这类"整段就是一个查询串变量"的写法（如
    ``post(`/secrets/rotate${qs}`)``）在归一后应还原成 ``/secrets/rotate``
    而不是 ``/secrets/rotate{}`` —— 因为 ``${qs}`` 整体就是一个 ``?a=1`` 片段。
    """
    path = raw.split("?", 1)[0]
    # 整段就是查询串变量的情况：${qs} / ${query} 之类，直接删掉
    path = re.sub(r"\$\{(?:qs|query|search|params)\}$", "", path, flags=re.I)
    path = _TEMPLATE_RE.sub("{}", path)
    path = _PATH_PARAM_RE.sub("{}", path)
    path = re.sub(r"\{+", "{", path)
    path = path.rstrip("/") or "/"
    if path.startswith("/api/v1"):
        path = path[len("/api/v1"):] or "/"
    return path


def to_snake_case(name: str) -> str:
    """camelCase → snake_case（与 CamelToSnakeMiddleware 的键名转换一致）。"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


# ── A 轴：前端调用路径 vs 后端路由 ──────────────────────────────────────────

# 只抓"调用位置"的路径：get('/x') / post(`${BASE}/x`) / { url: '/x' }
_CALL_RE = re.compile(
    r"""(?:\b(?:get|post|put|del|patch)\s*(?:<[^>]*>)?\s*\(\s*|url\s*:\s*)(['"`])((?:\\.|(?!\1).)*)\1"""
)
# 同文件里的 const 常量：const BASE = '/funds'
_CONST_RE = re.compile(r"^const\s+(\w+)\s*(?::\s*string\s*)?=\s*['\"]([^'\"]+)['\"]", re.M)


def _strip_comments(text: str) -> str:
    """去掉行注释与块注释，避免把文档示例里的路径当成真实调用。"""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(?m)//.*$", "", text)
    return text


def collect_backend_routes() -> set[str]:
    """取后端真实路由（归一化后）。"""
    sys.path.insert(0, str(BACKEND))
    from app.main import app  # noqa: PLC0415

    routes: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path or not path.startswith("/api"):
            continue
        routes.add(normalize_path(path))
    return routes


def collect_frontend_calls() -> list[tuple[str, int, str, str]]:
    """扫前端 api 层，返回 [(文件名, 行号, 原始文本, 归一化路径)]。"""
    calls: list[tuple[str, int, str, str]] = []
    if not FRONTEND_API.exists():
        return calls
    for path in sorted(FRONTEND_API.glob("*.ts")):
        if path.name.endswith(".test.ts"):
            continue
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        consts = dict(_CONST_RE.findall(text))
        for match in _CALL_RE.finditer(text):
            raw = match.group(2)
            resolved = raw
            for key, value in consts.items():
                resolved = resolved.replace("${" + key + "}", value)
            if not resolved.startswith("/") or resolved.startswith("//"):
                continue
            # 后端可能带 /api/v1 前缀；两种形态都试
            normalized = normalize_path(resolved)
            line_no = text[: match.start()].count("\n") + 1
            calls.append((path.name, line_no, raw, normalized))
    return calls


def check_path_alignment() -> list[dict]:
    """A 轴：返回未命中后端路由的前端调用。"""
    routes = collect_backend_routes()
    drift: list[dict] = []
    for filename, line_no, raw, normalized in collect_frontend_calls():
        if normalized in routes:
            continue
        # 前端是后端路由的前缀也算命中（如 /system/backup 覆盖 /system/backup/stats）
        if any(route.startswith(normalized + "/") for route in routes):
            continue
        drift.append(
            {"file": filename, "line": line_no, "raw": raw, "normalized": normalized}
        )
    return drift


# ── B 轴：ORM 模型 ↔ 数据库 schema ──────────────────────────────────────────

def _load_model_metadata():
    """导入全部模型，返回 SQLAlchemy MetaData。"""
    sys.path.insert(0, str(BACKEND))
    import importlib  # noqa: PLC0415
    import pkgutil  # noqa: PLC0415

    import app.models as models_pkg  # noqa: PLC0415
    from app.models.base import Base  # noqa: PLC0415

    for module in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module("app.models." + module.name)
    return Base.metadata


def _build_reference_db() -> Path:
    """在临时目录起一个空库并迁移到 head。失败时自动清理并抛出。"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="stack_align_"))
    db_path = tmp_dir / "reference.db"
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(
            "alembic upgrade head 失败，无法建立参照库:\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
    return tmp_dir


def check_model_db_alignment() -> list[str]:
    """B 轴：返回 ORM 模型与参照库之间的表/列差异描述。

    每次运行都会在临时目录建一个 ~2.8MB 的 SQLite 参照库，**必须**在 finally
    里删除 —— 否则跑一次留一个目录，磁盘会无限增长。
    """
    from sqlalchemy import create_engine, inspect  # noqa: PLC0415

    metadata = _load_model_metadata()
    tmp_dir = _build_reference_db()
    try:
        db_path = tmp_dir / "reference.db"
        engine = create_engine(f"sqlite:///{db_path.as_posix()}")
        try:
            inspector = inspect(engine)

            db_tables = set(inspector.get_table_names())
            # alembic 自身的版本表不是业务表
            db_tables.discard("alembic_version")
            model_tables = set(metadata.tables.keys())

            issues: list[str] = []
            for name in sorted(model_tables - db_tables):
                issues.append(f"模型声明的表 {name} 在数据库中不存在")
            for name in sorted(db_tables - model_tables):
                issues.append(f"数据库存在表 {name} 但模型未声明")

            for name in sorted(model_tables & db_tables):
                table = metadata.tables[name]
                db_columns = {col["name"] for col in inspector.get_columns(name)}
                model_columns = set(table.columns.keys())
                for column in sorted(model_columns - db_columns):
                    issues.append(f"{name}.{column} 模型声明了但数据库没有该列")
                for column in sorted(db_columns - model_columns):
                    issues.append(f"{name}.{column} 数据库有该列但模型未声明")

            return issues
        finally:
            engine.dispose()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── C 轴：前端 interface ↔ 后端 Pydantic schema ────────────────────────────

# 前端 interface 字段：形如 "  field_name?: string"
_FE_FIELD_RE = re.compile(r"^\s{2}(\w+)\??\s*:", re.M)


def _collect_backend_schemas() -> dict[str, set[str]]:
    """后端 BaseModel 子类 → 字段集合（同名类按模块作用域各自记录）。

    返回 ``{类名: [(文件, 字段集合), ...]}``；同名类出现在多个文件时保留多条，
    由配对阶段按"全局唯一"规则决定是否启用。
    """
    found: dict[str, list[tuple[str, set[str]]]] = {}
    for path in sorted((BACKEND / "app").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {getattr(b, "id", None) or getattr(b, "attr", None) for b in node.bases}
            if "BaseModel" not in bases:
                continue
            fields: set[str] = set()
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields.add(stmt.target.id)
            found.setdefault(node.name, []).append(
                (str(path.relative_to(ROOT)), fields)
            )
    return found


def _collect_frontend_interfaces() -> dict[str, list[tuple[str, set[str]]]]:
    """前端 interface → 字段集合（同名 interface 出现在多个文件时保留多条）。"""
    found: dict[str, list[tuple[str, set[str]]]] = {}
    for directory in (FRONTEND_API, FRONTEND_TYPES):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.ts")):
            if path.name.endswith(".test.ts"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r"^export interface (\w+)\s*\{", text, re.M):
                name = match.group(1)
                start = match.end()
                depth = 1
                index = start
                while index < len(text) and depth:
                    if text[index] == "{":
                        depth += 1
                    elif text[index] == "}":
                        depth -= 1
                    index += 1
                body = text[start:index]
                fields = set(_FE_FIELD_RE.findall(body))
                found.setdefault(name, []).append(
                    (str(path.relative_to(ROOT)), fields)
                )
    return found


# 前端导出函数：export async function foo(...): Promise<T>
_FE_FN_RE = re.compile(
    r"export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)\s*:\s*Promise<([^>]+)>", re.S
)
# 调用位置：get('/x') / post(`${BASE}/x`)
_FE_CALL_RE = re.compile(
    r"\b(get|post|put|del|patch)\s*(?:<[^>]*>)?\s*\(\s*(`[^`]*`|'[^']*')"
)
_FE_METHOD = {"get": "GET", "post": "POST", "put": "PUT", "del": "DELETE", "patch": "PATCH"}


def _collect_backend_response_models() -> dict[tuple[str, str], object]:
    """(HTTP 方法, 归一化路径) → response_model（Pydantic 类）。"""
    from fastapi.routing import APIRoute  # noqa: PLC0415
    from pydantic import BaseModel  # noqa: PLC0415

    sys.path.insert(0, str(BACKEND))
    from app.main import app  # noqa: PLC0415

    models: dict[tuple[str, str], object] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        response_model = route.response_model
        if response_model is None:
            continue
        if not (isinstance(response_model, type) and issubclass(response_model, BaseModel)):
            continue
        normalized = normalize_path(route.path)
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            models[(method, normalized)] = response_model
    return models


def check_field_alignment() -> list[dict]:
    """C 轴：前端 interface ↔ 后端 Pydantic schema 的字段差异。

    配对方式：**按 URL 解析到真实端点**，且前端函数的返回类型名与后端端点的
    ``response_model`` 类名**完全相同**才配对。

    为什么不按"类名相同"配对：仓库里存在大量**同名不同契约**的类 ——
    例如前端 ``types/organization.ts`` 的 ``DataPackageManifest``（介质包清单）
    与后端 ``schemas/data_package.py`` 的同名类完全是两回事；``AggregateQuery`` /
    ``MonitorSnapshot`` / ``Fund`` / ``Organization`` 同理。按类名配对会产生大量
    假阳性。按 URL 配对 + 类名相同，得到的每一对都是**真实的同一份契约**。
    """
    frontend_interfaces = _collect_frontend_interfaces()
    response_models = _collect_backend_response_models()

    drift: list[dict] = []
    for path in sorted(FRONTEND_API.glob("*.ts")):
        if path.name.endswith(".test.ts"):
            continue
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        consts = dict(_CONST_RE.findall(text))
        for match in _FE_FN_RE.finditer(text):
            func_name, return_type = match.group(1), match.group(3).strip()
            # 在函数体开头找调用
            body_slice = text[match.end(): match.end() + 2000]
            call = _FE_CALL_RE.search(body_slice)
            if not call:
                continue
            method = _FE_METHOD[call.group(1)]
            url = call.group(2)[1:-1]
            for key, value in consts.items():
                url = url.replace("${" + key + "}", value)
            route = response_models.get((method, normalize_path(url)))
            if route is None:
                continue
            model_name = route.__name__
            # 前端返回类型必须与后端 response_model 同名，且全局唯一
            if return_type != model_name:
                continue
            frontend_defs = frontend_interfaces.get(return_type)
            if not frontend_defs or len(frontend_defs) != 1:
                continue

            frontend_file, frontend_fields = frontend_defs[0]
            backend_fields = set(route.model_fields.keys())

            backend_snake = {to_snake_case(f) for f in backend_fields} - {"model_config"}
            frontend_snake = {to_snake_case(f) for f in frontend_fields}

            only_backend = sorted(backend_snake - frontend_snake)
            only_frontend = sorted(frontend_snake - backend_snake)
            if only_backend or only_frontend:
                drift.append(
                    {
                        "name": return_type,
                        "backend": f"{model_name} @ {method} {normalize_path(url)}",
                        "frontend": f"{frontend_file}:{return_type} ({path.name}:{func_name})",
                        "only_backend": only_backend,
                        "only_frontend": only_frontend,
                    }
                )

    # ── 补充配对：按"被端点用作 response_model 的模型名"匹配 ──────────────
    # 有些前端契约只声明在 types/*.ts（不出现在 api 函数的返回类型上），
    # 例如 ``SubordinateReportDashboard``。这类契约只靠 URL 配对会被漏掉。
    # 规则：后端某个模型**确被某个端点用作 response_model**（说明它是真实响应契约），
    #     且前端有同名 interface 且全局唯一 → 配对。
    # 同名但字段集合不一致的后端类视为歧义，跳过（防止同名不同义假阳性）。
    served: dict[str, frozenset[str]] = {}
    ambiguous: set[str] = set()
    for model in response_models.values():
        name = model.__name__
        fields = frozenset(model.model_fields.keys())
        existing = served.get(name)
        if existing is None:
            served[name] = fields
        elif existing != fields:
            ambiguous.add(name)

    for name in sorted(set(served) - ambiguous):
        frontend_defs = frontend_interfaces.get(name)
        if not frontend_defs or len(frontend_defs) != 1:
            continue
        frontend_file, frontend_fields = frontend_defs[0]
        backend_snake = {to_snake_case(f) for f in served[name]} - {"model_config"}
        frontend_snake = {to_snake_case(f) for f in frontend_fields}
        only_backend = sorted(backend_snake - frontend_snake)
        only_frontend = sorted(frontend_snake - backend_snake)
        if only_backend or only_frontend:
            drift.append(
                {
                    "name": name,
                    "backend": f"{name} (response_model)",
                    "frontend": f"{frontend_file}:{name}",
                    "only_backend": only_backend,
                    "only_frontend": only_frontend,
                }
            )

    return drift


# ── 入口 ────────────────────────────────────────────────────────────────────

# ── D 轴：请求体必填性（前端 XxxCreate/XxxUpdate ↔ 后端同名 Pydantic）──────
#
# 2026-10-26 事故：后端 ``OrganizationCreate.code`` 必填（6 位行政区划代码），
# 前端 ``types/organization.ts`` 却写成 ``code?: string``（可选），于是前端
# 「新增组织」对话框漏掉了这个输入框也没人发现 —— 用户点提交只能收到
# 422「组织编码（行政区划代码）不能为空」。C 轴只比 ``response_model``，
# **请求体从来没被比对过**，这类「提交少字段 / 必填性不符」长期无人拦截。
#
# D 轴规则（保守，宁漏不误报）：
#   1. 只看名字以 Create / Update 结尾的契约（请求体）；
#   2. 前后端**同名**、且各自在全局**唯一**（同名多义则跳过）；
#   3. 比较"必填字段集合"，两个方向都报（后端必填而前端可选 = 少填；
#      前端必填而后端可选 = 过度约束）。
#
# 后端必填判定：无默认值，或 ``= Field(...)``；注解含 Optional/None 一律视为非必填。
# 前端必填判定：TypeScript 字段名后**没有** ``?``。

_REQ_SUFFIXES = ("Create", "Update")
_FE_FIELD_OPT_RE = re.compile(r"^\s{2}(\w+)(\?)?\s*:", re.M)


def _annotation_is_optional(ann: ast.AST, source: str) -> bool:
    """Optional[X] / X | None 视为非必填（取不到源码时按非可选处理，保守）。"""
    try:
        text = ast.get_source_segment(source, ann) or ""
    except Exception:  # noqa: BLE001
        return False
    return "Optional" in text or "None" in text


def _is_field_ellipsis(value: ast.AST | None) -> bool:
    """``= Field(...)``（Pydantic v2 必填写法）。"""
    if not isinstance(value, ast.Call):
        return False
    func = value.func
    name = getattr(func, "id", None) or getattr(func, "attr", None)
    if name != "Field" or not value.args:
        return False
    first = value.args[0]
    return isinstance(first, ast.Constant) and first.value is Ellipsis


def _collect_backend_required_models() -> dict[str, list[tuple[str, set[str], set[str]]]]:
    """类名 → [(文件, 全部字段, 必填字段)]（仅 BaseModel 子类）。"""
    found: dict[str, list[tuple[str, set[str], set[str]]]] = {}
    for path in sorted((BACKEND / "app").rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {getattr(b, "id", None) or getattr(b, "attr", None) for b in node.bases}
            if "BaseModel" not in bases:
                continue
            fields: set[str] = set()
            required: set[str] = set()
            for stmt in node.body:
                if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
                    continue
                name = stmt.target.id
                fields.add(name)
                if _annotation_is_optional(stmt.annotation, source):
                    continue
                if stmt.value is None or _is_field_ellipsis(stmt.value):
                    required.add(name)
            found.setdefault(node.name, []).append(
                (str(path.relative_to(ROOT)), fields, required)
            )
    return found


def _collect_frontend_required_interfaces() -> dict[str, list[tuple[str, set[str], set[str]]]]:
    """interface 名 → [(文件, 全部字段, 必填字段(无 ``?``))]。"""
    found: dict[str, list[tuple[str, set[str], set[str]]]] = {}
    for directory in (FRONTEND_API, FRONTEND_TYPES):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.ts")):
            if path.name.endswith(".test.ts"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r"^export interface (\w+)\s*\{", text, re.M):
                name = match.group(1)
                start = match.end()
                depth = 1
                index = start
                while index < len(text) and depth:
                    if text[index] == "{":
                        depth += 1
                    elif text[index] == "}":
                        depth -= 1
                    index += 1
                body = text[start:index]
                pairs = _FE_FIELD_OPT_RE.findall(body)
                fields = {f for f, _opt in pairs}
                required = {f for f, opt in pairs if not opt}
                found.setdefault(name, []).append(
                    (str(path.relative_to(ROOT)), fields, required)
                )
    return found


def check_request_shape_alignment() -> list[dict]:
    """D 轴：前端 Create/Update 契约 ↔ 后端同名模型的**必填字段**差异。"""
    backend = _collect_backend_required_models()
    frontend = _collect_frontend_required_interfaces()

    drift: list[dict] = []
    for name, be_defs in sorted(backend.items()):
        if not name.endswith(_REQ_SUFFIXES):
            continue
        fe_defs = frontend.get(name)
        # 同名多义（前后端任一侧不唯一）→ 无法安全配对，跳过
        if not fe_defs or len(fe_defs) != 1 or len(be_defs) != 1:
            continue
        be_file, be_fields, be_required = be_defs[0]
        fe_file, fe_fields, fe_required = fe_defs[0]

        be_req = {to_snake_case(f) for f in be_required} - {"model_config"}
        fe_req = {to_snake_case(f) for f in fe_required}
        fe_all = {to_snake_case(f) for f in fe_fields}

        missing = sorted(be_req - fe_req)          # 后端必填但前端未必填/缺失
        over = sorted(fe_req - be_req)             # 前端必填但后端可选
        absent = sorted(be_req - fe_all)           # 后端必填但前端根本没有该字段
        if not (missing or over):
            continue
        drift.append(
            {
                "name": name,
                "backend": be_file,
                "frontend": fe_file,
                "not_required_in_frontend": [f for f in missing if f not in absent],
                "missing_in_frontend": absent,
                "required_only_in_frontend": over,
            }
        )
    return drift


def run() -> dict:
    """跑四条轴，返回结构化报告。"""
    return {
        "path_drift": check_path_alignment(),
        "model_db_drift": check_model_db_alignment(),
        "field_drift": check_field_alignment(),
        "request_shape_drift": check_request_shape_alignment(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="前后端 + 数据库三层对齐门禁")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    # Windows 控制台默认 GBK，输出里的箭头等符号会抛 UnicodeEncodeError ——
    # 门禁必须在任何环境下都能把结果打印出来（否则崩溃会掩盖真实漂移）。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    # 导入 app.main 会触发应用自身的启动日志（"路由加载完成"等），它们写 stdout。
    # 若不隔离，--json 的输出就没法被 json.loads 解析。因此：
    # 捕获 stdout → 应用日志改道 stderr → 真正的 stdout 只留门禁自己的结果。
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            report = run()
    except Exception as exc:  # noqa: BLE001 —— 门禁自身出错必须显式失败
        sys.stderr.write(captured.getvalue())
        print(f"[FAIL] 对齐门禁执行失败: {exc}", file=sys.stderr)
        return 2

    app_logs = captured.getvalue()
    if app_logs.strip():
        sys.stderr.write(app_logs)

    total = (
        len(report["path_drift"])
        + len(report["model_db_drift"])
        + len(report["field_drift"])
        + len(report["request_shape_drift"])
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if report["path_drift"]:
            print(f"[FAIL] A 轴 前端调用路径未命中后端路由（{len(report['path_drift'])}）:")
            for item in report["path_drift"]:
                print(f"    {item['file']}:{item['line']} {item['raw']} -> {item['normalized']}")
        if report["model_db_drift"]:
            print(f"[FAIL] B 轴 ORM 模型与数据库 schema 不一致（{len(report['model_db_drift'])}）:")
            for item in report["model_db_drift"]:
                print(f"    {item}")
        if report["field_drift"]:
            print(f"[FAIL] C 轴 前后端字段不一致（{len(report['field_drift'])}）:")
            for item in report["field_drift"]:
                print(f"    {item['name']} ({item['backend']} <-> {item['frontend']})")
                if item["only_backend"]:
                    print(f"        仅后端: {item['only_backend']}")
                if item["only_frontend"]:
                    print(f"        仅前端: {item['only_frontend']}")
        if report["request_shape_drift"]:
            print(f"[FAIL] D 轴 请求体必填性不一致（{len(report['request_shape_drift'])}）:")
            for item in report["request_shape_drift"]:
                print(f"    {item['name']} ({item['backend']} <-> {item['frontend']})")
                if item["missing_in_frontend"]:
                    print(f"        前端缺字段: {item['missing_in_frontend']}")
                if item["not_required_in_frontend"]:
                    print(f"        后端必填但前端可选: {item['not_required_in_frontend']}")
                if item["required_only_in_frontend"]:
                    print(f"        前端必填但后端可选: {item['required_only_in_frontend']}")
        if total == 0:
            print("[OK] 四层对齐无漂移：前端路径 / 模型↔库 / 前后端字段 / 请求体必填性")

    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
