"""账号开通包业务：导出、预览、确认、回执（P1-b）。

离线场景下源机只负责生成一个受签名保护的包，目标机在本地一次性落库。
所有安全校验都在 :mod:`app.core.account_package`，本层只做权限、组织和事务。
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core import account_package_keys
from app.core.account_package import (
    build_manifest,
    generate_otp,
    inspect_package,
    open_package,
    seal_package,
)
from app.core.account_package_authz import (
    AccountPackageAuthorizationError,
    authorization_summary,
    validate_manifest_grants,
    validate_menu_selection,
)
from app.core.config import settings
from app.core.constants import (
    ACCOUNT_PACKAGE_DATA_SCOPES,
    ACCOUNT_PACKAGE_ROLES,
    FACTORY_ADMIN_PASSWORD,
    FACTORY_ADMIN_USERNAME,
)
from app.core.security import PasswordPolicy, get_password_hash
from app.core.transaction import safe_commit
from app.models.account_package import AccountPackageAttempt, AccountPackageExport, AccountPackageReceipt
from app.models.organization import Organization
from app.models.org_grant import OrgGrant
from app.models.user import User
from app.services.effective_grant_service import clear_cache
from app.services.user_service import UserService
from app.utils.paths import get_runtime_uploads_path
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)


class AccountPackageBusinessError(RuntimeError):
    def __init__(self, message: str, *, code: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status
        self.public_message = message


def _normalize_machine(code: Optional[str]) -> str:
    return (code or "").strip().upper()


def _safe_name(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in item.items() if k != "credential_hash"}


def _normalize_grants(raw: Any) -> Dict[str, str]:
    """校验并推导授权矩阵；错误统一映射为稳定 AP_* 业务错误。"""
    try:
        return validate_manifest_grants(raw)
    except AccountPackageAuthorizationError as exc:
        raise AccountPackageBusinessError(str(exc), code=exc.code) from exc


def _normalize_menu_selection(raw: Any, grants: Dict[str, str]) -> Optional[List[str]]:
    try:
        return validate_menu_selection(raw, grants)
    except AccountPackageAuthorizationError as exc:
        raise AccountPackageBusinessError(str(exc), code=exc.code) from exc


def _normalize_fingerprint(value: Optional[str]) -> str:
    return re.sub(r"[^0-9A-F]", "", (value or "").upper())


def _signature_trust(raw: bytes) -> tuple[Dict[str, Any], str, bool, List[str]]:
    """读取包头签发公钥，判断它是否已在本机信任列表内。

    返回 ``(head, signer, signer_trusted, trusted_keys)``。``signer`` 为空表示
    旧版包（包头没有内嵌公钥），此时只能靠本机预置的信任公钥验签。
    """
    head = inspect_package(raw)
    signer = str(head.get("signer_public_key") or "").strip().lower()
    trusted_keys = account_package_keys.trusted_public_keys()
    if signer:
        return head, signer, signer in set(trusted_keys), trusted_keys
    return head, "", False, trusted_keys


def _assert_signer_trusted(
    signer: str, signer_trusted: bool, confirmed_fingerprint: Optional[str]
) -> None:
    """来源未受信任时必须由操作者带外核对指纹，禁止仅凭包内公钥静默信任。"""
    if not signer or signer_trusted:
        return
    expected = account_package_keys.key_fingerprint(signer)
    provided = _normalize_fingerprint(confirmed_fingerprint)
    if not provided or provided != _normalize_fingerprint(expected):
        raise AccountPackageBusinessError(
            "无法确认账号包来源：请先在目标机核对签发机指纹，再确认导入",
            code="AP_SIGNING_UNTRUSTED",
            status=403,
        )


def _persist_signer_trust(signer: str, signer_trusted: bool) -> bool:
    """把已人工核对的来源公钥持久化；失败只记录，不影响本次已完成的导入。"""
    if not signer or signer_trusted:
        return signer_trusted
    try:
        account_package_keys.add_trusted_public_key(signer)
        return True
    except account_package_keys.AccountPackageKeyError as exc:
        logger.warning("账号包来源公钥持久化失败（本次导入仍成功）: %s", exc)
        return False


def _build_export_accounts(
    db, raw_accounts: List[Dict[str, str]], grants: Dict[str, str]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """校验导出账号并生成凭据/清单项；任一账号非法即整体拒绝。"""
    seen: set[str] = set()
    credentials: List[Dict[str, Any]] = []
    items: List[Dict[str, Any]] = []
    for account in raw_accounts:
        username = str(account.get("username") or "").strip()
        if not username or username in seen:
            raise AccountPackageBusinessError("账号用户名缺失或重复", code="AP_USERNAME_TAKEN", status=409)
        seen.add(username)
        if db.query(User).filter(User.username == username).first() is not None:
            raise AccountPackageBusinessError(f"用户名已存在: {username}", code="AP_USERNAME_TAKEN", status=409)
        role = str(account.get("role") or "user")
        scope = str(account.get("data_scope") or "org")
        if role not in ACCOUNT_PACKAGE_ROLES or scope not in ACCOUNT_PACKAGE_DATA_SCOPES:
            raise AccountPackageBusinessError("账号角色或数据范围非法", code="AP_INVALID_ROLE")
        initial_password = str(account.get("initial_password") or "").strip()
        if initial_password:
            if len(initial_password) < settings.ACCOUNT_PACKAGE_MIN_PASSWORD:
                raise AccountPackageBusinessError("初始密码长度不足", code="AP_PASSWORD_WEAK")
            if not any(c.isalpha() for c in initial_password) or not any(
                c.isdigit() for c in initial_password
            ):
                raise AccountPackageBusinessError("初始密码必须同时包含字母和数字", code="AP_PASSWORD_WEAK")
            otp = initial_password
        else:
            otp = generate_otp()
        menus = _normalize_menu_selection(account.get("allowed_menus"), grants)
        credentials.append({
            "username": username,
            "one_time_password": otp,
            "generated_password": not bool(initial_password),
            "role": role,
            "data_scope": scope,
        })
        item: Dict[str, Any] = {
            "username": username,
            "full_name": str(account.get("full_name") or username),
            "credential_hash": get_password_hash(otp),
            "role": role,
            "data_scope": scope,
        }
        # 空值不写空数组：否则导入侧会把“未收窄”误判为“无可见菜单”。
        if menus:
            item["allowed_menus"] = menus
        items.append(item)
    return credentials, items


def _unrotated_factory_admins(db: Session) -> List[User]:
    """仍是出厂状态的出厂超管：从未完成首登改密。

    登录前导入的机器上，这类账号可被出厂密码直接登录并完成“强制改密”后接管，
    因此导入时必须一并换成现场设置的新密码。
    """
    return (
        db.query(User)
        .filter(
            User.username == FACTORY_ADMIN_USERNAME,
            User.is_superuser.is_(True),
            User.is_active.is_(True),
            User.must_change_password.is_(True),
        )
        .order_by(User.id)
        .all()
    )


def _resolve_factory_admin_password(
    factory_admins: List[User],
    password: Optional[str],
    required: bool,
) -> Optional[str]:
    """返回要写入的超管新密码；没有待接管的出厂超管时一律返回 None（不改动任何超管）。"""
    if not factory_admins:
        return None
    if not password:
        if required:
            raise AccountPackageBusinessError(
                "导入时必须设置本机超级管理员的新密码", code="AP_FACTORY_PASSWORD_REQUIRED"
            )
        return None
    if password == FACTORY_ADMIN_PASSWORD:
        raise AccountPackageBusinessError("不能继续使用出厂密码", code="AP_FACTORY_PASSWORD_WEAK")
    ok, reason = PasswordPolicy.validate(password, FACTORY_ADMIN_USERNAME)
    if not ok:
        raise AccountPackageBusinessError(
            f"超级管理员新密码不符合要求：{reason}", code="AP_FACTORY_PASSWORD_WEAK"
        )
    return password


def _validated_accounts(
    manifest: Dict[str, Any], grants: Dict[str, str]
) -> List[Dict[str, Any]]:
    """导入前校验账号身份/角色/范围/菜单，返回清洗后的账号列表。

    设计约束：包内不再接受 ``allowed_permissions``；菜单只能收窄到包授权页面。
    该校验在创建组织之前执行，避免“建了组织再失败”的半成品状态。
    """
    items = manifest.get("items") or []
    if not isinstance(items, list) or not items:
        raise AccountPackageBusinessError("包内没有账号", code="AP_BAD_PACKAGE")
    seen: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise AccountPackageBusinessError("包内账号格式非法", code="AP_BAD_PACKAGE")
        username = str(item.get("username") or "").strip()
        if not username or username in seen:
            raise AccountPackageBusinessError("账号用户名缺失或重复", code="AP_USERNAME_TAKEN", status=409)
        seen.add(username)
        role = str(item.get("role") or "user")
        scope = str(item.get("data_scope") or "org")
        if role not in ACCOUNT_PACKAGE_ROLES or scope not in ACCOUNT_PACKAGE_DATA_SCOPES:
            raise AccountPackageBusinessError("账号角色或数据范围非法", code="AP_INVALID_ROLE")
        cleaned.append(
            {
                "username": username,
                "full_name": str(item.get("full_name") or username),
                "credential_hash": str(item.get("credential_hash") or ""),
                "role": role,
                "data_scope": scope,
                "allowed_menus": _normalize_menu_selection(item.get("allowed_menus"), grants),
            }
        )
    return cleaned


class AccountPackageService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def package_dir() -> Path:
        path = get_runtime_uploads_path("account_packages")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def package_path(cls, package_id: str) -> Path:
        # package_id 仅允许 UUID 形态，避免路径穿越。
        try:
            uuid.UUID(str(package_id))
        except (ValueError, TypeError) as exc:
            raise AccountPackageBusinessError("非法包 ID", code="AP_BAD_PACKAGE") from exc
        return cls.package_dir() / f"account-package-{package_id}.apkg"

    # ---- P4：失败尝试台账（消费 ACCOUNT_PACKAGE_MAX_ATTEMPTS）----
    # subject_key 形如 export:<签发人id> / import:<目标机机器码>。导入维度选机器码而非
    # package_id，因为口令错误时 package_id 还在密文里读不到，机器码是唯一稳定可得的身份。

    @staticmethod
    def attempt_subject(kind: str, identity: Any) -> str:
        return f"{kind}:{str(identity or '').strip().upper()}"

    def _attempt_row(self, subject_key: str) -> Optional[AccountPackageAttempt]:
        return self.db.query(AccountPackageAttempt).filter(
            AccountPackageAttempt.subject_key == subject_key
        ).first()

    def check_attempt_allowed(self, subject_key: str, *, now: Optional[datetime] = None) -> None:
        """锁定中或重试过快则抛 429；锁过期自动清零放行。"""
        row = self._attempt_row(subject_key)
        if row is None:
            return
        moment = now or utcnow()
        if row.locked_until is not None:
            if row.locked_until > moment:
                raise AccountPackageBusinessError(
                    "账号包操作失败次数过多，已临时锁定，请稍后再试",
                    code="AP_ATTEMPTS_EXCEEDED", status=429,
                )
            row.locked_until = None
            row.fail_count = 0
            row.last_error = None
            row.last_attempt_at = None
            safe_commit(self.db)
            return
        interval = float(settings.ACCOUNT_PACKAGE_ATTEMPT_INTERVAL_SECONDS or 0)
        if interval > 0 and row.fail_count and row.last_attempt_at is not None:
            elapsed = (moment - row.last_attempt_at).total_seconds()
            if elapsed < interval:
                raise AccountPackageBusinessError(
                    "账号包操作过于频繁，请稍后再试", code="AP_RATE_LIMITED", status=429
                )

    def record_attempt_failure(
        self, subject_key: str, error_code: str, *, now: Optional[datetime] = None
    ) -> None:
        """累计一次失败；达到阈值写 locked_until。MAX_ATTEMPTS<=0 视为关闭锁定。"""
        moment = now or utcnow()
        row = self._attempt_row(subject_key)
        if row is None:
            row = AccountPackageAttempt(subject_key=subject_key, fail_count=0)
            self.db.add(row)
        row.fail_count = int(row.fail_count or 0) + 1
        row.last_error = (error_code or "")[:64]
        row.last_attempt_at = moment
        max_attempts = int(settings.ACCOUNT_PACKAGE_MAX_ATTEMPTS or 0)
        lockout_minutes = int(settings.ACCOUNT_PACKAGE_LOCKOUT_MINUTES or 0)
        if max_attempts > 0 and row.fail_count >= max_attempts:
            row.locked_until = moment + timedelta(minutes=max(lockout_minutes, 1))
        safe_commit(self.db)

    def record_attempt_success(self, subject_key: str) -> None:
        """成功即清空窗口：速率闸门只惩罚连续失败，不影响正常操作节奏。"""
        row = self._attempt_row(subject_key)
        if row is None:
            return
        row.fail_count = 0
        row.locked_until = None
        row.last_error = None
        row.last_attempt_at = None
        safe_commit(self.db)

    def export_package(
        self,
        *,
        package_id: str,
        organization_code: str,
        organization_name: str,
        parent_code: str,
        admin_username: str,
        admin_full_name: str,
        target_machine_code: str,
        grants: Dict[str, str],
        password: str,
        issued_by: User,
        valid_days: Optional[int] = None,
        accounts: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        if not settings.ACCOUNT_PACKAGE_ENABLED:
            raise AccountPackageBusinessError("账号开通包功能未启用", code="AP_DISABLED", status=403)
        try:
            private_key_hex = account_package_keys.local_private_key(create=True)
        except account_package_keys.AccountPackageKeyError as exc:
            raise AccountPackageBusinessError(
                f"本机签发密钥不可用：{exc}", code="AP_SIGNING_MISSING", status=403
            ) from exc
        if not private_key_hex:
            raise AccountPackageBusinessError("本机签发密钥不可用", code="AP_SIGNING_MISSING", status=403)
        if len(password or "") < settings.ACCOUNT_PACKAGE_MIN_PASSWORD:
            raise AccountPackageBusinessError("包口令长度不足", code="AP_PASSWORD_WEAK")
        if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
            raise AccountPackageBusinessError("包口令必须同时包含字母和数字", code="AP_PASSWORD_WEAK")
        org = self.db.query(Organization).filter(Organization.code == organization_code).first()
        if org is None:
            raise AccountPackageBusinessError("目标组织不存在", code="AP_ORG_NOT_FOUND", status=404)
        grants = _normalize_grants(grants)
        if not grants:
            raise AccountPackageBusinessError(
                "请至少勾选一个页面或功能再签发", code="AP_GRANT_EMPTY"
            )

        # P3：单包可携带多个账号；每个账号独立 128-bit OTP，明文只在本次响应返回。
        raw_accounts = accounts or [
            {
                "username": admin_username,
                "full_name": admin_full_name,
                "role": "admin",
                "data_scope": "org",
            }
        ]
        credentials, items = _build_export_accounts(self.db, raw_accounts, grants)
        manifest = build_manifest(
            package_id=package_id,
            organization_code=organization_code,
            organization_name=organization_name or org.name or organization_code,
            parent_code=parent_code,
            target_machine_code=_normalize_machine(target_machine_code),
            valid_days=valid_days or settings.ACCOUNT_PACKAGE_TTL_DAYS,
            grants=grants,
            credential_valid_days=settings.ACCOUNT_PACKAGE_CREDENTIAL_VALID_DAYS,
            items=items,
        )
        raw = seal_package(
            manifest,
            password=password,
            private_key_hex=private_key_hex,
            iterations=settings.ACCOUNT_PACKAGE_KDF_ITERATIONS,
        )
        issuer_org = None
        if getattr(issued_by, "organization_id", None):
            issuer_org = self.db.query(Organization).filter(
                Organization.id == issued_by.organization_id
            ).first()
        path = self.package_path(package_id)
        path.write_bytes(raw)
        head = inspect_package(raw)
        record = AccountPackageExport(
            package_id=package_id,
            format_version=1,
            issuer_org_code=getattr(issuer_org, "code", None) or "",
            issuer_user_id=getattr(issued_by, "id", None),
            target_org_code=organization_code,
            binding_mode="machine",
            target_machine_code=_normalize_machine(target_machine_code),
            kdf_iterations=settings.ACCOUNT_PACKAGE_KDF_ITERATIONS,
            payload_sha256=head["manifest_sha256"],
            expires_at=datetime.fromisoformat(manifest["expires_at"]),
            state="active",
            meta={"item_count": len(items), "grant_count": len(grants), "package_password_set": True},
        )
        self.db.add(record)
        safe_commit(self.db)
        return {
            "package_id": package_id,
            "file_name": path.name,
            "expires_at": manifest["expires_at"],
            # 兼容单账号调用方；多账号以 accounts 为准（OTP 只出现这一次）。
            "one_time_password": credentials[0]["one_time_password"],
            "admin_username": credentials[0]["username"],
            "accounts": credentials,
            "authorization": authorization_summary(grants),
            "download_path": f"/api/v1/account-packages/{package_id}/download",
            "signer_public_key": head.get("signer_public_key") or "",
            "signer_fingerprint": account_package_keys.key_fingerprint(
                str(head.get("signer_public_key") or "")
            ) if head.get("signer_public_key") else "",
        }

    def preview(self, raw: bytes, *, password: str, machine_code: str) -> Dict[str, Any]:
        _head, signer, signer_trusted, trusted_keys = _signature_trust(raw)
        candidates = ([signer] if signer else []) + trusted_keys
        manifest = open_package(
            raw,
            password=password,
            public_key_hex=candidates or None,
        )
        if not signer:
            # 旧包：只有本机信任公钥能验通，open_package 已证明来源可信。
            signer_trusted = bool(trusted_keys)
        if _normalize_machine(manifest.get("target_machine_code")) != _normalize_machine(machine_code):
            raise AccountPackageBusinessError("账号包与当前机器不匹配", code="AP_MACHINE_MISMATCH", status=403)
        grants = _normalize_grants(manifest.get("grants"))
        accounts = _validated_accounts(manifest, grants)
        org = self.db.query(Organization).filter(
            Organization.code == manifest.get("organization_code")
        ).first()
        if org is None and not manifest.get("organization_name"):
            raise AccountPackageBusinessError("包内缺少组织名称", code="AP_ORG_NOT_FOUND", status=404)
        return {
            "package_id": manifest.get("package_id"),
            "organization_code": manifest.get("organization_code"),
            "organization_name": manifest.get("organization_name"),
            "parent_code": manifest.get("parent_code"),
            "expires_at": manifest.get("expires_at"),
            "admin": _safe_name(accounts[0]),
            "accounts": [_safe_name(item) for item in accounts],
            "grants": grants,
            "authorization": authorization_summary(grants),
            "factory_admin_rotation_required": bool(_unrotated_factory_admins(self.db)),
            "organization_exists": org is not None,
            "signer_public_key": signer,
            "signer_fingerprint": account_package_keys.key_fingerprint(signer) if signer else "",
            "signer_trusted": signer_trusted,
            "trust_required": bool(signer) and not signer_trusted,
        }

    def confirm(
        self,
        raw: bytes,
        *,
        password: str,
        machine_code: str,
        factory_admin_password: Optional[str] = None,
        require_factory_rotation: bool = False,
        confirmed_fingerprint: Optional[str] = None,
    ) -> Dict[str, Any]:
        _head, signer, signer_trusted, trusted_keys = _signature_trust(raw)
        _assert_signer_trusted(signer, signer_trusted, confirmed_fingerprint)
        candidates = ([signer] if signer else []) + trusted_keys
        manifest = open_package(
            raw,
            password=password,
            public_key_hex=candidates or None,
        )
        if _normalize_machine(manifest.get("target_machine_code")) != _normalize_machine(machine_code):
            raise AccountPackageBusinessError("账号包与当前机器不匹配", code="AP_MACHINE_MISMATCH", status=403)
        package_id = str(manifest.get("package_id") or "")
        if self.db.query(AccountPackageReceipt.id).filter(
            AccountPackageReceipt.package_id == package_id
        ).first() is not None:
            raise AccountPackageBusinessError("该账号包已在本机导入", code="AP_ALREADY_IMPORTED", status=409)
        grants = _normalize_grants(manifest.get("grants"))
        accounts = _validated_accounts(manifest, grants)

        # 出厂超管接管：登录前导入的机器上，仍处出厂状态的超管必须同时换掉密码，
        # 否则任何知道出厂密码的人都能登录并完成“强制改密”接管本机（已实测）。
        factory_admins = _unrotated_factory_admins(self.db)
        factory_admin_password = _resolve_factory_admin_password(
            factory_admins, factory_admin_password, require_factory_rotation
        )

        code = str(manifest.get("organization_code") or "")
        if self.db.query(Organization.id).filter(Organization.code == code).first() is not None:
            raise AccountPackageBusinessError("目标组织已存在", code="AP_ORG_CONFLICT", status=409)
        parent = None
        if manifest.get("parent_code"):
            parent = self.db.query(Organization).filter(
                Organization.code == manifest.get("parent_code")
            ).first()
            if parent is None:
                raise AccountPackageBusinessError("上级组织不存在", code="AP_ORG_NOT_FOUND", status=404)

        org = Organization(
            code=code,
            name=manifest.get("organization_name") or code,
            parent_id=getattr(parent, "id", None),
            level=str(int(getattr(parent, "level", 0) or 0) + 1) if parent else "1",
            path=None,
            is_active=True,
            sort_order=0,
            created_by=None,
        )
        self.db.add(org)
        self.db.flush()
        org.path = f"{parent.path or f'/{parent.id}/'}{org.id}/" if parent else f"/{org.id}/"

        users = []
        user_service = UserService(self.db)
        valid_days = int((manifest.get("policy") or {}).get("credential_valid_days") or 30)
        credential_expires_at = utcnow() + timedelta(days=valid_days)
        for item in accounts:
            try:
                users.append(user_service.create_user_with_password_hash(
                    item["username"],
                    item["credential_hash"],
                    role=item["role"],
                    organization_id=org.id,
                    data_scope=item["data_scope"],
                    full_name=item.get("full_name"),
                    credential_expires_at=credential_expires_at,
                    allowed_menus=item.get("allowed_menus"),
                    commit=False,
                ))
            except ValueError as exc:
                raise AccountPackageBusinessError(str(exc), code="AP_USERNAME_TAKEN", status=409) from exc

        if factory_admin_password:
            # 与建号、授权同一个事务：任何一步失败，超管密码也不变。
            for factory_admin in factory_admins:
                factory_admin.hashed_password = get_password_hash(factory_admin_password)
                factory_admin.must_change_password = False
                factory_admin.revoke_all_tokens()

        # 只有包内授权非空才激活矩阵；空 grants 绝不能把组织切到“仅授权矩阵可见”。
        for module_key, level in grants.items():
            self.db.add(OrgGrant(organization_id=org.id, module_key=module_key, level=level))
        org.grant_version = 1 if grants else 0

        receipt = AccountPackageReceipt(
            package_id=package_id,
            machine_code=_normalize_machine(machine_code),
            issuer_org_code=manifest.get("parent_code"),
            target_org_code=code,
            activated_org_id=org.id,
            activated_user_id=getattr(users[0], "id", None) if users else None,
            state="used",
        )
        self.db.add(receipt)
        try:
            self.db.commit()
        except SQLAlchemyError as exc:  # 唯一索引兜底并发 confirm
            self.db.rollback()
            raise AccountPackageBusinessError(
                "该账号包已在本机导入或写入冲突", code="AP_ALREADY_IMPORTED", status=409
            ) from exc
        clear_cache()
        # 来源信任一旦由人工核对确认，就持久化到本机信任列表：后续同一签发机的包
        # 不再要求重复核对。持久化失败不影响本次已落库的导入，下次会再次要求核对。
        signer_trusted = _persist_signer_trust(signer, signer_trusted)
        return {
            "package_id": package_id,
            "organization_id": org.id,
            "organization_code": org.code,
            "authorization": authorization_summary(grants),
            "factory_admin_rotated": bool(factory_admin_password),
            "signer_fingerprint": account_package_keys.key_fingerprint(signer) if signer else "",
            "signer_trusted": signer_trusted,
            "users": [
                {
                    "user_id": getattr(user, "id", None),
                    "username": getattr(user, "username", None),
                    "must_change_password": True,
                }
                for user in users
            ],
        }

    def list_exports(self, issuer_org_code: Optional[str], limit: int = 50) -> List[AccountPackageExport]:
        query = self.db.query(AccountPackageExport)
        if issuer_org_code:
            query = query.filter(AccountPackageExport.issuer_org_code == issuer_org_code)
        return query.order_by(AccountPackageExport.id.desc()).limit(limit).all()

    def list_receipts(self) -> List[AccountPackageReceipt]:
        return self.db.query(AccountPackageReceipt).order_by(AccountPackageReceipt.id.desc()).all()

    def revoke(self, package_id: str, reason: str) -> AccountPackageExport:
        record = self.db.query(AccountPackageExport).filter(
            AccountPackageExport.package_id == package_id
        ).first()
        if record is None:
            raise AccountPackageBusinessError("账号包不存在", code="AP_NOT_FOUND", status=404)
        record.state = "revoked"
        record.revoked_at = utcnow()
        record.revoke_reason = reason[:500]
        safe_commit(self.db)
        return record
