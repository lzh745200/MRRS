"""app/api/v1/system/zero_trust.py 覆盖率补缺测试

补缺行：118-119（安全事件持久化失败后回滚再失败）、
265-271（未认证用户评估因子）、300-306（非 HTTPS 传输因子）、
321-324（low_risk / medium_risk 信任等级）、333/335（安全建议）、
518-519（事件统计循环累加）。

注：325-328（high_risk / untrusted 等级）在当前实现下不可达——
total_score 从 100 起最多被扣 40（未认证）+ 10（非 HTTPS）= 50 分，
评分不可能低于 50，见测试文件末尾说明。
"""

from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.system import zero_trust as zt
from app.api.v1.system.zero_trust import (
    _record_security_event,
    get_security_event_stats,
    get_trust_assessment,
)


def _make_request(scheme: str = "https", client_host: str = "10.0.0.1"):
    req = MagicMock()
    req.client.host = client_host
    req.url.scheme = scheme
    return req


# ── _record_security_event：回滚失败分支（lines 118-119） ─────────────────


class TestRecordSecurityEventRollbackFailure:
    def test_rollback_failure_is_logged_and_swallowed(self):
        """持久化失败后回滚再抛错 → 记录 warning 且不向上抛出（覆盖 118-119）。"""
        mock_db = MagicMock()
        mock_db.rollback.side_effect = RuntimeError("rollback broken")

        with patch.object(zt, "safe_commit", side_effect=RuntimeError("commit broken")):
            with patch.object(zt, "logger") as mock_logger:
                result = _record_security_event(
                    mock_db,
                    event_type="sensitive_access",
                    source="user:admin",
                    severity="high",
                    message="test rollback failure",
                )

        # 持久化失败 → id 保持 None，时间戳仍为构造时的值
        assert result["id"] is None
        assert result["event_type"] == "sensitive_access"
        assert result["source"] == "user:admin"
        # exception 记录持久化失败，warning 记录回滚失败 + 高严重度事件
        mock_logger.exception.assert_called_once()
        assert mock_logger.warning.call_count == 2
        warning_texts = " ".join(str(c.args[0]) for c in mock_logger.warning.call_args_list)
        assert "回滚失败" in warning_texts


# ── get_trust_assessment：未认证 / 非 HTTPS / 低分等级与建议 ──────────────


class TestTrustAssessmentBranches:
    """评分为因子分求和归一（深审 #93）后的期望值。

    原断言（60/50/90）锁定的是"正因子分只 append 不参与计算"的失效模型：
    总分只被两处硬编码扣分影响，与 factors 列表自相矛盾。现按
    100×Σ因子分/65 计算：未认证 = (-40+15+10+10+5)/65 → 0；
    已认证 + HTTP = (25+15+10-10+5)/65 → 69.2。
    """

    async def test_unauthenticated_https_is_untrusted(self):
        """未认证 + HTTPS → Σ=0 → 0.0 → untrusted（覆盖认证失败因子与等级分支）。"""
        result = await get_trust_assessment(_make_request(scheme="https"), current_user=None)

        data = result["data"]
        assert result["success"] is True
        assert data["score"] == 0.0
        assert data["level"] == "untrusted"
        auth_factor = next(f for f in data["factors"] if f["factor"] == "authentication")
        assert auth_factor["status"] == "fail"
        assert auth_factor["score"] == -40
        # 评分 < 60 → 触发"信任评分偏低"建议
        assert data["recommendations"] == ["信任评分偏低，建议审查安全配置"]

    async def test_unauthenticated_http_is_also_untrusted(self):
        """未认证 + HTTP → Σ=-10 → 夹取为 0.0 → untrusted，两条建议。"""
        result = await get_trust_assessment(_make_request(scheme="http"), current_user=None)

        data = result["data"]
        assert data["score"] == 0.0
        assert data["level"] == "untrusted"
        transport = next(f for f in data["factors"] if f["factor"] == "transport_security")
        assert transport["status"] == "warning"
        assert transport["score"] == -10
        assert data["recommendations"] == [
            "建议启用HTTPS确保传输层安全",
            "信任评分偏低，建议审查安全配置",
        ]

    async def test_authenticated_http_is_low_risk_with_https_recommendation(self):
        """已认证 + HTTP → Σ=45 → 69.2 → low_risk，仅 HTTPS 建议。"""
        user = MagicMock()
        user.username = "admin"

        result = await get_trust_assessment(_make_request(scheme="http"), current_user=user)

        data = result["data"]
        assert data["score"] == 69.2
        assert data["level"] == "low_risk"
        assert data["recommendations"] == ["建议启用HTTPS确保传输层安全"]


# ── get_security_event_stats：非空事件统计（lines 518-519） ───────────────


class TestSecurityEventStatsWithEvents:
    async def test_aggregates_severity_and_type(self):
        """数据库中有事件 → 按严重度/类型累加统计（覆盖 518-519）。"""
        e1 = MagicMock(severity="high", event_type="intrusion")
        e2 = MagicMock(severity="info", event_type="login")
        e3 = MagicMock(severity="high", event_type="login")

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = [e1, e2, e3]

        result = await get_security_event_stats(current_user=MagicMock(), db=mock_db)

        data = result["data"]
        assert data["total_events"] == 3
        assert data["by_severity"] == {"high": 2, "info": 1}
        assert data["by_type"] == {"intrusion": 1, "login": 2}
        # 2 个高严重度事件（0 < count <= 5）→ normal
        assert data["high_severity_count"] == 2
        assert data["security_posture"] == "normal"

    async def test_warning_posture_over_threshold(self):
        """高严重度事件 > 5 → security_posture 为 warning。"""
        events = [MagicMock(severity="critical", event_type="intrusion") for _ in range(6)]

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = events

        result = await get_security_event_stats(current_user=MagicMock(), db=mock_db)

        data = result["data"]
        assert data["high_severity_count"] == 6
        assert data["security_posture"] == "warning"
        assert data["by_severity"] == {"critical": 6}


# ── 不可达分支说明 ─────────────────────────────────────────────────────────
# 深审 #93 改为按因子分求和归一（100×Σ/65）后，可达档位为
# 100.0（已认证 + HTTPS）/ 69.2（已认证 + HTTP）/ 0.0（未认证，端点依赖下不可达），
# medium_risk（40~59）与 high_risk（20~39）在现有权重下没有对应组合，
# 已在 zero_trust.py 中标注 pragma 并说明原因。
