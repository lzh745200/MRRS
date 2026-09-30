"""启动环境钩子：依赖包检查 / 版本变更记录 / 关键文件完整性（B3 自 main.py 迁入）。"""

import logging
from pathlib import Path

from app.core.required_packages import (  # noqa: E402
    REQUIRED_RUNTIME_PACKAGES,
    fix_command,
    missing_runtime,
)

logger = logging.getLogger("assistance_management")

# 向后兼容别名（既有 `from app.main import REQUIRED_PACKAGES` 用法继续可用）
REQUIRED_PACKAGES = [dep.module for dep in REQUIRED_RUNTIME_PACKAGES]


def _check_required_packages():
    """启动自检：运行时必需依赖是否可导入（登记表见 app/core/required_packages.py）

    R15（2026-09-14）：此前三处清单互相漂移，UI 那份还列了应用不用的 fpdf2 与仅开发期
    的 pytest，导致恒报缺失。现统一走登记表 + import 名校验。
    """
    missing = missing_runtime()
    if missing:
        detail = "，".join(f"{dep.distribution}（{dep.purpose}）" for dep in missing)
        hint = fix_command(missing)
        if hint:
            logger.warning("缺少运行时依赖: %s；修复命令: %s", detail, hint)
        else:
            # 冻结运行时（安装包自包含）缺依赖 = 包本身异常，pip 不适用
            logger.error(
                "自包含运行时缺少依赖: %s —— 请重新安装安装包或联系管理员",
                detail,
            )
    else:
        logger.info("所有关键依赖包已安装。")


def _check_and_record_version_change():
    """检查版本变更并记录更新日志"""
    try:
        from app.core.database import SessionLocal
        from app.services.update_log_service import UpdateLogService
        from app.services.version_service import version_service

        db = SessionLocal()
        try:
            update_service = UpdateLogService(db)
            current_version = version_service.get_current_version()
            version_str = current_version.get("version", "unknown")

            result = update_service.check_and_record_version_change(
                current_version=version_str,
                updated_by="system",
            )

            if result:
                action = result.get("action")
                if action == "initialize":
                    init_count = result["result"].get("initialized_count", 0)
                    logger.info("版本历史初始化完成: %s 条记录", init_count)
                elif action == "record_change":
                    old_ver = result.get("old_version")
                    new_ver = result.get("new_version")
                    logger.info("检测到版本变更: %s -> %s", old_ver, new_ver)
            else:
                logger.info("当前版本: %s", version_str)

        finally:
            db.close()
    except Exception as e:
        logger.warning("版本变更检查失败: %s", e)


class FileIntegrityError(RuntimeError):
    """关键文件完整性校验失败（清单比对不符 / 关键文件缺失）。"""


_INTEGRITY_MANIFEST_NAME = "integrity_manifest.json"


def _load_integrity_manifest(base_dir: Path):
    """读取完整性清单；不可用时返回 None（按"未提供"处理）。"""
    import json

    manifest_path = base_dir / _INTEGRITY_MANIFEST_NAME
    if not manifest_path.exists():
        return None
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        # 清单存在但读取/解析失败：不能当作"校验通过"，但也不阻断启动
        # （装机残留的坏文件会把应用永久卡在启动阶段）。
        logger.error("文件完整性检查: 清单无法解析 %s: %s", manifest_path, exc)
        return None
    if isinstance(raw_manifest, dict):
        return raw_manifest
    logger.error(
        "文件完整性检查: 清单顶层不是对象（%s），按未提供处理",
        type(raw_manifest).__name__,
    )
    return None


def _collect_integrity_mismatches(base_dir: Path, critical_files, manifest) -> list:
    """比对关键文件哈希，返回不符合项描述列表（按严格与否区分处理）。"""
    import hashlib

    mismatches = []
    for rel_path in critical_files:
        file_path = base_dir / rel_path
        if not file_path.exists():
            if manifest is not None:
                mismatches.append(f"{rel_path}: 缺失")
            else:
                logger.warning("文件完整性检查: 关键文件缺失: %s", rel_path)
            continue

        try:
            file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        except OSError as exc:
            if manifest is not None:
                mismatches.append(f"{rel_path}: 无法读取({exc})")
            else:
                logger.warning("文件完整性检查: 无法读取 %s: %s", rel_path, exc)
            continue

        if manifest is None:
            logger.debug("文件完整性: %s SHA256=%s", rel_path, file_hash[:16])
            continue

        expected = manifest.get(rel_path)
        if not expected:
            logger.warning("文件完整性检查: 清单未登记 %s，跳过比对", rel_path)
        elif expected != file_hash:
            mismatches.append(f"{rel_path}: 哈希不符")

    return mismatches


def _verify_file_integrity(base_dir: Path | None = None):
    """启动时验证关键文件完整性（防二进制被替换）。

    有清单（backend/integrity_manifest.json，形如 {"app/main.py": "<sha256>"}）时
    **严格比对**：任何关键文件缺失或哈希不符都抛 FileIntegrityError 中止启动
    （fail-closed，防替换/篡改）。没有清单时不假装校验过，只记 WARNING 说明
    基线比对未启用 —— 此前实现仅把哈希写进 DEBUG 日志、缺文件也只是一条
    warning，与 docstring "防止二进制被替换" 完全不符（深审 LIVE #79）。

    Args:
        base_dir: 仓库（backend）根目录；默认由本模块位置上溯三级，测试可注入。

    Raises:
        FileIntegrityError: 提供了清单且存在缺失/哈希不符/无法读取的关键文件。
    """
    _critical_files = [
        "app/core/config.py",
        "app/core/security.py",
        "app/core/database.py",
        "app/main.py",
    ]

    # 本模块位于 app/startup/，仓库（backend）根需上溯三级
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent.parent

    manifest = _load_integrity_manifest(base_dir)
    if manifest is None:
        logger.warning(
            "文件完整性检查: 未提供 %s，本次仅记录哈希、不做基线比对（防篡改未启用）",
            _INTEGRITY_MANIFEST_NAME,
        )

    mismatches = _collect_integrity_mismatches(base_dir, _critical_files, manifest)

    if mismatches:
        raise FileIntegrityError(
            "关键文件完整性校验失败（文件可能被替换/篡改）: " + "; ".join(mismatches)
        )

    logger.info("关键文件完整性检查完成 (%d个文件)", len(_critical_files))
