#!/usr/bin/env python3
"""
安全自检脚本

检查所有安全加固项是否正确配置:
  - 数据库加密状态
  - 加密算法版本
  - 审计日志完整性
  - 文件权限
  - CSRF保护状态
  - 速率限制状态

退出码:
  0 = 全部通过
  1 = 存在WARNING
  2 = 存在CRITICAL问题
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

CRITICAL = "CRITICAL"
WARNING = "WARNING"
PASS = "PASS"

results = []


def check(name: str, condition: bool, level: str = CRITICAL, detail: str = ""):
    """记录检查结果"""
    status = PASS if condition else level
    results.append({
        "name": name,
        "status": status,
        "detail": detail if not condition else "OK",
    })
    icon = "[PASS]" if condition else ("[WARN]" if level == WARNING else "[FAIL]")
    print(f"  {icon} [{status}] {name}")
    if not condition and detail:
        print(f"    详情: {detail}")


def main():
    print("=" * 60)
    print("军事乡村振兴管理系统 - 安全自检")
    print("=" * 60)

    # 1. 配置检查
    print("\n[CFG] 配置检查")
    try:
        from app.core.config import settings

        check("SECRET_KEY已配置", bool(settings.SECRET_KEY), CRITICAL)
        check("CSRF保护已启用", settings.CSRF_ENABLED, CRITICAL)
        check("速率限制已启用", settings.RATE_LIMIT_ENABLED, WARNING)
        check("Bcrypt轮数≥10", settings.BCRYPT_ROUNDS >= 10, WARNING,
              f"当前{settings.BCRYPT_ROUNDS}轮")
        check("数据库加密已启用", settings.DB_ENCRYPTION_ENABLED, WARNING,
              "SQLite数据库文件未加密，物理接触可读取")
        check("调试模式已关闭", not settings.DEBUG, WARNING,
              "生产环境应关闭DEBUG")
        check("加密后端配置", hasattr(settings, 'ENCRYPTION_BACKEND'), WARNING,
              "未配置ENCRYPTION_BACKEND，默认应使用aes256")
    except Exception as e:
        check(f"配置加载: {e}", False, CRITICAL, str(e))

    # 2. 数据库检查
    print("\n[DB] 数据库检查")
    try:
        from app.core.database import engine, DATABASE_URL

        is_sqlite = "sqlite" in DATABASE_URL
        check("使用SQLite数据库", is_sqlite, WARNING)

        with engine.connect() as conn:
            # WAL模式检查
            wal = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
            check("WAL模式已启用", wal.upper() == "WAL", WARNING,
                  f"当前模式: {wal}")

            # 外键检查
            fk = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
            check("外键约束已启用", bool(fk), CRITICAL)

            # 加密检查
            try:
                conn.exec_driver_sql("PRAGMA key")
                check("SQLCipher加密", True, WARNING)
            except Exception:
                check("SQLCipher加密", False, WARNING,
                      "数据库文件未加密，建议启用sqlcipher3")
    except Exception as e:
        check(f"数据库连接: {e}", False, CRITICAL, str(e))

    # 3. 加密模块检查
    print("\n[CRYPT] 加密模块检查")
    try:
        from app.services.encryption_service import _get_cipher

        cipher = _get_cipher()
        backend = getattr(cipher, '_backend', 'unknown')
        check(f"加密后端: {backend}",
              backend in ("aes256", "fernet"), WARNING,
              f"当前后端: {backend}")

        # 测试加密/解密
        test_data = b"security-self-check-test-data-2026"
        encrypted = cipher.encrypt(test_data)
        decrypted = cipher.decrypt(encrypted)
        check("加密/解密正常", decrypted == test_data, CRITICAL)

        # 检查密钥长度
        if backend == "aes256" and hasattr(cipher, '_key'):
            key_len = len(cipher._key)
            check(f"AES-256密钥长度: {key_len * 8}位",
                  key_len == 32, WARNING,
                  f"当前{key_len * 8}位")
    except Exception as e:
        check(f"加密模块: {e}", False, CRITICAL, str(e))

    # 4. 审计日志检查
    print("\n[AUDIT] 审计日志检查")
    try:
        from app.models.audit import AuditLog
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            count = db.query(AuditLog).count()
            check("审计日志记录存在", count > 0, WARNING,
                  f"当前{count}条记录")
        finally:
            db.close()
    except Exception as e:
        check(f"审计日志: {e}", False, WARNING, str(e))

    # 5. 文件系统检查
    print("\n[FS] 文件系统检查")
    try:
        from app.utils.paths import get_database_path

        db_path = get_database_path()
        check("数据库文件存在", db_path.exists(), CRITICAL)

        if db_path.exists():
            import stat
            mode = db_path.stat().st_mode
            is_readable_others = bool(mode & stat.S_IROTH)
            check("数据库文件权限（仅所有者可读写）",
                  not is_readable_others, WARNING,
                  "数据库文件对其他用户可读")
    except Exception as e:
        check(f"文件系统: {e}", False, WARNING, str(e))

    # 汇总
    print("\n" + "=" * 60)
    critical_fails = sum(1 for r in results if r["status"] == CRITICAL)
    warnings = sum(1 for r in results if r["status"] == WARNING)
    passes = sum(1 for r in results if r["status"] == PASS)

    print(f"总计: {len(results)}项检查")
    print(f"  [PASS] 通过: {passes}")
    print(f"  [WARN] 警告: {warnings}")
    print(f"  [FAIL] 严重: {critical_fails}")
    print("=" * 60)

    if critical_fails > 0:
        print("\n[WARN] 存在严重安全问题，建议立即处理！")
        return 2
    elif warnings > 0:
        print("\n[WARN] 存在安全警告，建议尽快处理。")
        return 1
    else:
        print("\n[PASS] 所有安全检查通过。")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
