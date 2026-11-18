#!/usr/bin/env python3
"""P4：账号包 HTTP 并发压测（真实后端，不内置账号/口令）。

示例:
  python scripts/load_account_package_http.py --base-url http://127.0.0.1:8000 \
      --token <JWT> --file pkg.apkg --password '<包口令>' --concurrency 8 --rounds 40
只调用只读 /preview，避免压测反复建号；统计成功率与 p50/p95/p99。
"""
import argparse
import asyncio
import statistics
import time

import httpx


async def once(client, url, headers, file_bytes, password):
    t = time.perf_counter()
    try:
        r = await client.post(
            url,
            headers=headers,
            files={"file": ("pkg.apkg", file_bytes, "application/octet-stream")},
            data={"password": password},
        )
        ok = r.status_code == 200
        return ok, (time.perf_counter() - t) * 1000, r.status_code
    except httpx.HTTPError:
        return False, (time.perf_counter() - t) * 1000, 0


async def run(a):
    file_bytes = open(a.file, "rb").read()
    headers = {"Authorization": f"Bearer {a.token}"} if a.token else {}
    sem = asyncio.Semaphore(a.concurrency)
    async with httpx.AsyncClient(base_url=a.base_url, timeout=60) as client:
        async def bounded():
            async with sem:
                return await once(client, "/api/v1/account-packages/preview", headers, file_bytes, a.password)
        results = await asyncio.gather(*(bounded() for _ in range(a.rounds)))
    oks = [ms for ok, ms, _ in results if ok]
    bad = [code for ok, _, code in results if not ok]
    if not oks:
        print(f"[load] 全部失败 status={bad[:5]}")
        return 1
    s = sorted(oks)
    pct = lambda p: s[min(len(s) - 1, max(0, int(round(len(s) * p / 100)) - 1))]  # noqa: E731
    print(f"[load] total={len(results)} ok={len(oks)} fail={len(bad)} concurrency={a.concurrency}")
    print(f"[load] p50={pct(50):.0f}ms p95={pct(95):.0f}ms p99={pct(99):.0f}ms avg={statistics.mean(oks):.0f}ms")
    return 0 if not bad else 2


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--token", default="")
    p.add_argument("--file", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--rounds", type=int, default=20)
    raise SystemExit(asyncio.run(run(p.parse_args())))
