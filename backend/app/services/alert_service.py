"""
告警服务
提供多渠道告警功能(邮件、Webhook)
"""

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
            是否发送成功
        """
        try:
            # 获取SMTP配置
            smtp_host = getattr(settings, "SMTP_HOST", None)
            smtp_port = getattr(settings, "SMTP_PORT", 587)
            smtp_user = getattr(settings, "SMTP_USER", None)
            smtp_password = getattr(settings, "SMTP_PASSWORD", None)
            # SMTP_FROM 未配置时 config 里该属性仍存在但为 None，getattr 的
            # default 不会生效 → 发件人为空。改为显式回退到 smtp_user（深审 #70）。
            smtp_from = getattr(settings, "SMTP_FROM", None) or smtp_user

            # 超时：SMTP 服务器挂起时无限阻塞（且本函数在事件循环内同步执行）。
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

            # 发送邮件
            # 深审 #69：原实现 starttls() 不带 SSL context，smtplib 会退回
            # 不校验证书链/主机名的默认上下文，随后明文发送凭据（可被 MITM）；
            # 且 SMTP 无 timeout，服务器不响应即无限阻塞。两者一并修复。
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port, timeout=smtp_timeout) as server:
                server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

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
            是否发送成功
        """
        try:
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
