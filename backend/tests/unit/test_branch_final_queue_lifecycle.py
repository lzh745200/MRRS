"""终局分支清零 —— task_queue.py 与 fund_lifecycle.py 的剩余部分分支。

task_queue.py 目标弧（`test_worker_timeout_error_continue` 在 Windows/3.13 上
会因 timeout 分支紧循环饿死事件循环而挂死，故该用例对应的弧改由下方
`test_worker_real_timeout_then_exit` 以"真实 1s 超时 + 第二次调用翻转 _running"
的确定性方式覆盖）：
- 190->193  submit 时 _queue 为 None 且 _running 为真 → start() 早退，不入队
- 213->215  cancel_task 对终态任务返回 False
- 260->exit _running 为假 → worker 循环零次直接退出
- 264       except asyncio.TimeoutError → continue
- 282->290  执行中任务被取消 → 不置 COMPLETED，仅 finally 写 completed_at
- 285->290  执行中任务被取消且抛异常 → 不置 FAILED，仅 finally 写 completed_at

fund_lifecycle.py 目标弧（全量重建口径实测）：
- 606->612   额度锁定：拨付额度 ≤ 基线 → 放行提交
- 641->640   拨付计划：同一 fund 有多条 baseline → 仅保留最新
- 761->780   创建划转凭证：余额校验时经费已不可见 → 跳过余额校验
- 808->810   凭证详情：voucher 未挂项目 → 跳过项目级授权
- 1094->1101 合同详情：合同未挂项目 → 跳过项目级授权
- 1646->1648 决算审批：有意见但无绩效分 → 跳过写分、继续写等级
- 1872->1876 调整原因校验器：空值 → 跳过 strip，原样返回
"""
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.base import Base
from app.models.fund import Fund
from app.models.fund_lifecycle import (
    BudgetBaseline,
    FundContract,
    FundSettlement,
    FundTransferVoucher,
    SettlementStatus,
)
from app.models.project import Project


# ===========================================================================
#  task_queue.py — 直接驱动 LocalTaskQueue 的确定性用例
# ===========================================================================
class TestTaskQueueFinalBranches:
    async def test_submit_running_but_queue_unset_skips_enqueue(self):
        """190->193：_running 为真但 _queue 为 None → start() 早退，任务不入队。"""
        from app.services.task_queue import LocalTaskQueue

        q = LocalTaskQueue()
        q._running = True
        q._queue = None

        async def noop():
            return 1

        task_id = await q.submit(noop, name="noop")

        assert task_id in q._tasks
        assert q._queue is None  # start() 因 _running 已为真而早退，未新建队列

    def test_cancel_task_terminal_state_returns_false(self):
        """213->215：终态任务不可取消 → cancel() 假分支，返回 False。"""
        from app.services.task_queue import LocalTaskQueue, Task, TaskStatus

        q = LocalTaskQueue()
        t = Task(func=lambda: 1, name="done")
        t.status = TaskStatus.COMPLETED
        q._tasks[t.id] = t

        assert q.cancel_task(t.id) is False
        assert t.status == TaskStatus.COMPLETED

    async def test_worker_exits_immediately_when_not_running(self):
        """260->exit：_running 为假 → while 零次迭代，worker 立即返回。"""
        import asyncio

        from app.services.task_queue import LocalTaskQueue

        q = LocalTaskQueue()
        q._running = False
        q._queue = asyncio.PriorityQueue()

        await asyncio.wait_for(q._worker("w"), timeout=2)  # 不应阻塞

        assert q._running is False

    async def test_worker_real_timeout_then_exit(self):
        """264：真实 1s 超时 → except TimeoutError → continue，二次循环退出。

        等价于挂死的 test_worker_timeout_error_continue，但不使用
        AsyncMock 立即抛 TimeoutError（那会形成无 await 让渡的紧循环）。
        """
        import asyncio

        from app.services.task_queue import LocalTaskQueue, Task

        class _SlowThenIdleQueue:
            def __init__(self, owner):
                self._owner = owner
                self.calls = 0

            async def get(self):
                self.calls += 1
                if self.calls == 1:
                    await asyncio.sleep(5)  # 超过 wait_for 的 1.0s → 真超时
                self._owner._running = False  # 第二轮后让 while 自然退出
                return Task(func=lambda: "done", name="last")

        q = LocalTaskQueue()
        q._running = True
        fake = _SlowThenIdleQueue(q)
        q._queue = fake

        await asyncio.wait_for(q._worker("w"), timeout=10)

        assert fake.calls >= 2  # 首轮超时 continue，次轮取到任务后退出

    async def test_task_cancelled_during_exec_not_marked_completed(self):
        """282->290：执行中被取消 → 保持 RUNNING，仅 finally 写 completed_at。"""
        import asyncio

        from app.services.task_queue import LocalTaskQueue, Task, TaskStatus

        q = LocalTaskQueue()
        q._queue = asyncio.PriorityQueue()
        q._running = True
        holder = {}

        async def self_cancel_then_return():
            holder["task"]._cancelled = True
            return "ok"

        t = Task(func=self_cancel_then_return, name="self-cancel")
        holder["task"] = t
        q._tasks[t.id] = t
        await q._queue.put(t)

        worker = asyncio.create_task(q._worker("w"))
        await asyncio.sleep(0.2)
        q._running = False
        await asyncio.wait_for(worker, timeout=5)

        assert t.status == TaskStatus.RUNNING  # 未置 COMPLETED
        assert t.completed_at is not None  # finally 仍写入完成时间

    async def test_task_cancelled_and_raised_not_marked_failed(self):
        """285->290：执行中被取消且抛异常 → 不置 FAILED，仅 finally 写 completed_at。"""
        import asyncio

        from app.services.task_queue import LocalTaskQueue, Task, TaskStatus

        q = LocalTaskQueue()
        q._queue = asyncio.PriorityQueue()
        q._running = True
        holder = {}

        async def self_cancel_then_raise():
            holder["task"]._cancelled = True
            raise ValueError("boom")

        t = Task(func=self_cancel_then_raise, name="cancel-raise")
        holder["task"] = t
        q._tasks[t.id] = t
        await q._queue.put(t)

        worker = asyncio.create_task(q._worker("w"))
        await asyncio.sleep(0.2)
        q._running = False
        await asyncio.wait_for(worker, timeout=5)

        assert t.status == TaskStatus.RUNNING  # 未置 FAILED
        assert t.error is None  # 未记录错误
        assert t.completed_at is not None


# ===========================================================================
#  fund_lifecycle.py — HTTP 层夹具（自持，不跨文件导入）
# ===========================================================================
@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session):
    from app.main import app

    def _get_db():
        yield db_session

    admin = Mock()
    admin.id = 1
    admin.username = "admin"
    admin.role = "admin"
    admin.is_superuser = True
    admin.is_active = True
    admin.permissions_list = ["*"]
    admin.organization_id = 1
    admin.email = "admin@test.com"
    admin.full_name = "管理员"

    async def _get_current_user():
        return admin

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


@pytest.fixture
def project(db_session):
    p = Project(
        id=1,
        name="测试项目",
        type="infrastructure",
        budget=Decimal("1000.00"),
        status="in_progress",
        progress=50.0,
        organization_id=1,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def fund(db_session, project):
    f = Fund(
        id=1,
        project_id=project.id,
        name="测试经费",
        type="project",
        fund_type="project",
        fund_source="military",
        amount=Decimal("500.00"),
        planned_amount=Decimal("500.00"),
        approved_amount=Decimal("500.00"),
        allocated_amount=Decimal("200.00"),
        used_amount=Decimal("100.00"),
        remaining_amount=Decimal("400.00"),
        code="F001",
        lifecycle_phase=1,
        budget_locked=False,
        status="approved",
        operator="张三",
        organization_id=1,
    )
    db_session.add(f)
    db_session.flush()
    return f


class TestFundLifecycleFinalBranches:
    def test_quota_lock_within_baseline(self, client, fund, db_session):
        """606->612：拨付额度未超基线 → 不抛 400，提交并返回已锁定。"""
        fund.budget_locked = True
        fund.allocated_amount = Decimal("300.00")
        fund.approved_amount = Decimal("300.00")
        db_session.add(BudgetBaseline(
            fund_id=fund.id, project_id=fund.project_id, snapshot_year=2025,
            category="project", baseline_amount=Decimal("500.00"),
        ))
        db_session.flush()

        resp = client.post(f"/api/v1/fund-lifecycle/quota-lock/{fund.id}")

        assert resp.status_code == 200
        assert resp.json()["message"] == "额度已锁定"
        assert resp.json()["data"]["allocated"] == 300.0

    def test_allocation_plan_keeps_newest_baseline_only(self, client, project, fund, db_session):
        """641->640：同一 fund 多条 baseline → 仅保留最新（id 最大）的一条。"""
        db_session.add(BudgetBaseline(
            fund_id=fund.id, project_id=project.id, snapshot_year=2025,
            category="project", baseline_amount=Decimal("111.00"),
        ))
        db_session.flush()
        db_session.add(BudgetBaseline(
            fund_id=fund.id, project_id=project.id, snapshot_year=2025,
            category="project", baseline_amount=Decimal("222.00"),
        ))
        db_session.flush()

        resp = client.get(f"/api/v1/fund-lifecycle/allocation-plan/{project.id}")

        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["baseline_amount"] == 222.0  # 重复 fund_id 被跳过

    def test_get_transfer_voucher_without_project(self, client, db_session):
        """808->810：凭证未挂项目 → 跳过项目级授权校验。"""
        db_session.add(FundTransferVoucher(
            id=1, project_id=None, voucher_no="V-NOP",
            direction="military_to_local", amount=Decimal("10.00"), status="draft",
        ))
        db_session.flush()

        resp = client.get("/api/v1/fund-lifecycle/transfer-vouchers/1")

        assert resp.status_code == 200
        assert resp.json()["data"]["voucher_no"] == "V-NOP"
        assert resp.json()["data"]["project_id"] is None

    def test_get_contract_without_project(self, client, db_session):
        """1094->1101：合同未挂项目 → 跳过项目级授权，返回详情。"""
        db_session.add(FundContract(
            id=1, project_id=None, contract_no="C-NOP", contract_name="无项目合同",
        ))
        db_session.flush()

        resp = client.get("/api/v1/fund-lifecycle/contracts/1")

        assert resp.status_code == 200
        assert resp.json()["data"]["contract_no"] == "C-NOP"
        assert resp.json()["data"]["project_id"] is None

    def test_approve_settlement_level_without_score(self, client, project, db_session):
        """1646->1648：有审批意见但未给绩效分 → 跳过写分，继续写等级。"""
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()

        resp = client.post("/api/v1/fund-lifecycle/settlement/1/approve",
                           json={"audit_opinion": "批准", "performance_level": "B"})

        assert resp.status_code == 200
        db_session.refresh(s)
        assert s.performance_level == "B"
        assert s.performance_score is None  # 未提供分数 → 保持 None

    def test_quota_adjust_reason_validator_empty_returns_as_is(self):
        """1872->1876：空字符串 → if v 假 → 原样返回（不抛 ValueError）。"""
        from app.api.v1.fund_lifecycle import QuotaAdjustRequest

        assert QuotaAdjustRequest.validate_reason("") == ""

    async def test_create_transfer_voucher_fund_missing_at_balance_check(self):
        """761->780：存在性校验通过后余额校验查不到经费 → 跳过校验仍创建。

        竞态导致"校验时存在、余额查询时已不可见"时不得 500；用直调 + mock db
        按序注入 4 次查询：凭证编号(无) / Fund 存在 / 后续校验 Fund 存在 / 余额 Fund 缺失。
        """
        from app.api.v1.fund_lifecycle import TransferVoucherCreate, create_transfer_voucher

        def _q(first):
            q = MagicMock()
            q.filter.return_value = q
            q.first.return_value = first
            return q

        fund_stub = Mock()  # 真值即可，仅用于存在性校验
        db = MagicMock()
        db.query.side_effect = [_q(None), _q(fund_stub), _q(fund_stub), _q(None)]

        user = Mock(id=1, username="admin", role="admin", is_superuser=True, full_name="管理员")
        data = TransferVoucherCreate(
            fund_id=1, voucher_no="V-EDGE", direction="military_to_local", amount=10.0,
        )

        with patch("app.api.v1.fund_lifecycle.safe_commit"), \
             patch("app.api.v1.fund_lifecycle.write_work_log"):
            resp = await create_transfer_voucher(data, current_user=user, db=db)

        assert resp["code"] == 200
        assert resp["message"] == "创建成功"
        assert db.query.call_count == 4  # 余额校验查询已执行但返回 None
        created = db.add.call_args.args[0]
        assert created.voucher_no == "V-EDGE"
