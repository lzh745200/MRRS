# -*- coding: utf-8 -*-
"""
机器码和校验码服务
用于单机版系统的用户认证和注册管理
"""

import hashlib
import hmac
import logging
import platform
import secrets
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.machine_code import MachineCode
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

# 通行码 HMAC 密钥：用于跨机器自验证（管理员在 A 机为 B 机生成通行码，
# B 机注册时无需共享数据库，仅凭 HMAC(machine_code) 即可独立验证）。
# 安全基线（W1-T6 / ADR-0004）：内置默认值仅保证历史行为可计算，
# 但自验证路径在未显式配置密钥时一律拒绝（fail-closed）——
# 否则拿到源码者可离线伪造合法通行码绕过整个授权体系。
# 密钥来源 settings.PASS_CODE_SECRET：pydantic 合并真实环境变量与 .env，
# 打包模式 Electron 注入的环境变量同样被读取（此前直读 os.environ，.env 配置无效）。
# 注：模块属性名保持不变——W1-T6 回归测试直接 monkeypatch 这两个属性。
_PASS_CODE_SECRET_EXPLICIT = bool(settings.PASS_CODE_SECRET)
_PASS_CODE_SECRET = (settings.PASS_CODE_SECRET or "bumofu-assistance-passcode-v1").encode("utf-8")


class MachineCodeService:
    """机器码服务

    提供机器码生成、管理和验证功能。
    """

    def __init__(self, db: Optional[Session] = None):
        """初始化机器码服务

        Args:
            db: 数据库会话（可选，用于数据库操作）
        """
        self.db = db

    # 进程级缓存：机器码在进程生命周期内不变，首次计算后缓存
    _cached_machine_code: Optional[str] = None

    @staticmethod
    def _collect_wmic_info() -> list:
        if platform.system() != "Windows":  # pragma: no cover
            return []

        wmic_queries = [
            (["wmic", "cpu", "get", "ProcessorId"], None),
            (["wmic", "baseboard", "get", "SerialNumber"], "To be filled by O.E.M."),
            (["wmic", "diskdrive", "get", "SerialNumber"], None),
        ]
        procs = []
        for cmd, _ in wmic_queries:
            try:
                procs.append(
                    (
                        subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            text=True,
                            encoding="utf-8",
                            errors="ignore",
                            creationflags=0x08000000,
                        ),
                        _,
                    )
                )
            except Exception:  # pragma: no cover
                procs.append((None, _))

        info = []
        for proc, skip_val in procs:
            if proc is None:  # pragma: no cover
                continue
            try:
                stdout, _ = proc.communicate(timeout=2)
                val = stdout.strip().split("\n")[-1].strip()
                if val and val != skip_val:
                    info.append(val)
            except Exception:  # pragma: no cover
                try:
                    proc.kill()
                except Exception:
                    logger.debug("终止机器信息采集进程失败")
        return info

    @staticmethod
    def _get_mac_address() -> Optional[str]:
        try:
            return ":".join(
                ["{:02x}".format((uuid.getnode() >> elements) & 0xFF) for elements in range(0, 2 * 6, 2)][::-1]
            )
        except Exception:  # pragma: no cover
            logger.debug("获取 MAC 地址失败")
            return None

    @staticmethod
    def _get_computer_name() -> Optional[str]:
        try:
            name = platform.node()
            return name if name else None
        except Exception:  # pragma: no cover
            logger.debug("获取计算机名失败")
            return None

    @staticmethod
    def get_machine_code() -> str:
        """
        获取当前机器的唯一标识码

        结果被进程级缓存，首次调用后后续调用直接返回，无需重复执行
        wmic 子进程（每次登录可节省数秒）。

        Returns:
            机器码（32位十六进制字符串）
        """
        if MachineCodeService._cached_machine_code is not None:
            return MachineCodeService._cached_machine_code

        machine_info = []
        machine_info.extend(MachineCodeService._collect_wmic_info())

        mac = MachineCodeService._get_mac_address()
        if mac:
            machine_info.append(mac)

        computer_name = MachineCodeService._get_computer_name()
        if computer_name:
            machine_info.append(computer_name)

        if not machine_info:
            machine_info.append(str(uuid.uuid4()))

        combined = "|".join(machine_info)
        machine_code = hashlib.sha256(combined.encode()).hexdigest()
        MachineCodeService._cached_machine_code = machine_code

        return machine_code

    @staticmethod
    def generate_verification_code(machine_code: str) -> str:
        """
        根据机器码生成4位数字校验码

        Args:
            machine_code: 机器码

        Returns:
            4位数字校验码
        """
        # 使用机器码的哈希值生成4位数字
        hash_value = hashlib.md5(machine_code.encode(), usedforsecurity=False).hexdigest()

        # 取哈希值的前8位，转换为整数
        num = int(hash_value[:8], 16)

        # 取模得到4位数字（1000-9999）
        verification_code = (num % 9000) + 1000

        return str(verification_code)

    @staticmethod
    def verify_machine_code(machine_code: str, verification_code: str) -> bool:
        """
        验证机器码和校验码是否匹配

        Args:
            machine_code: 机器码
            verification_code: 校验码

        Returns:
            是否匹配
        """
        expected_code = MachineCodeService.generate_verification_code(machine_code)
        return expected_code == verification_code

    @staticmethod
    def generate_initial_password(username: str, verification_code: str) -> str:
        """
        生成初始登录密码

        规则：用户名前4位 + 校验码 + 固定后缀
        例如：admin + 1234 + @RRS

        Args:
            username: 用户名
            verification_code: 校验码

        Returns:
            初始密码
        """
        # 取用户名前4位（不足4位则全取）
        username_prefix = username[:4].upper()

        # 组合密码
        password = f"{username_prefix}{verification_code}@RRS"

        return password

    @staticmethod
    def get_machine_info() -> dict:
        """
        获取机器详细信息（用于显示）

        Returns:
            机器信息字典
        """
        info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "node": platform.node(),
        }

        # Windows 特定信息
        if platform.system() == "Windows":
            try:
                # CPU 信息
                result = subprocess.run(
                    ["wmic", "cpu", "get", "Name"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=5,
                )
                cpu_name = result.stdout.strip().split("\n")[-1].strip()
                info["cpu_name"] = cpu_name
            except Exception:  # pragma: no cover
                logger.debug("获取 CPU 信息失败")

            try:
                # 内存信息
                result = subprocess.run(
                    ["wmic", "computersystem", "get", "TotalPhysicalMemory"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=5,
                )
                memory = result.stdout.strip().split("\n")[-1].strip()
                if memory:
                    memory_gb = int(memory) / (1024**3)
                    info["memory_gb"] = round(memory_gb, 2)
            except Exception:  # pragma: no cover
                logger.debug("获取内存信息失败")

        return info

    @staticmethod
    def generate_pass_code(machine_code: str) -> str:
        """为指定机器码生成通行码（激活码）

        通行码 = HMAC-SHA256(PASS_CODE_SECRET, machine_code) 截断 32 位，
        格式化为 XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX。

        **确定性设计（跨机器自验证）**：
        任意机器只要知道目标机器码和共享密钥，就能独立重算并验证该通行码，
        无需访问生成机器的数据库。这使"管理员在 A 机为 B 机生成通行码、
        用户在 B 机注册"成为可能——B 机注册时用自身机器码重算 HMAC 即可验证。

        Args:
            machine_code: 目标机器的机器码

        Returns:
            str: 通行码（格式化为 XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX）
        """
        digest = hmac.new(
            _PASS_CODE_SECRET,
            (machine_code or "").encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:32]

        # 格式化为易读格式：XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
        formatted = "-".join([digest[i: i + 4] for i in range(0, 32, 4)])

        return formatted

    @staticmethod
    def verify_pass_code_hmac(pass_code: str, machine_code: str) -> bool:
        """独立验证通行码是否匹配指定机器码（HMAC 自验证，不依赖数据库）

        用于跨机器场景：通行码在系统 A 生成（绑定系统 B 的机器码），
        用户在系统 B 注册时，仅凭自身机器码重算 HMAC 即可验证通行码真伪。

        Args:
            pass_code: 用户输入的通行码（允许带/不带连字符）
            machine_code: 当前机器的机器码

        Returns:
            bool: 是否匹配
        """
        # W1-T6 fail-closed：密钥为源码内置默认值时拒绝自验证——
        # 该默认值随安装包分发，不构成秘密；继续放行等于允许离线伪造授权。
        if not _PASS_CODE_SECRET_EXPLICIT:
            logger.warning(
                "通行码 HMAC 自验证被拒绝：未显式配置 PASS_CODE_SECRET "
                "（fail-closed，见 ADR-0004）。请由管理员预录入通行码。"
            )
            return False
        expected = MachineCodeService.generate_pass_code(machine_code)
        # 兼容用户去掉连字符的输入
        normalized_input = (pass_code or "").strip().replace("-", "").lower()
        normalized_expected = expected.replace("-", "").lower()
        # 常量时间比较，避免时序侧信道
        return hmac.compare_digest(normalized_input, normalized_expected)

    def create_machine_code_record(
        self,
        machine_code: str,
        created_by: int,
        description: Optional[str] = None,
        pass_code: Optional[str] = None,
    ) -> MachineCode:
        """管理员录入机器码并生成通行码

        如果该机器码已有记录（pending/active/revoked），复用同一记录——
        生成新通行码、重置为 pending、清除旧的用户绑定。
        这允许管理员为同一台机器多次生成通行码，解决了“通行码已过期”问题。

        Args:
            machine_code: 用户提供的机器码
            created_by: 创建人ID（管理员）
            description: 备注说明
            pass_code: 手动设置的4位数字通行码（留空则自动生成32位通行码）

        Returns:
            MachineCode: 创建或重置后的机器码记录

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        # 生成新通行码
        final_pass_code = pass_code if pass_code else self.generate_pass_code(machine_code)

        # 检查机器码是否已有记录（unique 约束：同一 machine_code 只有一条记录）
        existing = self.db.query(MachineCode).filter(MachineCode.machine_code == machine_code).first()

        if existing:
            # 复用已有记录：重置通行码和状态，清除旧的用户绑定
            old_status = existing.status
            old_user_id = existing.user_id

            existing.pass_code = final_pass_code
            existing.status = "pending"
            existing.user_id = None
            existing.activated_at = None
            existing.revoked_at = None
            existing.created_by = created_by
            existing.description = description or existing.description

            try:
                safe_commit(self.db)
            except IntegrityError as e:
                # 手动指定的通行码与另一条记录冲突（pass_code UNIQUE）：
                # 历史缺陷 → 冒泡为未处理 500。改抛业务 ValueError（API 层转 400），
                # 让管理员看到可操作的提示而非“服务器错误”。safe_commit 已回滚会话。
                raise ValueError("该通行码已被其他机器码记录占用，请更换一个通行码") from e
            self.db.refresh(existing)

            logger.info(
                "管理员重新生成通行码: machine_code=%s..., "
                "old_status=%s, old_user_id=%s, "
                "new_pass_code=%s..., created_by=%s",
                machine_code[:16],
                old_status,
                old_user_id,
                final_pass_code[:16] if final_pass_code else "None",
                created_by,
            )

            return existing

        # 机器码不存在，创建新记录
        record = MachineCode(
            machine_code=machine_code,
            pass_code=final_pass_code,
            status="pending",
            created_by=created_by,
            description=description,
        )

        self.db.add(record)
        try:
            safe_commit(self.db)
        except IntegrityError as e:
            # 机器码此处必不冲突（existing 为 None 才走本分支），冲突只可能来自
            # 手动指定的 pass_code 与另一条记录重复（pass_code UNIQUE）→ 转业务 400。
            raise ValueError("该通行码已被其他机器码记录占用，请更换一个通行码") from e
        self.db.refresh(record)

        logger.info(
            "管理员创建机器码记录: machine_code=%s..., "
            "pass_code=%s..., created_by=%s",
            machine_code[:16],
            final_pass_code[:16] if final_pass_code else "None",
            created_by,
        )

        return record

    def verify_pass_code(self, pass_code: str, machine_code: str) -> Optional[MachineCode]:
        """验证通行码是否有效

        匹配优先级：
        1. 机器特定通行码：pass_code + machine_code + status=pending
        2. 组织通行码：pass_code + organization_id 非空 + status=pending（不绑定特定机器）
        3. 仅凭 pass_code 回退（wmic 漂移，自动改绑并留痕）
        4. HMAC 自验证（跨机器场景，未配置 PASS_CODE_SECRET 时 fail-closed）
        兼容激活中断的边界场景：active 但 user_id 为空。

        输入归一化：先按原文精确匹配（快路径），失败后对存储值与输入同时
        去除连字符再重试四级匹配——用户手工抄写 32 位格式化通行码时极易
        漏连字符，此前直接报"通行码无效"造成注册受阻。
        大小写归一化：通行码为小写十六进制（自动生成）或纯数字（手动 4 位），
        大写输入（图片 OCR、手动录入习惯、第三方工具转写）属于同一通行码，
        输入统一转小写后再匹配（对存储值同样做小写归一比较）。

        Args:
            pass_code: 用户输入的通行码
            machine_code: 当前机器的机器码

        Returns:
            Optional[MachineCode]: 验证通过返回记录，否则返回None

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        # 去除首尾空白 + 转小写（防止复制粘贴带入空格/大小写不一致导致匹配失败）
        pass_code = (pass_code or "").strip().lower()

        # 快路径：原文精确匹配
        record = self._verify_pass_code_impl(pass_code, machine_code, normalize=False)
        if record:
            return record

        # 归一化回退：对存储值与输入同步去连字符后重试四级匹配。
        # 覆盖两个方向：输入多打了连字符（normalized != 原文）、
        # 用户全省略连字符而存储值带连字符（normalized == 原文但存储不同）。
        normalized = pass_code.replace("-", "")
        if normalized:
            return self._verify_pass_code_impl(normalized, machine_code, normalize=True)

        logger.warning(
            "通行码验证失败: pass_code=%s..., machine_code=%s...",
            pass_code[:16],
            machine_code[:16],
        )
        return None

    def _verify_pass_code_impl(
        self, pass_code: str, machine_code: str, normalize: bool
    ) -> Optional[MachineCode]:
        """四级验证实现。normalize=True 时对库内 pass_code 去连字符后比对。

        大小写：pass_code 入参已在 verify_pass_code 转小写；此处对库内列
        统一 func.lower 后比较（hex 通行码不区分大小写，接受用户大写输入）。
        """
        from sqlalchemy import or_, func as sa_func

        stored_raw = MachineCode.pass_code
        if normalize:
            stored_raw = sa_func.replace(stored_raw, "-", "")
        stored_pc = sa_func.lower(stored_raw)
        status_ok = or_(
            MachineCode.status == "pending",
            and_(MachineCode.status == "active", MachineCode.user_id.is_(None)),
        )

        # 1. 优先匹配机器特定通行码
        record = (
            self.db.query(MachineCode)
            .filter(
                and_(
                    stored_pc == pass_code,
                    MachineCode.machine_code == machine_code,
                    status_ok,
                )
            )
            .first()
        )

        if record:
            # 重置 active(未绑定) 为 pending
            if record.status == "active" and record.user_id is None:
                record.status = "pending"
                safe_commit(self.db)
            logger.info("机器通行码验证成功: pass_code=%s...", pass_code[:16])
            return record

        # 2. 回退：匹配组织通行码（不绑定特定机器码）
        record = (
            self.db.query(MachineCode)
            .filter(
                and_(
                    stored_pc == pass_code,
                    MachineCode.organization_id.isnot(None),
                    status_ok,
                )
            )
            .first()
        )

        if record:
            if record.status == "active" and record.user_id is None:
                record.status = "pending"
                safe_commit(self.db)
            logger.info("组织通行码验证成功: pass_code=%s...", pass_code[:16])
            return record

        # 3. 最终回退：仅凭 pass_code 匹配（不要求 machine_code 一致）
        #    处理场景：wmic 输出不稳定 / 进程重启后机器码重新计算导致不一致
        #    安全性：限 status=pending 且 organization_id 为空（机器通行码）
        record = (
            self.db.query(MachineCode)
            .filter(
                and_(
                    stored_pc == pass_code,
                    MachineCode.organization_id.is_(None),
                    MachineCode.status == "pending",
                )
            )
            .first()
        )

        if record:
            # 自动更新机器码绑定到当前机器，后续登录走第一优先级
            old_machine_code = record.machine_code[:16] if record.machine_code else "None"
            record.machine_code = machine_code
            try:
                safe_commit(self.db)
            except IntegrityError:
                # 目标机器码已被另一条记录占用（machine_code UNIQUE 冲突）。
                # 历史缺陷：未捕获 → 冒泡为未处理 500，注册页只显示“服务器错误”。
                # 现回滚改绑并按验证失败处理（调用方得到干净的 400，可提示联系管理员）。
                # 改绑未发生，故不写改绑审计。
                self.db.rollback()
                logger.warning(
                    "通行码回退改绑失败：机器码 %s... 已被其他记录占用，放弃改绑（返回验证失败）",
                    machine_code[:16],
                )
                return None
            # W1-T6：静默改绑属敏感操作，必须留痕可追溯
            try:
                from app.services.work_log_service import write_work_log

                write_work_log(
                    self.db, "machine_code", "passcode_fallback_rebind",
                    getattr(record, "id", None),
                    f"通行码回退验证改绑机器码: {old_machine_code}... -> {machine_code[:16]}...",
                )
            except Exception:  # pragma: no cover
                logger.debug("记录通行码回退改绑审计失败", exc_info=True)
            logger.info(
                "通行码回退验证成功（机器码已更新）: pass_code=%s..., "
                "old_machine_code=%s..., new_machine_code=%s...",
                pass_code[:16],
                old_machine_code,
                machine_code[:16],
            )
            return record

        # 4. HMAC 自验证（跨机器场景）：仅在原文（非归一化）路径尝试，
        #    HMAC 验证内部已自行做去连字符归一化。
        if not normalize and MachineCodeService.verify_pass_code_hmac(pass_code, machine_code):
            try:
                record = MachineCode(
                    machine_code=machine_code,
                    pass_code=machine_code[:32],  # 占位：本机记录不以 HMAC 全文存储
                    status="pending",
                    created_by=None,
                    description="跨机器通行码验证（HMAC 自验证）",
                )
                self.db.add(record)
                safe_commit(self.db)
                self.db.refresh(record)
                logger.info(
                    "通行码 HMAC 自验证成功（跨机器）: machine_code=%s..., "
                    "已在本机创建绑定记录 id=%s",
                    machine_code[:16],
                    record.id,
                )
                return record
            except Exception as e:  # pragma: no cover
                logger.warning("HMAC 自验证后创建本地记录失败: %s", e)
                return MachineCode(
                    machine_code=machine_code,
                    pass_code=machine_code[:32],
                    status="pending",
                    created_by=None,
                )

        return None

    def activate_machine_code(self, record: MachineCode, user_id: int) -> None:
        """激活机器码（绑定到用户）

        Args:
            record: 机器码记录
            user_id: 用户ID

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        record.status = "active"
        record.user_id = user_id
        record.activated_at = datetime.now(timezone.utc)

        safe_commit(self.db)

        logger.info(f"机器码已激活: machine_code={record.machine_code[:16]}..., " f"user_id={user_id}")

    def revoke_machine_code(self, machine_code_id: int) -> bool:
        """撤销机器码

        Args:
            machine_code_id: 机器码记录ID

        Returns:
            bool: 是否成功撤销

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        record = self.db.query(MachineCode).filter(MachineCode.id == machine_code_id).first()
        if not record:
            return False

        record.status = "revoked"
        record.revoked_at = datetime.now(timezone.utc)

        safe_commit(self.db)

        logger.info(f"机器码已撤销: id={machine_code_id}, machine_code={record.machine_code[:16]}...")
        return True

    def get_machine_code_by_user(self, user_id: int) -> Optional[MachineCode]:
        """获取用户绑定的机器码

        Args:
            user_id: 用户ID

        Returns:
            Optional[MachineCode]: 机器码记录

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        return (
            self.db.query(MachineCode)
            .filter(
                and_(
                    MachineCode.user_id == user_id,
                    MachineCode.status == "active",
                )
            )
            .first()
        )

    def verify_user_machine(self, user_id: int, current_machine_code: str) -> bool:
        """验证用户是否在授权的机器上登录

        Args:
            user_id: 用户ID
            current_machine_code: 当前机器的机器码

        Returns:
            bool: 是否授权

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        record = self.get_machine_code_by_user(user_id)
        if not record:
            # 用户未绑定机器码，允许登录（兼容旧用户）
            logger.info(f"用户未绑定机器码，允许登录: user_id={user_id}")
            return True

        is_authorized = record.machine_code == current_machine_code
        if not is_authorized:
            logger.warning(
                f"用户尝试在未授权的机器上登录: user_id={user_id}, "
                f"expected={record.machine_code[:16]}..., "
                f"actual={current_machine_code[:16]}..."
            )

        return is_authorized

    def list_machine_codes(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[MachineCode], int]:
        """查询机器码列表

        Args:
            status: 状态筛选（pending/active/revoked）
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            tuple[list[MachineCode], int]: (机器码列表, 总数)

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        query = self.db.query(MachineCode)

        if status:
            query = query.filter(MachineCode.status == status)

        total = query.count()

        # 使用 joinedload 预加载用户关系，避免 N+1 查询
        from sqlalchemy.orm import joinedload

        records = (
            query.options(joinedload(MachineCode.user))
            .order_by(MachineCode.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return records, total

    # ==================== 组织通行证码相关方法 ====================

    @staticmethod
    def generate_organization_verification_code(organization_id: int, organization_name: str) -> str:
        """基于组织信息生成4位校验码（确定性）

        同一组织每次生成相同的校验码，便于验证和管理。

        Args:
            organization_id: 组织ID
            organization_name: 组织名称

        Returns:
            str: 4位数字校验码
        """
        # 组合组织ID和名称
        combined = f"{organization_id}:{organization_name}"

        # 使用 MD5 哈希
        hash_value = hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()

        # 取哈希值的前8位，转换为整数
        num = int(hash_value[:8], 16)

        # 取模得到4位数字（1000-9999）
        verification_code = (num % 9000) + 1000

        return str(verification_code)

    @staticmethod
    def generate_organization_pass_code(organization_id: int, verification_code: str) -> str:
        """生成12位组织通行码

        格式：XXXX-XXXX-XXXX（带连字符显示）

        Args:
            organization_id: 组织ID
            verification_code: 校验码

        Returns:
            str: 12位通行码（格式化为 XXXX-XXXX-XXXX）
        """
        # 生成随机盐
        salt = secrets.token_hex(8)

        # 组合组织ID、校验码和盐生成通行码
        combined = f"{organization_id}:{verification_code}:{salt}"

        # 使用 SHA256 哈希
        hash_value = hashlib.sha256(combined.encode()).hexdigest()

        # 取前12位字符（大写字母和数字）
        pass_code = hash_value[:12].upper()

        # 格式化为 XXXX-XXXX-XXXX
        formatted = f"{pass_code[:4]}-{pass_code[4:8]}-{pass_code[8:12]}"

        return formatted

    def create_organization_pass_code(
        self,
        organization_id: int,
        verification_code: str,
        allow_subordinate: bool,
        created_by: int,
        description: Optional[str] = None,
    ) -> MachineCode:
        """管理员输入校验码+选择组织→生成通行码

        管理员在下级单位提供机器校验码后，选择对应组织并输入校验码，
        系统生成通行码。通行码关联到组织，不绑定特定机器。

        Args:
            organization_id: 管理员选择的下级组织ID
            verification_code: 下级单位提供的机器校验码
            allow_subordinate: 是否允许下级组织生成通行码
            created_by: 创建人ID（管理员）
            description: 备注说明

        Returns:
            MachineCode: 包含通行码的记录

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        # 生成通行码（随机，不绑定特定机器码）
        pass_code = self.generate_pass_code(secrets.token_hex(16))

        # 生成唯一标识符
        machine_code = f"ORG-{organization_id}-{secrets.token_hex(8)}"

        # 创建记录
        record = MachineCode(
            machine_code=machine_code,
            pass_code=pass_code,
            status="pending",
            organization_id=organization_id,
            allow_subordinate_generation=allow_subordinate,
            description=description or f"校验码: {verification_code}",
            created_by=created_by,
        )

        self.db.add(record)
        safe_commit(self.db)
        self.db.refresh(record)

        logger.info(
            "管理员为组织生成通行码: organization_id=%s, "
            "verification_code=%s, pass_code=%s...",
            organization_id,
            verification_code,
            pass_code[:16],
        )

        return record

    def delete_organization_pass_code(self, pass_code_id: int) -> bool:
        """删除通行码记录

        管理员可删除通行码记录。已激活的记录也可删除。

        Args:
            pass_code_id: 通行码记录ID

        Returns:
            bool: 是否删除成功

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        record = self.db.query(MachineCode).filter(MachineCode.id == pass_code_id).first()
        if not record:
            return False

        self.db.delete(record)
        safe_commit(self.db)

        logger.info("通行码记录已删除: id=%s", pass_code_id)
        return True

    def get_organization_pass_codes(
        self,
        organization_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[MachineCode], int]:
        """查询组织通行码列表

        Args:
            organization_id: 组织ID筛选（可选）
            status: 状态筛选（pending/active/revoked）
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            tuple[list[MachineCode], int]: (通行码列表, 总数)

        Raises:
            ValueError: 数据库会话未初始化
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        # 查询组织通行码（organization_id 不为空）
        query = self.db.query(MachineCode).filter(MachineCode.organization_id.isnot(None))

        if organization_id:
            query = query.filter(MachineCode.organization_id == organization_id)

        if status:
            query = query.filter(MachineCode.status == status)

        total = query.count()

        # 使用 joinedload 预加载组织关系，避免 N+1 查询
        from sqlalchemy.orm import joinedload

        records = (
            query.options(joinedload(MachineCode.organization))
            .order_by(MachineCode.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return records, total


# 创建全局实例（用于静态方法调用）
machine_code_service = MachineCodeService()
