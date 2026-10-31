"""
零信任安全架构 - 设备指纹识别模块

提供设备身份验证、风险评分和持续信任评估功能。
"""

import hashlib
from typing import Any, Dict, List, Optional
from datetime import timezone, datetime
from dataclasses import dataclass, asdict
from enum import Enum
import re

from app.core.logging import logger
# 注意：本模块所有方法为同步 def，必须使用同步的 SimpleCache（default_cache）。
# 不能用 async 的 cache_manager / cache 别名 —— 那会让 cache.get/set 返回协程对象，
# 导致 is_device_blocked 永远为 True、get_trust_score 返回协程而非 float，
# 并产生 "coroutine was never awaited" RuntimeWarning。
from app.core.cache import default_cache


class DeviceRiskLevel(str, Enum):
    """设备风险等级"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DeviceFingerprint:
    """设备指纹数据结构"""

    fingerprint_id: str
    user_agent: str
    ip_address: str
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    platform: Optional[str] = None
    fonts: Optional[List[str]] = None
    canvas_hash: Optional[str] = None
    webgl_hash: Optional[str] = None
    plugins: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    trust_score: float = 0.5
    risk_level: DeviceRiskLevel = DeviceRiskLevel.MEDIUM
    is_blocked: bool = False
    block_reason: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.last_seen is None:
            self.last_seen = datetime.now(timezone.utc)

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        data["risk_level"] = self.risk_level.value
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["last_seen"] = self.last_seen.isoformat() if self.last_seen else None
        return data


class DeviceFingerprintService:
    """设备指纹服务"""

    CACHE_PREFIX = "device_fp:"
    BLOCKLIST_PREFIX = "device_block:"
    TRUST_CACHE_PREFIX = "trust_score:"

    def __init__(self):
        self._suspicious_patterns = self._load_suspicious_patterns()

    def _load_suspicious_patterns(self) -> Dict:
        """加载可疑模式配置"""
        return {
            "automation_tools": [
                "selenium",
                "webdriver",
                "phantomjs",
                "headless",
                "puppeteer",
                "playwright",
                "cypress",
            ],
            "suspicious_ua_patterns": [
                r"(?i)^$",  # 空 User-Agent
                r"(?i)(bot|crawler|spider|scraper)",
                r"(?i)(sqlmap|nikto|nmap|burp)",
            ],
            "trusted_platforms": ["Win32", "MacIntel", "Linux x86_64", "iPhone", "iPad", "Android"],
        }

    def generate_fingerprint(self, user_agent: str, ip_address: str, **kwargs) -> str:
        """
        生成设备指纹 ID

        基于多种设备特征生成唯一标识
        """
        # 基础特征
        components = [
            user_agent,
            ip_address,
            kwargs.get("screen_resolution", ""),
            kwargs.get("platform", ""),
            kwargs.get("language", ""),
        ]

        # 高级特征
        if kwargs.get("canvas_hash"):
            components.append(kwargs["canvas_hash"])
        if kwargs.get("webgl_hash"):
            components.append(kwargs["webgl_hash"])

        # 生成哈希
        fingerprint_string = "|".join(components)
        fingerprint_id = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]

        return fingerprint_id

    def create_device_record(
        self, fingerprint_id: str, user_agent: str, ip_address: str, **kwargs
    ) -> DeviceFingerprint:
        """创建设备记录"""
        device = DeviceFingerprint(
            fingerprint_id=fingerprint_id,
            user_agent=user_agent,
            ip_address=ip_address,
            screen_resolution=kwargs.get("screen_resolution"),
            timezone=kwargs.get("timezone"),
            language=kwargs.get("language"),
            platform=kwargs.get("platform"),
            fonts=kwargs.get("fonts"),
            canvas_hash=kwargs.get("canvas_hash"),
            webgl_hash=kwargs.get("webgl_hash"),
            plugins=kwargs.get("plugins"),
        )

        # 计算初始信任评分
        device.trust_score = self._calculate_trust_score(device)
        device.risk_level = self._determine_risk_level(device.trust_score)

        # 保存到缓存
        self._save_device(device)

        logger.info(f"创建设备指纹: {fingerprint_id}, 信任评分: {device.trust_score}")

        return device

    def _calculate_trust_score(self, device: DeviceFingerprint) -> float:
        """
        计算设备信任评分

        评分范围: 0.0 - 1.0
        越高表示越可信
        """
        score = 0.5  # 基础分

        # User-Agent 分析
        ua = device.user_agent.lower()

        # 检查自动化工具
        for tool in self._suspicious_patterns["automation_tools"]:
            if tool.lower() in ua:
                score -= 0.3
                break

        # 检查可疑模式
        for pattern in self._suspicious_patterns["suspicious_ua_patterns"]:
            if re.search(pattern, device.user_agent):
                score -= 0.2
                break

        # 平台可信度
        if device.platform:
            if device.platform in self._suspicious_patterns["trusted_platforms"]:
                score += 0.1

        # 特征完整性加分
        if device.canvas_hash and device.webgl_hash:
            score += 0.1
        if device.fonts and len(device.fonts) > 5:
            score += 0.05

        # 确保分数在合理范围
        return max(0.0, min(1.0, score))

    def _determine_risk_level(self, trust_score: float) -> DeviceRiskLevel:
        """根据信任评分确定风险等级"""
        if trust_score >= 0.8:
            return DeviceRiskLevel.LOW
        elif trust_score >= 0.5:
            return DeviceRiskLevel.MEDIUM
        elif trust_score >= 0.3:
            return DeviceRiskLevel.HIGH
        else:
            return DeviceRiskLevel.CRITICAL

    def _save_device(self, device: DeviceFingerprint):
        """保存设备信息到缓存"""
        cache_key = f"{self.CACHE_PREFIX}{device.fingerprint_id}"
        default_cache.set(cache_key, device.to_dict(), ttl=86400 * 30)  # 30天

    def get_device(self, fingerprint_id: str) -> Optional[DeviceFingerprint]:
        """获取设备信息"""
        cache_key = f"{self.CACHE_PREFIX}{fingerprint_id}"
        data = default_cache.get(cache_key)

        if not data:
            return None

        # 从字典重建对象
        return DeviceFingerprint(
            fingerprint_id=data["fingerprint_id"],
            user_agent=data["user_agent"],
            ip_address=data["ip_address"],
            screen_resolution=data.get("screen_resolution"),
            timezone=data.get("timezone"),
            language=data.get("language"),
            platform=data.get("platform"),
            fonts=data.get("fonts"),
            canvas_hash=data.get("canvas_hash"),
            webgl_hash=data.get("webgl_hash"),
            plugins=data.get("plugins"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            last_seen=datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else None,
            trust_score=data.get("trust_score", 0.5),
            risk_level=DeviceRiskLevel(data.get("risk_level", "medium")),
            is_blocked=data.get("is_blocked", False),
            block_reason=data.get("block_reason"),
        )

    def update_trust_score(self, fingerprint_id: str, action: str, success: bool) -> float:
        """
        根据用户行为更新信任评分

        Args:
            fingerprint_id: 设备指纹ID
            action: 操作类型
            success: 是否成功

        Returns:
            新的信任评分
        """
        device = self.get_device(fingerprint_id)
        if not device:
            return 0.5

        # 根据行为调整评分
        if action == "login":
            if success:
                device.trust_score = min(1.0, device.trust_score + 0.05)
            else:
                device.trust_score = max(0.0, device.trust_score - 0.1)

        elif action == "mfa_verified":
            device.trust_score = min(1.0, device.trust_score + 0.1)

        elif action == "suspicious_activity":
            device.trust_score = max(0.0, device.trust_score - 0.15)

        elif action == "data_export":
            # 数据导出需要更严格的评估
            if not success:
                device.trust_score = max(0.0, device.trust_score - 0.2)

        # 更新风险等级
        device.risk_level = self._determine_risk_level(device.trust_score)
        device.last_seen = datetime.now(timezone.utc)

        # 保存更新
        self._save_device(device)

        # 缓存信任评分（用于快速查询）
        trust_key = f"{self.TRUST_CACHE_PREFIX}{fingerprint_id}"
        default_cache.set(trust_key, device.trust_score, ttl=3600)

        return device.trust_score

    def block_device(self, fingerprint_id: str, reason: str):
        """封禁设备"""
        device = self.get_device(fingerprint_id)
        if device:
            device.is_blocked = True
            device.block_reason = reason
            device.trust_score = 0.0
            device.risk_level = DeviceRiskLevel.CRITICAL
            self._save_device(device)

        # 添加到封禁列表
        block_key = f"{self.BLOCKLIST_PREFIX}{fingerprint_id}"
        block_record = {
            "reason": reason,
            "blocked_at": datetime.now(timezone.utc).isoformat(),
        }
        default_cache.set(block_key, block_record, ttl=86400 * 7)

        logger.warning(f"设备被封禁: {fingerprint_id}, 原因: {reason}")

    def is_device_blocked(self, fingerprint_id: str) -> bool:
        """检查设备是否被封禁"""
        block_key = f"{self.BLOCKLIST_PREFIX}{fingerprint_id}"
        return default_cache.get(block_key) is not None

    def get_trust_score(self, fingerprint_id: str) -> float:
        """获取设备信任评分（带缓存）"""
        # 先查缓存
        trust_key = f"{self.TRUST_CACHE_PREFIX}{fingerprint_id}"
        cached_score = default_cache.get(trust_key)
        if cached_score is not None:
            return cached_score

        # 查数据库
        device = self.get_device(fingerprint_id)
        if device:
            default_cache.set(trust_key, device.trust_score, ttl=3600)
            return device.trust_score

        return 0.5  # 默认中等信任

    def verify_device(
        self, fingerprint_id: str, user_id: str, required_trust_level: DeviceRiskLevel = DeviceRiskLevel.MEDIUM
    ) -> Dict:
        """
        验证设备是否可信

        Returns:
            验证结果字典
        """
        result: Dict[str, Any] = {
            "verified": False,
            "requires_mfa": False,
            "requires_challenge": False,
            "block_access": False,
            "reason": None,
            "trust_score": 0.0,
            "risk_level": DeviceRiskLevel.CRITICAL,
        }

        # 检查封禁状态
        if self.is_device_blocked(fingerprint_id):
            result["block_access"] = True
            result["reason"] = "设备已被封禁"
            return result

        # 获取设备信息
        device = self.get_device(fingerprint_id)
        if not device:
            # 新设备，需要额外验证
            result["requires_mfa"] = True
            result["reason"] = "新设备登录"
            return result

        # 更新最后访问时间
        device.last_seen = datetime.now(timezone.utc)
        self._save_device(device)

        result["trust_score"] = device.trust_score
        result["risk_level"] = device.risk_level

        # 风险等级检查
        if device.risk_level == DeviceRiskLevel.CRITICAL:
            result["block_access"] = True
            result["reason"] = "设备风险等级过高"
            return result

        if device.risk_level == DeviceRiskLevel.HIGH:
            result["requires_challenge"] = True
            result["reason"] = "设备风险较高，需要额外验证"
            return result

        # 信任评分检查
        if device.trust_score < 0.3:
            result["requires_mfa"] = True
            result["reason"] = "设备信任评分不足"
            return result

        # 位置异常检测（简化版）
        # 实际生产环境应使用更复杂的地理分析

        result["verified"] = True
        return result


# 全局服务实例
device_fingerprint_service = DeviceFingerprintService()
