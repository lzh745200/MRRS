"""
告警服务
提供多渠道告警功能(邮件、Webhook)

离线契约：``settings.OFFLINE_MODE``（出厂默认 True）为真时，两个通道都在
**入口处**短路 —— 不解析 DNS、不建立连接、不发起 HTTP 请求，只记 INFO
日志并返回 False。完全离线单机部署因此不存在任何出网行为；现场确需接入
内网邮件服务器或钉钉/企业微信，必须显式设置 ``OFFLINE_MODE=false``。
"""

import asyncio
import logging
import smtplib
import ssl
from datetime import timezone, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 离线短路日志模板（%s 为通道名），便于现场按同一前缀检索日志
_OFFLINE_SKIP_LOG = "离线模式，跳过外部告警（%s通道）"


def _offline_mode() -> bool:
    """读取离线总开关；属性缺失时按"离线"处理（安全默认，宁可不发也不出网）。"""
    return bool(getattr(settings, "OFFLINE_MODE", True))


def _send_email_sync(
    host: str,
    port: int,
    user: str,
    password: str,
    message: MIMEMultipart,
    timeout: int,
) -> None:
    """同步 SMTP 发送实现（由 ``asyncio.to_thread`` 包裹，不阻塞事件循环）。

    深审 #69：starttls 必须显式传 SSL context（否则不校验证书链/主机名），
    且 SMTP 必须带 timeout（服务器挂起时不再无限阻塞）。
    """
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=timeout) as server:
        server.starttls(context=context)
        server.login(user, password)
        server.send_message(message)


class AlertService:
    """告警服务"""

    @staticmethod
    async def send_email_alert(recipients: List[str], subject: str, message: str) -> bool:
        """
        发送邮件告警

        Args:
            recipients: 收件人列表
            subject: 邮件主题
            message: 邮件内容

        Returns:
            是否发送成功（离线模式下恒为 False，且不产生任何网络 I/O）
        """
        try:
            # 离线总开关：入口处短路，先于任何配置解析 / DNS 解析 / 建连
            if _offline_mode():
                logger.info(_OFFLINE_SKIP_LOG, "邮件")
                return False

            # 获取SMTP配置
            smtp_host = getattr(settings, "SMTP_HOST", None)
            smtp_port = getattr(settings, "SMTP_PORT", 587)
            smtp_user = getattr(settings, "SMTP_USER", None)
            smtp_password = getattr(settings, "SMTP_PASSWORD", None)
            # SMTP_FROM 未配置时 config 里该属性仍存在但为 None，getattr 的
            # default 不会生效 → 发件人为空。改为显式回退到 smtp_user（深审 #70）。
            smtp_from = getattr(settings, "SMTP_FROM", None) or smtp_user

            # 超时：SMTP 服务器挂起时避免无限阻塞。
            smtp_timeout = getattr(settings, "SMTP_TIMEOUT", 10)
            try:
                smtp_timeout = max(1, int(smtp_timeout))
            except (TypeError, ValueError):
                logger.warning("SMTP_TIMEOUT 配置非法，回退 10 秒")
                smtp_timeout = 10

            if not all([smtp_host, smtp_user, smtp_password, smtp_from]):
                logger.warning("SMTP配置不完整,跳过邮件发送")
                return False

            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = smtp_from
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = subject

            msg.attach(MIMEText(message, "plain", "utf-8"))

            # 发送邮件：smtplib 是同步阻塞调用，必须移出事件循环线程，
            # 否则 SMTP 服务器不响应时整个 ASGI loop 被卡住（≤ SMTP_TIMEOUT 秒）。
            await asyncio.to_thread(
                _send_email_sync,
                smtp_host,
                smtp_port,
                smtp_user,
                smtp_password,
                msg,
                smtp_timeout,
            )

            logger.info(f"邮件告警已发送: {subject}")
            return True

        except Exception as e:
            logger.error(f"发送邮件告警失败: {e}")
            return False

    @staticmethod
    async def send_webhook_alert(webhook_url: str, message: str, webhook_type: str = "generic") -> bool:
        """
        发送Webhook告警

        Args:
            webhook_url: Webhook URL
            message: 告警消息
            webhook_type: Webhook类型(generic/dingtalk/wecom)

        Returns:
            是否发送成功（离线模式下恒为 False，且不创建任何 HTTP 客户端）
        """
        try:
            # 离线总开关：入口处短路，先于构造 payload / 创建 httpx 客户端
            if _offline_mode():
                logger.info(_OFFLINE_SKIP_LOG, "Webhook")
                return False

            # 根据类型构造不同的消息格式
            if webhook_type == "dingtalk":
                payload = {
                    "msgtype": "text",
                    "text": {"content": f"【系统告警】\n{message}"},
                }
            elif webhook_type == "wecom":
                payload = {
                    "msgtype": "text",
                    "text": {"content": f"【系统告警】\n{message}"},
                }
            else:
                payload = {
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # 发送HTTP请求
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload, timeout=10.0)
                response.raise_for_status()

            logger.info(f"Webhook告警已发送: {webhook_url}")
            return True

        except Exception as e:
            logger.error(f"发送Webhook告警失败: {e}")
            return False
