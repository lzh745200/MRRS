#!/usr/bin/env python3
"""P5：双机离线等价演练（源库 A → .apkg 文件 → 目标库 B）。

不启动 HTTP、不联网；验证包文件可离线搬运、目标库一次性确认。
实体双机验收仍需按 docs 清单人工执行。
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.grant_signing import generate_keypair  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.services.account_package_service import AccountPackageService  # noqa: E402


def _db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, autoflush=False, autocommit=False)()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--keep", action="store_true", help="保留临时包用于人工检查")
    a = p.parse_args()
    priv, pub = generate_keypair()
    settings.ACCOUNT_PACKAGE_ENABLED = True
    settings.ACCOUNT_PACKAGE_SIGNING_KEY = priv
    settings.ACCOUNT_PACKAGE_PUBKEY = pub
    settings.ACCOUNT_PACKAGE_KDF_ITERATIONS = 310_000
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        AccountPackageService.package_dir = classmethod(lambda cls: tmp_path)
        src = _db()
        root = Organization(code="520000", name="州局", level="1", is_active=True)
        src.add(root)
        src.commit()
        src.refresh(root)
        src.add(Organization(code="520100", name="市局", parent_id=root.id, level="2", is_active=True))
        src.commit()
        out = AccountPackageService(src).export_package(
            package_id="55555555-5555-5555-5555-555555555555",
            organization_code="520100", organization_name="市局", parent_code="520000",
            admin_username="mc_admin", admin_full_name="管理员", target_machine_code="MC-A",
            grants={"projects": "edit"}, password="offline-pass-123",
            issued_by=SimpleNamespace(id=1, organization_id=root.id),
        )
        package = tmp_path / out["file_name"]
        # 模拟离线介质：复制到另一目录后才在目标机读取
        usb = tmp_path / "usb"
        usb.mkdir()
        target_file = usb / package.name
        target_file.write_bytes(package.read_bytes())
        dst = _db()
        dst.add(Organization(code="520000", name="州局", level="1", is_active=True))
        dst.commit()
        result = AccountPackageService(dst).confirm(
            target_file.read_bytes(), password="offline-pass-123", machine_code="MC-A"
        )
        assert result["users"][0]["username"] == "mc_admin"
        print(
            f"[dual-machine] OK package={out['package_id']} "
            f"target_file={target_file.name} users={len(result['users'])}"
        )
        if a.keep:
            print(f"[dual-machine] kept at {tmp_path} (process exit will remove; use --keep only for inspection)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
