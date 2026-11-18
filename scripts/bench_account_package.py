#!/usr/bin/env python3
"""P4：账号包 KDF/加解密基准（离线，不依赖 HTTP）。

用法: python scripts/bench_account_package.py --iterations 310000 --rounds 5
只测 CPU/IO 局部成本，不替代 HTTP 压测。
"""
import argparse
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.account_package import build_manifest, open_package, seal_package  # noqa: E402
from app.core.grant_signing import generate_keypair  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--iterations", type=int, default=600_000)
    p.add_argument("--rounds", type=int, default=5)
    a = p.parse_args()
    priv, pub = generate_keypair()
    seal_ms, open_ms, sizes = [], [], []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(max(1, a.rounds)):
            manifest = build_manifest(
                package_id=str(uuid.uuid4()),
                organization_code="520100",
                target_machine_code="BENCH-MC",
                items=[{"username": f"u{i}", "credential_hash": "$2b$12$" + "a" * 53,
                        "role": "user", "data_scope": "self"}],
            )
            t = time.perf_counter()
            raw = seal_package(manifest, password="bench-pass-123", private_key_hex=priv,
                               iterations=a.iterations)
            seal_ms.append((time.perf_counter() - t) * 1000)
            t = time.perf_counter()
            open_package(raw, password="bench-pass-123", public_key_hex=pub)
            open_ms.append((time.perf_counter() - t) * 1000)
            sizes.append(len(raw))
    p95 = lambda xs: sorted(xs)[min(len(xs) - 1, int(round(len(xs) * 0.95)) - 1)]  # noqa: E731
    print(f"[account-package bench] iterations={a.iterations} rounds={len(seal_ms)} bytes={sizes[0]}")
    print(f"seal  avg={statistics.mean(seal_ms):.1f}ms p95={p95(seal_ms):.1f}ms")
    print(f"open  avg={statistics.mean(open_ms):.1f}ms p95={p95(open_ms):.1f}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
