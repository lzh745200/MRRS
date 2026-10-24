"""OFFLINE_MODE 离线开关：外部告警短路与非离线回退测试。

覆盖契约（离线适配审计 A1/A2 收口）：
1. 出厂默认 ``settings.OFFLINE_MODE is True``（完全离线单机部署）；
2. 离线时 ``send_email_alert`` / ``send_webhook_alert`` 在**入口处**短路：
   返回 False、记 INFO「离线模式，跳过外部告警」，且不解析 DNS、不建连；
3. 非离线模式（``OFFLINE_MODE=False``）仍走原路径：SMTP 建连发送 / httpx POST；
4. SMTP 的同步 smtplib 调用被 ``asyncio.to_thread`` 包裹，不在事件循环线程执行。
"""

import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _email_settings(mock_settings, offline: bool):
    """给 settings 桩补齐邮件告警所需字段。"""
    mock_settings.OFFLINE_MODE = offline
    mock_settings.SMTP_HOST = "smtp.test.com"
    mock_settings.SMTP_PORT = 587
    mock_settings.SMTP_USER = "user@test.com"
    mock_settings.SMTP_PASSWORD = "secret"
    mock_settings.SMTP_FROM = "noreply@test.com"
    mock_settings.SMTP_TIMEOUT = 10


class _FakeSMTP:
    """记录调用线程与关键动作的 SMTP 替身。"""

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        _FakeSMTP.observed["thread"] = threading.get_ident()
        _FakeSMTP.observed["host"] = host
        _FakeSMTP.observed["port"] = port
        _FakeSMTP.observed["timeout"] = timeout

    observed = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def starttls(self, context=None):
        _FakeSMTP.observed["starttls"] = context is not None

    def login(self, user, password):
        _FakeSMTP.observed["login"] = (user, password)

    def send_message(self, msg):
        _FakeSMTP.observed["sent"] = True


class TestOfflineModeDefault:
    def test_settings_defaults_to_offline(self):
        """出厂默认必须是离线模式（完全离线单机部署）。"""
        from app.core.config import settings

        assert settings.OFFLINE_MODE is True


class TestEmailAlertOffline:
    @pytest.mark.asyncio
    async def test_short_circuits_without_touching_smtp_when_offline(self):
        """离线：配置齐全也不建连，直接 False + INFO。"""
        from app.services.alert_service import AlertService

        with patch("app.services.alert_service.settings") as mock_st:
            _email_settings(mock_st, offline=True)
            with patch("smtplib.SMTP") as smtp_cls:
                with patch("app.services.alert_service.logger") as mock_log:
                    result = await AlertService.send_email_alert(
                        ["a@b.com"], "主题", "内容"
                    )

        assert result is False
        # 关键：不解析 DNS、不建连
        smtp_cls.assert_not_called()
        mock_log.info.assert_called_once()
        assert "离线模式，跳过外部告警" in mock_log.info.call_args[0][0]
        mock_log.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_online_path_still_sends_and_runs_in_worker_thread(self):
        """非离线：仍走 SMTP 发送，且同步调用被移出事件循环线程。"""
        from app.services.alert_service import AlertService

        _FakeSMTP.observed = {}
        main_thread = threading.get_ident()
        with patch("app.services.alert_service.settings") as mock_st:
            _email_settings(mock_st, offline=False)
            with patch("smtplib.SMTP", _FakeSMTP):
                result = await AlertService.send_email_alert(
                    ["a@b.com", "c@d.com"], "主题", "内容"
                )

        assert result is True
        assert _FakeSMTP.observed["sent"] is True
        assert _FakeSMTP.observed["host"] == "smtp.test.com"
        assert _FakeSMTP.observed["timeout"] == 10
        assert _FakeSMTP.observed["starttls"] is True
        assert _FakeSMTP.observed["login"] == ("user@test.com", "secret")
        # asyncio.to_thread 包裹：smtplib 在工作线程执行，不阻塞事件循环
        assert _FakeSMTP.observed["thread"] != main_thread

    @pytest.mark.asyncio
    async def test_online_path_still_warns_on_incomplete_config(self):
        """非离线 + 配置不完整：保持原行为（WARNING 并返回 False）。"""
        from app.services.alert_service import AlertService

        with patch("app.services.alert_service.settings") as mock_st:
            _email_settings(mock_st, offline=False)
            mock_st.SMTP_HOST = None
            with patch("smtplib.SMTP") as smtp_cls:
                with patch("app.services.alert_service.logger") as mock_log:
                    result = await AlertService.send_email_alert(
                        ["a@b.com"], "主题", "内容"
                    )

        assert result is False
        smtp_cls.assert_not_called()
        mock_log.warning.assert_called_once_with("SMTP配置不完整,跳过邮件发送")


class TestWebhookAlertOffline:
    @pytest.mark.asyncio
    async def test_short_circuits_without_building_http_client_when_offline(self):
        """离线：不创建 httpx 客户端、不发起请求。"""
        from app.services.alert_service import AlertService

        with patch("app.services.alert_service.settings") as mock_st:
            mock_st.OFFLINE_MODE = True
            with patch("httpx.AsyncClient") as client_cls:
                with patch("app.services.alert_service.logger") as mock_log:
                    result = await AlertService.send_webhook_alert(
                        "https://hook.example.com/hook", "告警消息", webhook_type="dingtalk"
                    )

        assert result is False
        client_cls.assert_not_called()
        mock_log.info.assert_called_once()
        assert "离线模式，跳过外部告警" in mock_log.info.call_args[0][0]

    @pytest.mark.asyncio
    async def test_online_path_still_posts_when_not_offline(self):
        """非离线：保持原 httpx 行为（timeout=10.0 + dingtalk 负载）。"""
        from app.services.alert_service import AlertService

        mock_resp = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        with patch("app.services.alert_service.settings") as mock_st:
            mock_st.OFFLINE_MODE = False
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await AlertService.send_webhook_alert(
                    "https://hook.example.com/hook", "告警消息", webhook_type="dingtalk"
                )

        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]["timeout"] == 10.0
        assert call_args[1]["json"]["msgtype"] == "text"
