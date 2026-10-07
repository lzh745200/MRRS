"""app/api/v1 部分分支（partial branches）清零专项 —— B 组。

目标文件与弧（coverage.py --show-missing 实测）：
- school.py:            74->exit, 610->616, 638->644, 801->804, 878->882, 1135->1137
- projects.py:          538->535, 1071->1077, 1083->1094, 1369->1368, 1797->1800, 2043->2049
- funds.py:             147->140, 154->140, 361->378, 632->642
- supported_village.py: 1200->1229, 1221->1216, 1493->1500, 1496->1498
- organization.py:      232->exit, 680->683, 848->855
- recycle_bin.py:       167->169, 243->247, 271->262
- map.py:               99->101, 190->204, 457->462
- rural_works.py:       169->178
- menus.py:             609->611
- messages.py:          385->388
"""
import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1 import map as map_mod
from app.api.v1 import messages as messages_mod
from app.api.v1 import organization as org_mod
from app.api.v1 import projects as projects_mod
from app.api.v1 import recycle_bin as recycle_mod
from app.api.v1 import rural_works as rural_works_mod
from app.api.v1 import school as school_mod
from app.api.v1 import supported_village as sv_mod
from app.core.config import settings
from app.models.project import Project
from app.models.school import ScholarshipStatus, School, SchoolProject


# ---------------------------------------------------------------------------
# 公共小夹具
# ---------------------------------------------------------------------------
def _admin_user(**extra):
    u = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)
    for k, v in extra.items():
        setattr(u, k, v)
    return u


def _query(first_result):
    """构造 db.query(<Model>) 链：filter(...)[.options(...)].first() → first_result"""
    q = MagicMock()
    q.filter.return_value = q
    q.options.return_value = q
    q.first.return_value = first_result
    return q


# ===========================================================================
# school.py
# ===========================================================================
class TestSchoolBranchGaps:
    def test_apply_scholarship_approval_result_non_pending_kept(self):
        """74->exit：学生已非 pending → 不改写状态。"""
        db = MagicMock()
        student = SimpleNamespace(status=ScholarshipStatus.APPROVED)
        db.query.return_value.filter.return_value.first.return_value = student
        task = SimpleNamespace(status="approved", entity_id=7)

        school_mod._apply_scholarship_approval_result(db, task)

        assert student.status == ScholarshipStatus.APPROVED

    async def test_download_attachment_school_missing_skips_permission(self, tmp_path, monkeypatch):
        """610->616：附件所属学校已不存在 → 跳过数据权限校验仍可下载。"""
        f = tmp_path / "att.txt"
        f.write_text("hello", encoding="utf-8")
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

        att = SimpleNamespace(id=1, school_id=99, file_path=str(f),
                              file_name="att.txt", file_type="text/plain")
        db = MagicMock()
        db.query.side_effect = [_query(att), _query(None)]  # 附件存在，学校已删

        resp = await school_mod.download_attachment(1, current_user=_admin_user(), db=db)

        assert os.path.samefile(str(resp.path), str(f))

    async def test_delete_attachment_school_missing_skips_permission(self, tmp_path, monkeypatch):
        """638->644：学校已不存在 → 跳过权限校验，正常删除磁盘文件与记录。"""
        f = tmp_path / "att2.txt"
        f.write_text("data", encoding="utf-8")
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

        att = SimpleNamespace(id=2, school_id=99, file_path=str(f),
                              file_name="att2.txt", file_type="text/plain")
        db = MagicMock()
        db.query.side_effect = [_query(att), _query(None)]

        await school_mod.delete_attachment(2, current_user=_admin_user(), db=db)

        assert not f.exists()
        db.delete.assert_called_once_with(att)

    async def test_create_school_without_type(self):
        """801->804：未传 type → 跳过 type 枚举转换，type 保持 None。"""
        data = SimpleNamespace(code=None, model_dump=lambda: {"name": "乡村小学"})
        db = MagicMock()
        user = _admin_user(organization_id=None)

        with patch.object(school_mod, "write_work_log"), \
             patch.object(school_mod, "submit_entity_change_approval", return_value=None):
            resp = await school_mod.create_school(data, current_user=user, db=db)

        created = db.add.call_args.args[0]
        assert created.name == "乡村小学"
        assert created.type is None  # 未走 SchoolType(...) 转换
        assert resp["code"] == 200

    async def test_update_school_without_code(self):
        """878->882：更新不带 code → 跳过编码唯一性检查，code 保持不变。"""
        school = School(id=3, name="旧校名", code="S-003", support_status=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = school
        data = school_mod.SchoolUpdate(name="新校名")

        with patch.object(school_mod, "write_work_log"), \
             patch.object(school_mod, "submit_entity_change_approval", return_value=None):
            resp = await school_mod.update_school(3, data, current_user=_admin_user(), db=db)

        assert school.name == "新校名"
        assert school.code == "S-003"  # 未触发编码唯一性查询/冲突
        assert resp["code"] == 200

    async def test_create_school_project_without_phase(self):
        """1135->1137：未传 phase → 不做 ProjectPhase 转换，phase 保持 None。"""
        school = SimpleNamespace(id=5, name="某校", organization_id=None, created_by=1)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = school
        data = SimpleNamespace(model_dump=lambda: {"name": "宿舍改造", "budget": 100})
        user = _admin_user()

        with patch.object(school_mod, "submit_entity_change_approval", return_value=None):
            resp = await school_mod.create_project(5, data, current_user=user, db=db)

        created = db.add.call_args.args[0]
        assert isinstance(created, SchoolProject)
        assert created.phase is None
        assert resp["code"] == 200


# ===========================================================================
# projects.py
# ===========================================================================
class TestProjectsBranchGaps:
    async def test_get_project_stats_row_with_none_status(self):
        """538->535：聚合行 status 为 None → 不写入分状态计数。"""
        rows_q, invested_q = MagicMock(), MagicMock()
        rows_q.filter.return_value = rows_q
        rows_q.group_by.return_value.all.return_value = [(None, 2, 100.0)]
        invested_q.filter.return_value = invested_q
        invested_q.scalar.return_value = 10
        db = MagicMock()
        db.query.side_effect = [rows_q, invested_q]

        resp = await projects_mod.get_project_stats(current_user=_admin_user(), db=db)

        stats = resp["data"]
        assert stats["total"] == 2
        assert stats["draft"] == 0  # None 状态未写入任何分状态字段

    async def test_update_project_no_changes_skips_audit_and_approval(self):
        """1071->1077 / 1083->1094：无实际变更 → 跳过审计与审批任务创建。"""
        project = Project(id=1, name="项目P", status="draft", created_by=1)
        db = MagicMock()
        db.query.return_value.filter.return_value.options.return_value.first.return_value = project
        data = projects_mod.ProjectUpdate.model_construct()  # exclude_unset 后为空 dict
        request = MagicMock()

        resp = await projects_mod.update_project(
            1, data, request, current_user=_admin_user(), db=db
        )

        assert resp["code"] == 200
        assert resp["data"]["approval_task_id"] is None
        db.refresh.assert_called_once_with(project)

    async def test_update_project_task_skips_unknown_field(self):
        """1369->1368：payload 含模型不存在的字段 → 跳过 setattr 继续下一字段。"""
        project = SimpleNamespace(id=1, created_by=1, organization_id=None)
        task = SimpleNamespace(id=1, project_id=1, name="旧名", description=None,
                               status="pending", priority=0, assignee=None,
                               due_date=None, created_at=None, updated_at=None)
        db = MagicMock()
        db.query.side_effect = [_query(project), _query(task)]
        data = SimpleNamespace(model_dump=lambda exclude_unset=True: {"name": "新名", "ghost": 1})

        resp = await projects_mod.update_project_task(
            1, 1, data, current_user=_admin_user(), db=db
        )

        assert task.name == "新名"
        assert not hasattr(task, "ghost")  # 未知字段被跳过
        assert resp["data"]["name"] == "新名"

    def test_build_import_project_code_not_duplicated(self):
        """1797->1800：生成的编码无冲突 → 不重新生成。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        data = {"name": "导入项目"}

        project = projects_mod._build_import_project(db, data, _admin_user(id=9))

        assert project.name == "导入项目"
        assert project.code.startswith("PRJ-")

    async def test_delete_project_file_without_filepath(self):
        """2043->2049：filepath 为空 → 不触碰磁盘，直接删记录。"""
        project = SimpleNamespace(id=1, created_by=1, organization_id=None)
        pf = SimpleNamespace(id=11, project_id=1, filepath=None)
        db = MagicMock()
        db.query.side_effect = [_query(project), _query(pf)]

        resp = await projects_mod.delete_project_file(
            1, 11, current_user=_admin_user(), db=db
        )

        assert resp["code"] == 200
        db.delete.assert_called_once_with(pf)


# ===========================================================================
# funds.py
# ===========================================================================
class TestFundsBranchGaps:
    def test_resolve_fund_approval_approve_unexpected_status(self):
        """147->140：approve 后任务状态既非 pending 也非 approved → 不计数。"""
        from app.api.v1.funds import _resolve_fund_approval_tasks

        db = MagicMock()
        fund = SimpleNamespace(id=1)
        db.query.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(id=11, status="pending")
        ]
        with patch("app.api.v1.funds.ApprovalWorkflowService") as svc_cls:
            svc_cls.return_value.approve_task.return_value = SimpleNamespace(
                id=11, status="planned"  # 中间态：循环退出但不计完结
            )
            count = _resolve_fund_approval_tasks(
                db, fund, "approve", operator=_admin_user()
            )
        assert count == 0

    def test_resolve_fund_approval_reject_unexpected_status(self):
        """154->140：reject 后任务状态非 rejected → 不计数。"""
        from app.api.v1.funds import _resolve_fund_approval_tasks

        db = MagicMock()
        fund = SimpleNamespace(id=1)
        db.query.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(id=12, status="pending")
        ]
        with patch("app.api.v1.funds.ApprovalWorkflowService") as svc_cls:
            svc_cls.return_value.reject_task.return_value = SimpleNamespace(
                id=12, status="pending"  # 驳回被拒回：状态未完结
            )
            count = _resolve_fund_approval_tasks(
                db, fund, "reject", operator=_admin_user(), reason="材料不全"
            )
        assert count == 0

    def test_parse_date_value_non_string_returns_unchanged(self):
        """361->378：日期字段传入非字符串（如 int）→ 原样返回。"""
        from app.api.v1.funds import _parse_date_value

        sentinel = 20260721
        assert _parse_date_value("start_date", sentinel) is sentinel

    def test_update_fund_unchanged_value_no_field_change(self):
        """632->642：新值与旧值相同 → 不写 FundFieldChange。"""
        from app.api.v1.funds import update_fund

        fund = SimpleNamespace(id=1, status="pending", name="同名", code="F-001")
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = fund
        data = SimpleNamespace(model_dump=lambda exclude_unset=True: {"name": "同名"})
        user = _admin_user(full_name="管理员")

        resp = update_fund(1, data, current_user=user, db=db)

        assert resp["code"] == 200
        assert resp["message"] == "更新成功"
        db.add.assert_not_called()  # 值未变化 → 无字段级变更留痕


# ===========================================================================
# supported_village.py
# ===========================================================================
class TestSupportedVillageBranchGaps:
    def _village(self):
        return SimpleNamespace(id=1, organization_id=None, created_by=1, name="示范村")

    async def test_validate_yearly_data_year_zero_skips_yoy(self):
        """1200->1229：year<=0 → 跳过同比预警计算。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.options.return_value.first.return_value = self._village()

        resp = await sv_mod.validate_yearly_data(1, 0, current_user=_admin_user(), db=db)

        assert resp["data"]["warnings"] == []
        assert resp["data"]["valid"] is True

    async def test_validate_yearly_data_small_change_no_warning(self):
        """1221->1216：同比变动 ≤ ±50% → 不产生预警，继续下一列。"""
        cur = SimpleNamespace(id=1, year=2024, total_households=110)
        prev = SimpleNamespace(id=1, year=2023, total_households=100)
        none_q = _query(None)
        village_q = MagicMock()
        village_q.filter.return_value.options.return_value.first.return_value = self._village()
        # 查询顺序：村庄 1 次 + 11 个板块当年 + 11 个板块前一年（population 为首个板块）
        db = MagicMock()
        db.query.side_effect = (
            [village_q]                       # 村庄存在性
            + [_query(cur)]                   # population 当年
            + [_query(None)] * 10             # 其余板块当年
            + [_query(prev)]                  # population 前一年
            + [_query(None)] * 10             # 其余板块前一年
        )

        resp = await sv_mod.validate_yearly_data(1, 2024, current_user=_admin_user(), db=db)

        assert resp["data"]["warnings"] == []  # 10% 变动未触发 ±50% 阈值

    def test_section_label_map_comment_edges(self):
        """1493->1500 / 1496->1498：无注释列与纯括号注释列的映射。"""
        fake_model = SimpleNamespace(
            __table__=SimpleNamespace(columns=[
                SimpleNamespace(name="plain_col", comment=None),        # 无注释
                SimpleNamespace(name="hint_col", comment="（进度）"),    # 拆分后 label 为空
                SimpleNamespace(name="total_households", comment="总户数(人)"),
            ])
        )

        mapping = sv_mod._section_label_map(fake_model)

        assert mapping["plain_col"] == "plain_col"           # 无注释列仍按英文属性名兜底
        assert mapping["（进度）"] == "hint_col"              # 空 label → 整条注释作为 key
        assert mapping["总户数"] == "total_households"        # 正常取括号前标签
        assert "" not in mapping                             # 空 label 不产生空 key


# ===========================================================================
# organization.py
# ===========================================================================
class TestOrganizationBranchGaps:
    def test_set_no_cache_headers_with_none_response(self):
        """232->exit：response 为 None → 直接返回，不设置头。"""
        assert org_mod._set_no_cache_headers(None) is None

    async def test_update_organization_unique_code(self):
        """680->683：新编码无冲突 → 不抛 400，正常更新。"""
        org = SimpleNamespace(id=1, name="组织A", code=None)
        db = MagicMock()
        db.query.side_effect = [_query(org), _query(None)]  # 组织存在；新编码无重复
        data = org_mod.OrganizationUpdate(code="UNIQ-X")

        with patch.object(org_mod, "safe_commit"), \
             patch.object(org_mod, "write_work_log"), \
             patch.object(org_mod, "cache_manager") as cm:
            cm.delete = AsyncMock()
            resp = await org_mod.update_organization(1, data, current_user=_admin_user(), db=db)

        assert org.code == "UNIQ-X"
        assert resp["code"] == 200

    async def test_move_organization_parent_chain_terminates(self):
        """848->855：新父级父链到根自然结束 → 正常移动，不抛循环错误。"""
        org = SimpleNamespace(id=5, parent_id=None, name="子组织")
        root = SimpleNamespace(id=2, parent_id=None, name="根组织")
        db = MagicMock()
        db.query.side_effect = [_query(org), _query(root), _query(root)]
        body = org_mod.MoveOrganizationRequest(new_parent_id=2)

        with patch.object(org_mod, "safe_commit"), \
             patch.object(org_mod, "cache_manager") as cm:
            cm.delete = AsyncMock()
            resp = await org_mod.move_organization(5, body, current_user=_admin_user(), db=db)

        assert org.parent_id == 2
        assert resp["data"] == {"message": "移动成功"}


# ===========================================================================
# recycle_bin.py
# ===========================================================================
class TestRecycleBinBranchGaps:
    async def test_restore_record_without_deleted_at(self):
        """167->169：模型无 deleted_at 属性 → 跳过清空，直接复位。"""
        rec = SimpleNamespace(is_active=False, status=None, name="记录R")
        db = MagicMock()
        db.get.return_value = rec

        with patch("app.utils.audit_logger.AuditLogger"):
            resp = await recycle_mod._restore_record(
                db, object(), "项目", "project", 1, _admin_user(), on_changed=None
            )

        assert rec.is_active is True
        assert not hasattr(rec, "deleted_at")  # 未被强加 deleted_at 属性
        assert resp["data"] == {"id": 1}

    async def test_batch_restore_zero_count(self):
        """243->247：update 影响 0 行 → 不做标记清理二次查询。"""
        q = MagicMock()
        q.filter.return_value.update.return_value = 0
        db = MagicMock()
        db.query.return_value = q

        resp = await recycle_mod._batch_restore_records(
            db, Project, "项目", [1, 2], _admin_user(), on_changed=None
        )

        assert resp["data"] == {"restored": 0}
        assert db.query.call_count == 1  # count=0 → 未进入逐条 reset 循环

    async def test_batch_purge_purge_failure_skips_count(self):
        """271->262：级联清除失败 → 不累计，继续处理下一条。"""
        rec = SimpleNamespace(id=1, is_active=False)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = rec

        with patch("app.services.cascade_purge_service.CascadePurgeService") as svc_cls, \
             patch("app.utils.audit_logger.AuditLogger"), \
             patch("app.services.immediate_backup.trigger_immediate_backup"):
            svc_cls.return_value.purge.return_value = {"success": False, "message": "外键约束"}
            resp = await recycle_mod._batch_purge_records(
                db, Project, "项目", "project", [1, 2], _admin_user(), on_changed=None
            )

        assert resp["data"] == {"purged": 0, "ids": []}
        assert svc_cls.return_value.purge.call_count == 2  # 两条都被尝试


# ===========================================================================
# map.py
# ===========================================================================
class _LockThatInitializes:
    """模拟并发场景：进入锁的瞬间另一线程已完成初始化（内层双检为假）。"""

    def __init__(self, mod):
        self._mod = mod

    def __enter__(self):
        setattr(self._mod, "_map_cache", None)
        return self

    def __exit__(self, *exc):
        return False


class TestMapBranchGaps:
    def test_get_map_cache_inner_double_check_false(self, monkeypatch):
        """99->101：外层判定 UNSET、进锁后已被初始化 → 内层跳过构造。"""
        monkeypatch.setattr(map_mod, "_map_cache", map_mod._UNSET)
        monkeypatch.setattr(map_mod, "_map_cache_lock", _LockThatInitializes(map_mod))

        result = map_mod._get_map_cache()

        assert result is None  # 已被置为 None（diskcache 不可用语义），且未再构造

    def test_get_coords_without_county_uses_center(self):
        """190->204：无县市名 → 回退州中心坐标加抖动。"""
        lng, lat, estimated = map_mod._get_coords(None, None, None, record_id=1, name="x")

        assert estimated is True
        assert abs(lng - map_mod.QIANNAN_CENTER[0]) <= 0.05
        assert abs(lat - map_mod.QIANNAN_CENTER[1]) <= 0.05

    async def test_get_distances_cache_miss_computes(self):
        """457->462：缓存未命中（get 返回 None）→ 继续全量计算。"""
        cache = MagicMock()
        cache.get.return_value = None
        vq, sq = MagicMock(), MagicMock()
        vq.all.return_value = []
        sq.all.return_value = []
        db = MagicMock()
        db.query.side_effect = [vq, sq]
        scope = MagicMock()
        scope.filter_by_org_ids.side_effect = lambda q, *a, **k: q

        with patch.object(map_mod, "_get_map_cache", return_value=cache):
            resp = await map_mod.get_distances(
                current_user=_admin_user(id=7), data_scope=scope, db=db
            )

        assert resp["data"]["villages"] == []
        assert resp["data"]["schools"] == []
        assert resp["data"]["base"]["name"] == "区域中心"


# ===========================================================================
# rural_works.py
# ===========================================================================
class TestRuralWorksBranchGaps:
    async def test_create_rural_work_without_id_skips_approval(self):
        """169->178：service 返回结果无 id → 不创建审批任务。"""
        db = MagicMock()
        user = SimpleNamespace(id=1, organization_id=None)

        with patch.object(rural_works_mod, "RuralWorkService") as svc_cls, \
             patch.object(rural_works_mod, "submit_entity_change_approval") as submit:
            svc_cls.return_value.create_rural_work.return_value = {"name": "道路硬化"}
            resp = await rural_works_mod.create_rural_work(
                MagicMock(name="data"), db=db, current_user=user
            )

        assert resp.code == 200
        assert resp.data["approval_task_id"] is None
        submit.assert_not_called()  # 无 id → 不创建审批任务


# ===========================================================================
# menus.py
# ===========================================================================
class TestMenusBranchGaps:
    def test_filter_menu_tree_children_all_filtered_out(self):
        """609->611：子节点全部无权限 → 父节点不带 children 键。"""
        from app.api.v1.menus import _filter_menu_tree

        tree = [
            {"key": "parent", "title": "父级",
             "children": [{"key": "child1"}, {"key": "child2"}]},
        ]

        result = _filter_menu_tree(tree, allowed_keys={"parent"})

        assert result == [{"key": "parent", "title": "父级"}]  # 空 children 被剔除


# ===========================================================================
# messages.py
# ===========================================================================
class TestMessagesBranchGaps:
    async def test_recent_activities_empty_resource_cn(self):
        """385->388：resource_type 为空 → 标题不带资源前缀。"""
        log = SimpleNamespace(id="1", action="create", resource_type=None,
                              resource_id=None, username=None, created_at=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = [log]

        resp = await messages_mod.get_recent_activities(
            limit=10, current_user=_admin_user(), db=db
        )

        items = resp["data"]["items"]
        assert items[0]["title"] == "新增记录"  # 无资源名前缀
