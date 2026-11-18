#!/usr/bin/env python3
"""P4：账号包 HTTP/ASGI 并发压测（无需外部后端）。

使用真实 FastAPI 路由 `/account-packages/export`，依赖覆盖超管；临时 SQLite，
统计成功率/p50/p95/p99。网络层为 ASGI transport，不是物理网卡压测。
"""
import argparse
import asyncio
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.core.grant_signing import generate_keypair  # noqa: E402
from app.core.security import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.services.account_package_service import AccountPackageService  # noqa: E402


def _db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, autoflush=False, autocommit=False)()


async def run(rounds: int, concurrency: int):
    priv, pub = generate_keypair()
    settings.ACCOUNT_PACKAGE_ENABLED = True
    settings.ACCOUNT_PACKAGE_SIGNING_KEY = priv
    settings.ACCOUNT_PACKAGE_PUBKEY = pub
    settings.ACCOUNT_PACKAGE_KDF_ITERATIONS = 310_000
    tmp = tempfile.TemporaryDirectory()
    AccountPackageService.package_dir = classmethod(lambda cls: Path(tmp.name))
    db = _db()
    org = Organization(code="520100", name="市局", level="1", is_active=True)
    db.add(org); db.commit(); db.refresh(org)
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=org.id)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin

    sem = asyncio.Semaphore(concurrency)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        csrf_resp = await client.get("/api/v1/auth/csrf-token")
        csrf_token = csrf_resp.json()["data"]["csrf_token"]
        headers = {"X-CSRF-Token": csrf_token}

        async def one():
            async with sem:
                payload = {
                    "organization_code": "520100", "organization_name": "市局", "parent_code": "",
                    "admin_username": f"u{uuid.uuid4().hex[:10]}", "admin_full_name": "U",
                    "target_machine_code": "LOAD-MC-123", "package_password": "passw0rd-pass",
                    "grants": {"projects": "view"}, "valid_days": 7,
                }
                t = time.perf_counter()
                r = await client.post("/api/v1/account-packages/export", json=payload, headers=headers)
                return r.status_code, (time.perf_counter() - t) * 1000
        results = await asyncio.gather(*(one() for _ in range(rounds)))
    app.dependency_overrides.clear()
    tmp.cleanup()
    ok = sorted(ms for st, ms in results if st == 200)
    bad = [st for st, _ in results if st != 200]
    print(f"[asgi-load] total={len(results)} ok={len(ok)} fail={len(bad)} concurrency={concurrency}")
    if ok:
        pct = lambda p: ok[min(len(ok)-1, max(0, int(round(len(ok)*p/100))-1))]  # noqa: E731
        print(f"[asgi-load] p50={pct(50):.0f}ms p95={pct(95):.0f}ms p99={pct(99):.0f}ms avg={statistics.mean(ok):.0f}ms")
    return 0 if not bad else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=4)
    a = ap.parse_args()
    raise SystemExit(asyncio.run(run(a.rounds, a.concurrency)))
