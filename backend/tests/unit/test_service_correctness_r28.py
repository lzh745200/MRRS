"""R28 服务层正确性回归 —— 真实 SQLite 落库验证（M25 / M26 / M29 / M30）。

对应 R27 排查报告 medium 项的修复。这些缺陷的共同点是「mock 下看起来正确、
真实数据库下才暴露」：外键重映射丢失、组织 path 未回填、覆盖导入把缺键写成
NULL、审批并发/重放双写。因此全部使用临时 SQLite 文件库落库验证，不依赖 mock。

锁定口径：
- M25 smart_conflict_resolver._update_foreign_keys 必须重映射 funds 的
  project_id / village_id / school_id 到本机行；
- M26 permission_package_service._import_organizations 新建组织必须回填
  parent_id / path / level（组织级数据权限依赖 path 前缀匹配）；
- M29 data_package_service._bulk_upsert_records overwrite 只写记录实际携带的
  键，缺键不得清空既有列；显式 None 仍照写；
- M30 approval_workflow_service.approve_task 原子抢占：check 与 act 之间被
  并发推进的行不能再次写入（无审批记录、级别不被本请求改动）。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 —— 确保全部模型注册进 Base.metadata
from app.models import Base
from app.models.approval import (
    ApprovalNode,
    ApprovalRecord,
    ApprovalStatus,
    ApprovalTask,
    ApprovalWorkflow,
)
from app.models.fund import Fund
from app.models.organization import Organization
from app.models.project import Project
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.models.todo import Todo


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'r28.db'}")
    Base.metadata.create_all(bind=engine)
    # expire_on_commit=False：M30 用例需要在 commit 后保留陈旧对象快照，
    # 模拟「check 之后、act 之前」被并发推进会话更新的竞态窗口。
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


# ══════════════════════════════════════════════════════════════
# M25：跨机导入经费的外键必须重映射到本机行
# ══════════════════════════════════════════════════════════════


class TestM25FundForeignKeyRemap:
    def test_fund_fks_remapped_to_local_rows(self, session_factory):
        from app.services.smart_conflict_resolver import SmartConflictResolver

        s = session_factory()
        village = SupportedVillage(village_name="本机帮扶村")
        project = Project(name="本机项目")
        school = School(name="本机学校")
        s.add_all([village, project, school])
        s.commit()

        resolver = SmartConflictResolver(s)

        # 源机记录：村/项目/学校的 id 都是源机编号（5/7/9），本机行 id 不同
        record = {
            "code": "F-2026-001",
            "name": "跨机导入经费",
            "project_id": 7,
            "village_id": 5,
            "school_id": 9,
        }
        resolver._update_foreign_keys(
            record,
            "funds",
            {
                "projects": {7: project.id},
                "villages": {5: village.id},
                "schools": {9: school.id},
            },
        )

        fund = Fund(
            code=record["code"],
            name=record["name"],
            project_id=record["project_id"],
            village_id=record["village_id"],
            school_id=record["school_id"],
            organization_id=1,
        )
        s.add(fund)
        s.commit()
        s.expire_all()

        loaded = s.query(Fund).filter(Fund.code == "F-2026-001").one()
        assert loaded.project_id == project.id
        assert loaded.village_id == village.id
        assert loaded.school_id == school.id
        # 源机编号不得残留（本机自增 id 与源机不同，这里 7/5/9 均非本机 id）
        assert loaded.village_id != 5
        assert loaded.school_id != 9

    def test_unmapped_and_null_fks_left_untouched(self, session_factory):
        from app.services.smart_conflict_resolver import SmartConflictResolver

        resolver = SmartConflictResolver(session_factory())
        record = {"code": "F-2", "project_id": 7, "village_id": None}
        resolver._update_foreign_keys(record, "funds", {"projects": {999: 1}})
        # 未在映射表中的引用保持原值；显式 None 不被误改
        assert record["project_id"] == 7
        assert record["village_id"] is None


# ══════════════════════════════════════════════════════════════
# M26：权限包导入的新建组织必须回填 parent_id / path / level
# ══════════════════════════════════════════════════════════════


class TestM26OrganizationPathBackfill:
    def _import(self, s, organizations_data):
        from app.services.permission_package_service import PermissionPackageService

        svc = PermissionPackageService(s)
        stats = {"organizations_created": 0, "organizations_updated": 0}
        errors = []
        svc._import_organizations(organizations_data, stats, errors)
        s.commit()
        return stats, errors

    def test_parent_chain_backfilled(self, session_factory):
        s = session_factory()
        data = [
            {"id": 1, "name": "省级单位", "code": "ORG-P"},
            {"id": 2, "name": "市级单位", "code": "ORG-C", "parent_id": 1},
            {"id": 3, "name": "县级单位", "code": "ORG-X", "parent_id": 2},
        ]
        stats, errors = self._import(s, data)

        orgs = {o.code: o for o in s.query(Organization).all()}
        root, child, leaf = orgs["ORG-P"], orgs["ORG-C"], orgs["ORG-X"]

        assert errors == []
        assert stats["organizations_created"] == 3
        assert root.parent_id is None
        assert root.path == f"/{root.id}/"
        assert child.parent_id == root.id
        assert child.path == f"/{root.id}/{child.id}/"
        assert leaf.parent_id == child.id
        assert leaf.path == f"/{root.id}/{child.id}/{leaf.id}/"
        assert str(root.level) == "1"
        assert str(child.level) == "2"
        assert str(leaf.level) == "3"

    def test_unresolvable_parent_falls_back_to_root(self, session_factory):
        s = session_factory()
        # parent_id=99 指向包外/不可解析的源 id → 落为根，path 仍完整
        stats, errors = self._import(
            s, [{"id": 10, "name": "孤立单位", "code": "ORG-LONE", "parent_id": 99}]
        )
        org = s.query(Organization).filter(Organization.code == "ORG-LONE").one()
        assert errors == []
        assert org.parent_id is None
        assert org.path == f"/{org.id}/"
        assert str(org.level) == "1"

    def test_existing_org_not_touched(self, session_factory):
        s = session_factory()
        existing = Organization(name="旧名称单位", code="ORG-KEEP", path="/88/", level=1)
        s.add(existing)
        s.commit()
        old_path = existing.path

        data = [
            {"id": 1, "name": "旧名称单位", "code": "ORG-KEEP", "parent_id": None},
        ]
        self._import(s, data)

        s.expire_all()
        kept = s.query(Organization).filter(Organization.code == "ORG-KEEP").one()
        # 既有行的层级由本机维护，导入不得改写 path/parent
        assert kept.path == old_path
        assert kept.parent_id is None


# ══════════════════════════════════════════════════════════════
# M29：overwrite 导入只写记录实际携带的键
# ══════════════════════════════════════════════════════════════


class TestM29UpsertMissingKeys:
    def test_missing_keys_do_not_null_existing_columns(self, session_factory):
        from app.services.data_package_service import DataPackageService

        s = session_factory()
        # organization_id 参与业务键判定（W18-D1/D5）：本机行必须带与导入目标
        # 一致的组织归属，否则会被判为「撞 id 的另一条记录」而改号插入。
        s.add(School(id=501, name="原学校名", address="原地址", principal="原校长", organization_id=1))
        s.commit()

        svc = DataPackageService(s)
        imported, skipped, errors = svc._bulk_upsert_records(
            School,
            [{"id": 501, "name": "新学校名"}],  # 未携带 address/principal
            org_id=1,
            overwrite=True,
        )
        s.commit()
        s.expire_all()

        row = s.get(School, 501)
        assert errors == []
        assert imported == 1
        assert row.name == "新学校名"          # 携带的键正常更新
        assert row.address == "原地址"         # 缺失的键保留旧值，不得写 NULL
        assert row.principal == "原校长"

    def test_explicit_none_is_written(self, session_factory):
        from app.services.data_package_service import DataPackageService

        s = session_factory()
        s.add(School(id=502, name="原学校", address="原地址", organization_id=1))
        s.commit()

        svc = DataPackageService(s)
        svc._bulk_upsert_records(
            School,
            [{"id": 502, "name": "新学校", "address": None}],  # 显式 None 与缺键不同
            org_id=1,
            overwrite=True,
        )
        s.commit()
        s.expire_all()

        row = s.get(School, 502)
        assert row.name == "新学校"
        assert row.address is None

    def test_mixed_key_sets_in_one_batch(self, session_factory):
        from app.services.data_package_service import DataPackageService

        s = session_factory()
        s.add(School(id=503, name="A 校", address="A 地址", principal="A 校长", organization_id=1))
        s.add(School(id=504, name="B 校", address="B 地址", principal="B 校长", organization_id=1))
        s.commit()

        svc = DataPackageService(s)
        # 同一批次两组键集合：A 组带 address，B 组带 principal
        svc._bulk_upsert_records(
            School,
            [
                {"id": 503, "name": "A 新", "address": "A 新地址"},
                {"id": 504, "name": "B 新", "principal": "B 新校长"},
            ],
            org_id=1,
            overwrite=True,
        )
        s.commit()
        s.expire_all()

        a = s.get(School, 503)
        b = s.get(School, 504)
        assert a.address == "A 新地址" and a.principal == "A 校长"
        assert b.principal == "B 新校长" and b.address == "B 地址"

    def test_pk_only_record_uses_do_nothing(self, session_factory):
        """记录只携带主键（无任何可更新列）→ 空 UPDATE 集合必须退化为 DO NOTHING
        （``DO UPDATE SET`` 空列表是非法 SQL；DO NOTHING 语义等价于「冲突即忽略」）。"""
        from app.services.data_package_service import DataPackageService

        svc = DataPackageService(session_factory())
        stmt = svc._build_upsert_statement(Todo, [{"id": 601}], "id", overwrite=True)
        assert "DO NOTHING" in str(stmt).upper()

        # 对照：携带可更新列时仍是 DO UPDATE，且只更新携带列
        stmt2 = svc._build_upsert_statement(Todo, [{"id": 601, "title": "t"}], "id", overwrite=True)
        compiled = str(stmt2)
        assert "DO UPDATE" in compiled.upper()
        assert "title" in compiled


# ══════════════════════════════════════════════════════════════
# M30：审批原子抢占（重放/并发不双写）
# ══════════════════════════════════════════════════════════════


def _seed_task(session_factory, levels=2):
    s = session_factory()
    wf = ApprovalWorkflow(name="R28 测试流程", entity_type="r28_fund", is_active=True)
    s.add(wf)
    s.flush()
    for level in range(1, levels + 1):
        s.add(
            ApprovalNode(
                workflow_id=wf.id,
                level=level,
                name=f"第{level}级",
                approver_type="user",
                approver_id=None,  # 未分配审批人：任何登录用户可审批（单机语义）
            )
        )
    task = ApprovalTask(
        workflow_id=wf.id,
        entity_type="r28_fund",
        entity_id=1,
        submitter_id=1,
        current_level=1,
        status=ApprovalStatus.PENDING.value,
    )
    s.add(task)
    s.commit()
    return s, task.id


class TestM30ApprovalAtomicClaim:
    def test_replay_after_final_approve_writes_once(self, session_factory):
        from app.services.approval_workflow_service import ApprovalWorkflowService

        s, task_id = _seed_task(session_factory, levels=1)
        svc = ApprovalWorkflowService(s)

        first = svc.approve_task(task_id, approver_id=10, standalone=True)
        assert first is not None
        assert first.status == ApprovalStatus.APPROVED.value

        replay = svc.approve_task(task_id, approver_id=10, standalone=True)
        assert replay is None
        records = s.query(ApprovalRecord).filter(ApprovalRecord.task_id == task_id).all()
        assert len(records) == 1
        assert records[0].level == 1

    def test_stale_level_claim_rejected(self, session_factory, monkeypatch):
        """check 与 act 之间行被并发推进会话更新 → 抢占失败、零写入。"""
        from app.services.approval_workflow_service import ApprovalWorkflowService

        s, task_id = _seed_task(session_factory, levels=2)
        svc = ApprovalWorkflowService(s)

        real_get = svc.get_task

        def racing_get(tid):
            task = real_get(tid)
            # 结束本会话读事务（expire_on_commit=False：task 保持陈旧快照），
            # 再由另一个连接推进级别 —— 模拟并发窗口
            s.commit()
            other = session_factory()
            try:
                other.query(ApprovalTask).filter(ApprovalTask.id == tid).update(
                    {"current_level": 9}
                )
                other.commit()
            finally:
                other.close()
            return task

        monkeypatch.setattr(svc, "get_task", racing_get)

        assert svc.approve_task(task_id, approver_id=10, standalone=True) is None

        s.expire_all()
        fresh = s.get(ApprovalTask, task_id)
        assert fresh.current_level == 9  # 并发方的推进保持，不被本请求二次推进
        assert fresh.status == ApprovalStatus.PENDING.value
        assert s.query(ApprovalRecord).filter(ApprovalRecord.task_id == task_id).count() == 0

    def test_middle_level_advances_once(self, session_factory):
        from app.services.approval_workflow_service import ApprovalWorkflowService

        s, task_id = _seed_task(session_factory, levels=2)
        svc = ApprovalWorkflowService(s)

        result = svc.approve_task(task_id, approver_id=10, standalone=True)
        assert result is not None
        s.expire_all()
        fresh = s.get(ApprovalTask, task_id)
        assert fresh.current_level == 2
        assert fresh.status == ApprovalStatus.PENDING.value
        records = s.query(ApprovalRecord).filter(ApprovalRecord.task_id == task_id).all()
        assert len(records) == 1
        assert records[0].level == 1
