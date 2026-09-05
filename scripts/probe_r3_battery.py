# -*- coding: utf-8 -*-
"""Round-3 battery: discover real paths from OpenAPI then probe message/reminder/template/report/audit/export-history modules."""
import json
import time

import httpx

BASE = "http://127.0.0.1:8006/api/v1"
LOG = open(r"C:\military-Rural Revitalization-system\scripts\probe_r3_out.txt", "w", encoding="utf-8")


def log(name, ok, extra=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {extra}", flush=True)
    LOG.write(f"[{'PASS' if ok else 'FAIL'}] {name} {extra}\n")
    LOG.flush()


def body_of(r):
    try:
        return r.json()
    except Exception:
        return {}


def main():
    c = httpx.Client(base_url=BASE, timeout=60)
    for _ in range(60):
        try:
            if c.get(f"{BASE}/health").status_code < 500:
                break
        except Exception:
            pass
        time.sleep(1)
    j = c.post(f"{BASE}/auth/login", json={"username": "admin", "password": "Admin@12345"}).json()
    ah = {"Authorization": f"Bearer {j['data']['access_token']}"}
    log("admin-login", j.get("code") == 200)

    # openapi discovery
    try:
        spec = c.get(f"{BASE}/openapi.json").json()
        paths = sorted(spec.get("paths", {}).keys())
        log("openapi-discovery", len(paths) > 50, f"paths={len(paths)}")
    except Exception as e:
        log("openapi-discovery", False, f"exc {type(e).__name__}: {e}")
        return

    want = ("message", "remind", "template", "report", "audit", "operation-log",
            "import-export", "data-report", "help", "version", "config", "backup",
            "feedback", "search", "recycle", "map", "sync", "task")
    picked = [p for p in paths if any(w in p.lower() for w in want)]
    # dedupe by keeping GET list-ish candidates only
    got = 0
    checked = set()
    for p in picked:
        methods = {m.lower() for m in spec["paths"][p].keys()}
        if "get" not in methods:
            continue
        if p in checked:
            continue
        checked.add(p)
        if got >= 26:
            break
        try:
            r = c.get(f"{BASE}{p}", headers=ah, params={"page": 1, "page_size": 5})
            j = body_of(r)
            code = j.get("code") if isinstance(j, dict) else None
            ok = r.status_code < 400 and (code is None or code == 200 or code == 0)
            got += 1
            log(f"GET {p}", ok, f"http={r.status_code}")
        except Exception as e:
            log(f"GET {p}", False, f"exc {type(e).__name__}: {e}")

    # one POST-ish smoke per key module that is not destructive: mark-message-read & export-history none; skip POSTs this round.
    LOG.close()


if __name__ == "__main__":
    main()
