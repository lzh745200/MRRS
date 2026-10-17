# -*- coding: utf-8 -*-
"""JSON 列可变性棘轮 —— R19 同类缺陷的横向排查结论（2026-10-17）。

背景：R19 修过一个高危缺陷 —— `two_factor_auth.backup_codes` 是裸 ``Column(JSON)``，
`verify_login` 里 ``backup_codes.remove(token)`` 的**就地修改**不产生 attribute 事件，
SQLAlchemy 认为属性未变、不生成 UPDATE，提交静默丢失 → 备用恢复码可无限复用。
约定是："需要就地改的 JSON 列必须 ``MutableList``/``MutableDict.as_mutable(JSON)``"。

本次横向排查（27 个 JSON 列逐一过筛）结论：**除 backup_codes 外，其余 26 列在代码里
全部是"整体赋值"（写入即完整快照），没有就地修改** —— 因此不需要 Mutable 包装；
需要锁的是这条结论本身，防止将来新增 JSON 列时"默认裸列 + 就地改"重现 R19 缺陷。

三层锁定：

1. **台账棘轮**：全库 JSON 列集合 == 已复核清单（新增列必须显式登记，
   登记时强制回答"就地改还是整体替换"）；
2. **声明检查**：必须就地改的列（现为 backup_codes）在模型源码里必须真的写成
   ``MutableList.as_mutable(JSON)`` —— 注意 Mutable **无法用类型检测**：
   SQLAlchemy 的 ``as_mutable`` 不改列类型，而是通过 ``mapper_configured``
   事件给属性挂监听（实测 ``col.type`` 仍是普通 JSON）；
3. **行为锁定**：backup_codes 的就地 remove 必须落库（直接复现 R19 的缺陷行为面）。
"""

import importlib
import pkgutil
from pathlib import Path

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import sessionmaker

import app.models as models_pkg
from app.models import Base
from app.models.two_factor_auth import TwoFactorAuth

MODELS_DIR = Path(__file__).resolve().parents[2] / "app" / "models"

# ── 已复核清单（2026-10-17）：table.column —— 全部为"整体替换"语义 ──────────────
# 新增 JSON 列会让台账用例失败：若该列会被**就地修改**，必须改用
# MutableList/MutableDict.as_mutable(JSON) 并在此处标注 "就地改"；
# 若整体替换，把它加进本清单（等于声明"已复核，不需要 Mutable"）。
REVIEWED_PLAIN_JSON_COLUMNS = {
    "alert_rules.channels",                          # 告警渠道列表：整体重写
    "alert_rules.email_recipients",                  # 收件人列表：整体重写
    "api_access_logs.request_body",                  # 访问日志：写入即快照，只读
    "api_access_logs.request_params",
    "approval_tasks.change_data",                    # 审批快照：写入即定型
    "approval_tasks.original_data",
    "audit_changes.new_value",                       # 审计留痕：只增不改
    "audit_changes.old_value",
    "audit_logs.metadata",
    "audit_logs.new_value",
    "audit_logs.old_value",
    "data_conflicts.import_data",                    # 冲突记录：整体写入/整体合并
    "data_conflicts.local_data",
    "data_conflicts.merged_data",
    "data_export_logs.data_types",                   # 导出任务参数：整体替换
    "data_export_logs.filters",
    "data_packages.data_types",                      # 数据包清单：打包时定型
    "data_packages.manifest",
    "data_sync_logs.details",                        # 同步日志：写入即快照
    "data_sync_logs.modules",
    "donation_items.attachments",                    # 捐赠物资凭证：登记/更新时整体替换（_normalize_attachments 全量重写，无就地改）
    "effectiveness_evaluations.indicators",          # 指标字典：按指标整体替换
    "export_tasks.query_params",                     # 导出任务参数：整体替换
    "import_histories.error_details",                # 导入错误明细：写入即定型
    "security_events.affected_resources",            # 安全事件：只增不改
    "security_events.details",
}

# 就地改语义的列（必须 Mutable 包装）；R19 修复的 backup_codes 即此列。
MUTABLE_JSON_COLUMNS = {
    "two_factor_auth.backup_codes",
}


def _load_all_models():
    """导入 app.models 全部子模块（`import app.models` 本身不登记任何表）。"""
    for info in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"app.models.{info.name}")


@pytest.fixture(scope="module", autouse=True)
def _all_models_loaded():
    _load_all_models()


def _json_columns():
    """全库 JSON 列集合（table.column）。"""
    found = set()
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSON):
                found.add(f"{table.name}.{col.name}")
    return found


class TestInventoryRatchet:
    def test_json_column_inventory_is_fully_reviewed(self):
        """JSON 列台账：新增列必须显式登记（强制回答就地改 / 整体替换）。"""
        discovered = _json_columns()
        reviewed = REVIEWED_PLAIN_JSON_COLUMNS | MUTABLE_JSON_COLUMNS
        new_columns = sorted(discovered - reviewed)
        stale_entries = sorted(reviewed - discovered)
        assert not new_columns, (
            "发现未复核的 JSON 列：%s\n"
            "请先决定语义——就地修改（delete/append/update）必须用 "
            "MutableList/MutableDict.as_mutable(JSON) 并登记进 MUTABLE_JSON_COLUMNS；"
            "整体替换则登记进 REVIEWED_PLAIN_JSON_COLUMNS。" % new_columns
        )
        assert not stale_entries, "清单里有已不存在的列（改名/删列后请同步台账）：%s" % stale_entries

    def test_two_factor_backup_codes_declared_mutable(self):
        """就地改的列必须在模型源码里真的声明 MutableList（类型检测不可靠）。"""
        source = (MODELS_DIR / "two_factor_auth.py").read_text(encoding="utf-8")
        assert "backup_codes = Column(MutableList.as_mutable(JSON)" in source

    def test_baseline_sizes_are_documented(self):
        """台账规模快照：防"大改后清单被顺手删空"式弱化。"""
        assert len(REVIEWED_PLAIN_JSON_COLUMNS) == 26
        assert len(MUTABLE_JSON_COLUMNS) == 1
        assert len(_json_columns()) == 27


class TestInplaceMutationSemantics:
    @pytest.fixture
    def session_factory(self, tmp_path):
        engine = create_engine(f"sqlite:///{tmp_path / 'json_mut.db'}")
        Base.metadata.create_all(bind=engine)
        yield sessionmaker(bind=engine)
        engine.dispose()

    def test_backup_codes_inplace_removal_persists(self, session_factory):
        """R19 缺陷行为面：就地 remove 必须落库（否则恢复码可无限复用）。"""
        s = session_factory()
        s.add(TwoFactorAuth(user_id=1, secret_key="x", backup_codes=["aaa", "bbb"], enabled=True))
        s.commit()
        s.close()

        s = session_factory()
        row = s.query(TwoFactorAuth).filter_by(user_id=1).one()
        row.backup_codes.remove("aaa")  # 就地修改
        s.commit()
        s.close()

        s = session_factory()
        row = s.query(TwoFactorAuth).filter_by(user_id=1).one()
        assert list(row.backup_codes) == ["bbb"], "就地 remove 未落库 —— R19 缺陷回归"
        s.close()
