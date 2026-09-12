# -*- coding: utf-8 -*-
"""B1 数据域过滤下沉的结构性回归（v1.12.3 Phase 2 · 批次 b1/b2 收口）。

评估报告 B1【P1】的症结是"过滤靠逐点手工调用"——扫描器只能发现"完全没过滤"，
发现不了"过滤条件写错"或"新端点又绕过统一入口"。本文件把纪律变成结构：

1. **入口唯一性（AST 扫描）**：`app/api/**` 下任何模块都不得再引用
   `filter_by_data_scope`（import 或调用）。注释/文档串提及不算（AST 天然忽略）。
   这样"新写的路由直接调核心原语"会在 CI 立刻失败，而不是等审计发现。
2. **语义不漂移（SQL 编译串比对）**：`scoped_filter(q, M, u)` 与
   `filter_by_data_scope(q, M, u)` 对三档角色（super_admin / admin / user）
   必须编译出**完全相同的 SQL**——下沉只换入口、不改过滤语义（军事审计 S2 红线）。
3. **单一真源未被复制**：`services/data_scope_query.py` 必须委托给
   `core/data_permission.filter_by_data_scope`，不得自行实现一套过滤。
"""

import ast
import os
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.data_permission import filter_by_data_scope
from app.models.project import Project
from app.models.supported_village import SupportedVillage
from app.services.data_scope_query import scoped_count, scoped_filter, scoped_query

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "app")
API_DIR = os.path.abspath(os.path.join(APP_DIR, "api"))

_PRIMITIVE = "filter_by_data_scope"


def _referencing_modules(root: str):
    """返回 (相对路径, 行号) 列表：AST 层面引用了核心过滤原语的文件。"""
    hits = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            # utf-8-sig：仓库里 app/api/v1/projects.py 等文件带 UTF-8 BOM，
            # 用 utf-8 读取会把 BOM 变成 \ufeff 交给 ast.parse → 误报 SyntaxError
            tree = ast.parse(open(path, encoding="utf-8-sig").read(), filename=path)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Name):
                    names.append(node.id)
                elif isinstance(node, ast.Attribute):
                    names.append(node.attr)
                elif isinstance(node, ast.ImportFrom):
                    names.extend(alias.name for alias in node.names)
                if _PRIMITIVE in names:
                    hits.append((os.path.relpath(path, os.path.dirname(API_DIR)), node.lineno))
    return hits


def _user(role="user", user_id=7, org_id=3, superuser=False):
    return SimpleNamespace(role=role, id=user_id, organization_id=org_id,
                           is_superuser=superuser, created_by=user_id)


def _session():
    engine = create_engine("sqlite://")
    return sessionmaker(bind=engine)()


class TestEntrypointUniqueness:
    def test_api_layer_never_uses_core_primitive_directly(self):
        """api/** 必须经服务层统一入口，不得直接引用核心原语（B1 结构性收口）。"""
        hits = _referencing_modules(API_DIR)
        assert hits == [], (
            "以下位置仍在 api 层直接引用 %s（应改用 app.services.data_scope_query）: %s"
            % (_PRIMITIVE, hits)
        )

    def test_services_layer_has_no_direct_api_usage(self):
        """服务层同样不应出现"绕过入口又直接调用原语"的新代码（delegation 除外）。"""
        hits = [
            (path, line)
            for path, line in _referencing_modules(os.path.join(APP_DIR, "services"))
            if not path.endswith(os.path.join("services", "data_scope_query.py"))
        ]
        assert hits == [], "服务层仍直接引用 %s: %s" % (_PRIMITIVE, hits)


class TestSemanticEquivalence:
    """三档角色的 SQL 编译串必须逐字一致（下沉不得改变过滤语义）。"""

    def _sql(self, builder, model, user):
        db = _session()
        try:
            query = db.query(model)
            return str(builder(query, model, user))
        finally:
            db.close()

    def test_super_admin_sql_identical(self):
        user = _user(role="super_admin", superuser=True)
        for model in (SupportedVillage, Project):
            assert self._sql(scoped_filter, model, user) == self._sql(
                filter_by_data_scope, model, user
            )

    def test_admin_sql_identical(self):
        """部门级 admin：必须限定本组织（S2 红线，不做放行豁免）。"""
        user = _user(role="admin", org_id=42)
        for model in (SupportedVillage, Project):
            sql_scoped = self._sql(scoped_filter, model, user)
            sql_core = self._sql(filter_by_data_scope, model, user)
            assert sql_scoped == sql_core
            assert "organization_id" in sql_scoped  # 组织过滤确实生效

    def test_regular_user_sql_identical(self):
        user = _user(role="user", user_id=99)
        for model in (SupportedVillage, Project):
            sql_scoped = self._sql(scoped_filter, model, user)
            sql_core = self._sql(filter_by_data_scope, model, user)
            assert sql_scoped == sql_core
            assert "created_by" in sql_scoped  # 仅本人

    def test_scoped_query_and_count_agree(self, tmp_path):
        user = _user(role="admin", org_id=42)
        # scoped_count 会真正执行 SQL：需要建表（内存库无表会 OperationalError）
        import app.models  # noqa: F401 — 触发全部模型注册到 Base.metadata
        from app.models.base import Base

        engine = create_engine(f"sqlite:///{tmp_path / 'drill.db'}")
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        try:
            sql_query = str(scoped_query(db, SupportedVillage, user))
            sql_filter = str(scoped_filter(db.query(SupportedVillage), SupportedVillage, user))
            assert sql_query == sql_filter
            # scoped_count 基于 scoped_query，口径必须一致（统计与列表不得分叉）
            assert scoped_count(db, SupportedVillage, user) == 0
        finally:
            db.close()


class TestSingleSourceDelegation:
    def test_scoped_filter_delegates_to_core(self):
        """单一真源：服务层入口必须调用 core 原语，不得自行实现过滤。"""
        db = _session()
        try:
            sentinel = object()
            with patch(
                "app.core.data_permission.filter_by_data_scope", return_value=sentinel
            ) as mock_core:
                result = scoped_filter(db.query(SupportedVillage), SupportedVillage, _user())
            assert result is sentinel
            assert mock_core.call_count == 1
        finally:
            db.close()

    def test_scoped_query_delegates_to_core(self):
        db = _session()
        try:
            sentinel = object()
            with patch(
                "app.core.data_permission.filter_by_data_scope", return_value=sentinel
            ) as mock_core:
                result = scoped_query(db, Project, _user())
            assert result is sentinel
            assert mock_core.call_count == 1
        finally:
            db.close()
