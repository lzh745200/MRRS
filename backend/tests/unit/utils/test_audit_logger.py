"""
审计日志测试

测试 app/utils/audit_logger.py 模块
"""
import json
from unittest.mock import patch
from app.utils.audit_logger import (
    AuditLogger,
    AuditAction,
    AuditLevel,
    log_audit
)

class TestAuditLogger:
    """审计日志测试类"""

    @patch('app.utils.audit_logger.logger')
    def test_log_basic(self, mock_logger):
        """测试基本日志记录"""
        AuditLogger.log(
            action=AuditAction.LOGIN,
            user_id=123,
            username="testuser",
            level=AuditLevel.INFO
        )

        # 验证logger被调用
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "login" in call_args

    @patch('app.utils.audit_logger.logger')
    def test_log_with_details(self, mock_logger):
        """测试带详细信息的日志"""
        AuditLogger.log(
            action=AuditAction.UPDATE,
            user_id=123,
            username="testuser",
            resource_type="project",
            resource_id=456,
            details={"old_status": "pending", "new_status": "approved"},
            level=AuditLevel.INFO
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args.replace("[AUDIT] ", ""))

        assert log_data["action"] == "update"
        assert log_data["user_id"] == 123
        assert log_data["resource_type"] == "project"
        assert log_data["resource_id"] == 456
        assert log_data["details"]["old_status"] == "pending"

    @patch('app.utils.audit_logger.logger')
    def test_log_critical_level(self, mock_logger):
        """测试严重级别日志"""
        AuditLogger.log(
            action=AuditAction.DELETE,
            user_id=123,
            username="admin",
            level=AuditLevel.CRITICAL
        )

        # 验证使用critical级别
        mock_logger.critical.assert_called_once()

    @patch('app.utils.audit_logger.logger')
    def test_log_warning_level(self, mock_logger):
        """测试警告级别日志"""
        AuditLogger.log(
            action=AuditAction.LOGIN_FAILED,
            user_id=0,
            username="testuser",
            level=AuditLevel.WARNING
        )

        # 验证使用warning级别
        mock_logger.warning.assert_called_once()

    @patch('app.utils.audit_logger.logger')
    def test_log_login_success(self, mock_logger):
        """测试登录成功日志"""
        AuditLogger.log_login(
            user_id=123,
            username="testuser",
            success=True,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0"
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args.replace("[AUDIT] ", ""))

        assert log_data["action"] == "login"
        assert log_data["details"]["success"] is True
        assert log_data["ip_address"] == "192.168.1.100"

    @patch('app.utils.audit_logger.logger')
    def test_log_login_failure(self, mock_logger):
        """测试登录失败日志"""
        AuditLogger.log_login(
            user_id=0,
            username="testuser",
            success=False,
            ip_address="192.168.1.100",
            failure_reason="密码错误"
        )

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        log_data = json.loads(call_args.replace("[AUDIT] ", ""))

        assert log_data["action"] == "login_failed"
        assert log_data["details"]["success"] is False
        assert log_data["details"]["failure_reason"] == "密码错误"

    @patch('app.utils.audit_logger.logger')
    def test_log_data_change(self, mock_logger):
        """测试数据变更日志"""
        AuditLogger.log_data_change(
            action=AuditAction.UPDATE,
            user_id=123,
            username="testuser",
            resource_type="project",
            resource_id=456,
            old_data={"status": "pending"},
            new_data={"status": "approved"},
            ip_address="192.168.1.100"
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        log_data = json.loads(call_args.replace("[AUDIT] ", ""))

        assert log_data["action"] == "update"
        assert "old_data" in log_data["details"]
        assert "new_data" in log_data["details"]

    @patch('app.utils.audit_logger.logger')
    def test_log_sensitive_operation(self, mock_logger):
        """测试敏感操作日志"""
        AuditLogger.log_sensitive_operation(
            action=AuditAction.EXPORT,
            user_id=123,
            username="admin",
            details={"file_type": "excel", "record_count": 1000},
            ip_address="192.168.1.100"
        )

        mock_logger.critical.assert_called_once()
        call_args = mock_logger.critical.call_args[0][0]
        log_data = json.loads(call_args.replace("[AUDIT] ", ""))

        assert log_data["action"] == "export"
        assert log_data["level"] == "critical"

    @patch('app.utils.audit_logger.logger')
    def test_log_permission_change(self, mock_logger):
        """测试权限变更日志"""
        AuditLogger.log_permission_change(
            action=AuditAction.PERMISSION_GRANT,
            operator_id=123,
            operator_name="admin",
            target_user_id=456,
            target_username="user1",
            permission_details={"permission": "project:write"},
            ip_address="192.168.1.100"
        )

        mock_logger.critical.assert_called_once()
        call_args = mock_logger.critical.call_args[0][0]
        log_data = json.loads(call_args.replace("[AUDIT] ", ""))

        assert log_data["action"] == "permission_grant"
        assert log_data["details"]["target_user_id"] == 456

    @patch('app.utils.audit_logger.logger')
    def test_log_audit_convenience_function(self, mock_logger):
        """测试便捷函数"""
        log_audit(
            action=AuditAction.CREATE,
            user_id=123,
            username="testuser",
            resource_type="fund",
            resource_id=789
        )

        mock_logger.info.assert_called_once()

    def test_audit_action_enum(self):
        """测试审计操作枚举"""
        assert AuditAction.LOGIN == "login"
        assert AuditAction.LOGOUT == "logout"
        assert AuditAction.CREATE == "create"
        assert AuditAction.UPDATE == "update"
        assert AuditAction.DELETE == "delete"

    def test_audit_level_enum(self):
        """测试审计级别枚举"""
        assert AuditLevel.INFO == "info"
        assert AuditLevel.WARNING == "warning"
        assert AuditLevel.CRITICAL == "critical"

    @patch('app.utils.audit_logger.logger')
    def test_log_safely_returns_true_on_success(self, mock_logger):
        """log_safely：正常路径等同 log()，返回 True。

        2026-11-01 类型债棘轮：三个调用点各自的 try/except 收敛到本方法，
        这里锁住「成功时布尔返回」契约，避免调用方误判。
        """
        ok = AuditLogger.log_safely(action=AuditAction.CREATE, user_id=1, username="u")
        assert ok is True
        mock_logger.info.assert_called_once()

    @patch('app.utils.audit_logger.logger')
    def test_log_safely_swallows_failure_with_warning(self, mock_logger):
        """log_safely：审计失败必须吞掉异常并留 WARNING（否则备份结果被审计拖垮）。"""
        with patch.object(AuditLogger, 'log', side_effect=RuntimeError("audit db down")):
            ok = AuditLogger.log_safely(action=AuditAction.CREATE, user_id=1, username="u")

        assert ok is False
        mock_logger.warning.assert_called_once()
