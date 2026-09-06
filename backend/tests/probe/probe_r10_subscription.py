# -*- coding: utf-8 -*-
# 固化自 2026-09-06 w15 探测（工单 003 报表订阅闭环全链路）。
# 运行：python backend/tests/probe/probe_r10_subscription.py
#      或一次跑全部：python backend/tests/probe/run_all.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 10 轮：报表订阅全链路（创建/next_send_at 计算/generate-now 落盘+站内消息/
dispatch 到期分发与同周期幂等/启停/删除边界）。"""
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="probe_r10_")
os.chdir(TMP)
os.environ["BUMOFU_BACKEND_DIR_OVERRIDE"] = TMP
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/probe.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "x" * 40
os.environ["UPLOAD_DIR"] = f"{TMP}/uploads"
os.environ["BACKUP_ENABLED"] = "false"

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BACKEND_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print(("PASS" if cond else "FAIL"), name, "" if cond else str(detail)[:240])


def unwrap(j):
    return j.get("data") if isinstance(j, dict) and j.get("code") == 200 and isinstance(j.get("data"), (dict, list)) else j


DB_PATH = f"{TMP}/probe.db"
BASE = "/api/v1/reports/subscriptions"

from app.main import app  # noqa: E402

with TestClient(app, raise_server_exceptions=False) as client:
    # ── 登录 ──
    r = client.get("/api/v1/auth/csrf-token")
    token = (r.json().get("data") or {}).get("csrf_token")
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@2026"},
                    headers={"X-CSRF-Token": token})
    at = (r.json().get("data") or {}).get("access_token")
    AUTH = {"Authorization": f"Bearer {at}", "X-CSRF-Token": token}
    check("管理员登录", bool(at), r.text[:120])

    # ── R1.1 四频次创建 ──
    ids = {}
    for freq, day in [("daily", None), ("weekly", 3), ("monthly", 15), ("quarterly", 20)]:
        r = client.post(BASE, json={
            "name": f"订阅-{freq}", "report_type": "comprehensive", "format": "xlsx",
            "frequency": freq, "send_day": day, "send_time": "08:00",
        }, headers=AUTH)
        body = unwrap(r.json())
        ids[freq] = (body or {}).get("id")
        check(f"创建订阅-{freq}", r.status_code == 200 and ids[freq], r.text[:160])

    # ── R1.2 列表与 next_send_at 计算（四条、均未来、频次语义正确）──
    r = client.get(BASE, params={"page": 1, "page_size": 20}, headers=AUTH)
    items = unwrap(r.json()).get("items") or []
    check("列表返回 4 条", len(items) == 4, len(items))
    now = datetime.now()
    by_freq = {i["frequency"]: i for i in items}
    nxt = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%S") if s and "T" in s else (
        datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None)
    n_daily = nxt(by_freq["daily"]["next_send_at"])
    check("daily next=明天08:00", n_daily is not None and n_daily > now and n_daily.hour == 8,
          by_freq["daily"]["next_send_at"])
    n_weekly = nxt(by_freq["weekly"]["next_send_at"])
    check("weekly next=周三08:00(下一个周三)",
          n_weekly is not None and n_weekly.weekday() == 2 and n_weekly.hour == 8,
          by_freq["weekly"]["next_send_at"])
    n_monthly = nxt(by_freq["monthly"]["next_send_at"])
    check("monthly next=15号08:00", n_monthly is not None and n_monthly.day == 15,
          by_freq["monthly"]["next_send_at"])
    n_quarterly = nxt(by_freq["quarterly"]["next_send_at"])
    check("quarterly next=季度首月20号", n_quarterly is not None
          and n_quarterly.month in (1, 4, 7, 10) and n_quarterly.day == 20,
          by_freq["quarterly"]["next_send_at"])

    # ── R1.3 generate-now：生成+落盘+站内消息+last_sent_at ──
    msg_before_resp = client.get("/api/v1/messages", params={"page": 1, "page_size": 50},
                                 headers=AUTH)
    msg_before_count = len((unwrap(msg_before_resp.json()) or {}).get("items") or [])
    r = client.post(f"{BASE}/{ids['daily']}/generate-now", headers=AUTH)
    body = unwrap(r.json())
    file_name = (body or {}).get("file_name", "")
    file_path = (body or {}).get("file_path", "")
    check("generate-now 200 且带 file_name", r.status_code == 200 and bool(file_name), r.text[:200])
    check("文件真实落盘且非空", file_path and os.path.isfile(file_path)
          and os.path.getsize(file_path) > 0, file_path)
    msg_after_resp = client.get("/api/v1/messages", params={"page": 1, "page_size": 50},
                                headers=AUTH)
    msg_after_items = (unwrap(msg_after_resp.json()) or {}).get("items") or []
    check("站内消息 +1", len(msg_after_items) == msg_before_count + 1,
          f"{msg_before_count} -> {len(msg_after_items)}")
    check("消息标题含订阅名", any("订阅-daily" in (m.get("title") or "") for m in msg_after_items),
          [m.get("title") for m in msg_after_items[:3]])
    r = client.get(f"{BASE}/{ids['daily']}", headers=AUTH)
    sub_now = unwrap(r.json())
    check("last_sent_at 已更新", bool(sub_now.get("last_sent_at")), sub_now)

    # ── R1.4 dispatch 到期分发（DB 回拨 last_sent_at 8 天 → 到期）+ 同周期幂等 ──
    from app.core.database import SessionLocal  # noqa: E402
    from app.services.subscription_dispatch_service import SubscriptionDispatchService  # noqa: E402

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE report_subscriptions SET last_sent_at = datetime('now', '-8 days') WHERE id = ?",
        (ids["daily"],),
    )
    conn.commit()
    conn.close()

    db = SessionLocal()
    stats1 = __import__("asyncio").run(
        SubscriptionDispatchService().dispatch_due_subscriptions(db, datetime.now()))
    db.close()
    check("回拨后 dispatch 生成 ≥1", stats1["dispatched"] >= 1, stats1)
    check("dispatch 无失败", stats1["failed"] == 0, stats1)

    conn = sqlite3.connect(DB_PATH)
    count1 = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='probe_marker'").fetchone()
    conn.close()
    # 同 now 再跑：last_sent_at 已更新 → 同周期不重复
    db = SessionLocal()
    stats2 = __import__("asyncio").run(
        SubscriptionDispatchService().dispatch_due_subscriptions(db, datetime.now()))
    db.close()
    check("同周期二次 dispatch 不重复", stats2["dispatched"] == 0, stats2)

    # ── R1.5 边界：禁用 400 / 不存在 404 / toggle / 删除 ──
    r = client.post(f"{BASE}/{ids['weekly']}/toggle", headers=AUTH)
    check("toggle 禁用成功", r.status_code == 200 and
          (unwrap(r.json()) or {}).get("is_active") is False, r.text[:160])
    r = client.post(f"{BASE}/{ids['weekly']}/generate-now", headers=AUTH)
    check("禁用订阅 generate-now 400", r.status_code == 400, r.text[:160])
    r = client.post(f"{BASE}/999999/generate-now", headers=AUTH)
    check("不存在订阅 404", r.status_code == 404, r.text[:160])
    r = client.delete(f"{BASE}/{ids['monthly']}", headers=AUTH)
    check("删除订阅 200", r.status_code == 200, r.text[:160])
    r = client.get(f"{BASE}/{ids['monthly']}", headers=AUTH)
    check("删除后详情 404", r.status_code == 404, r.status_code)

print(f"\n===== w15 R1 订阅全链路: PASS {len(PASS)} / FAIL {len(FAIL)} =====")
sys.exit(1 if FAIL else 0)
