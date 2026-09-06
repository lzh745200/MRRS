# -*- coding: utf-8 -*-
# 固化自 2026-09 深度探测循环（r7 轮）。
# 运行：python backend/tests/probe/probe_r7_help_assessment_effectiveness.py
#      或一次跑全部：python backend/tests/probe/run_all.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 7 轮长尾模块：帮助文档全量 / 考核评估 / 成效评估（真实 HTTP）"""
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="probe_r7_")
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
    if isinstance(j, dict) and isinstance(j.get("data"), (dict, list)):
        if j.get("code") == 200 or j.get("success") is True:
            return j["data"]
    return j


from app.main import app  # noqa: E402

with TestClient(app, raise_server_exceptions=False) as client:
    r = client.get("/api/v1/auth/csrf-token")
    token = (r.json().get("data") or {}).get("csrf_token")
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@2026"},
                    headers={"X-CSRF-Token": token})
    at = (r.json().get("data") or {}).get("access_token")
    check("管理员登录", bool(at))
    AUTH = {"Authorization": f"Bearer {at}", "X-CSRF-Token": token}

    # ═══ 帮助文档全量 ═══
    r = client.get("/api/v1/system/help/articles", headers=AUTH)
    arts = unwrap(r.json()) or []
    if isinstance(arts, dict):
        arts = arts.get("items") or arts.get("articles") or []
    check("帮助文章列表", r.status_code == 200 and len(arts) >= 3, (r.status_code, len(arts)))
    # 每篇文章可取
    ok_detail = 0
    for a in arts[:5]:
        aid = a.get("id")
        r = client.get(f"/api/v1/system/help/articles/{aid}", headers=AUTH)
        if r.status_code == 200:
            ok_detail += 1
    check("文章详情抽样", ok_detail > 0, ok_detail)
    # 关键词搜索
    r = client.get("/api/v1/system/help/articles", params={"keyword": "密码"}, headers=AUTH)
    check("帮助搜索", r.status_code == 200, r.status_code)
    # 分类过滤
    r = client.get("/api/v1/system/help/articles", params={"category": "quick_start"}, headers=AUTH)
    check("帮助分类过滤", r.status_code == 200, r.status_code)

    # ═══ 考核评估 ═══
    r = client.post("/api/v1/supported-villages",
                    json={"village_name": "探针考核村", "province": "贵州省"}, headers=AUTH)
    vid = (unwrap(r.json()) or {}).get("id")
    check("创建考核村庄", bool(vid))
    r = client.get("/api/v1/assessment/village-scores", headers=AUTH)
    check("村庄得分", r.status_code == 200, str(r.json())[:140])
    r = client.get("/api/v1/assessment/anomalies", headers=AUTH)
    check("考核异常", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/assessment/trend-prediction", headers=AUTH)
    check("趋势预测", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/assessment/village-comparison", params={"village_ids": str(vid)}, headers=AUTH)
    check("村庄对比", r.status_code == 200, r.status_code)

    # ═══ 成效评估 ═══
    r = client.post("/api/v1/effectiveness/evaluate",
                    json={"village_id": vid, "year": 2026}, headers=AUTH)
    check("成效评估执行(2026)", r.status_code == 200, str(r.json())[:160])
    r = client.post("/api/v1/effectiveness/evaluate",
                    json={"village_id": vid, "year": 2025}, headers=AUTH)
    check("成效评估执行(2025)", r.status_code == 200, str(r.json())[:160])
    r = client.get(f"/api/v1/effectiveness/report/{vid}", params={"year": 2026}, headers=AUTH)
    check("成效报告", r.status_code == 200, r.status_code)
    r = client.get(f"/api/v1/effectiveness/compare/{vid}", params={"year1": 2025, "year2": 2026}, headers=AUTH)
    check("成效对比", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/effectiveness/rankings", params={"year": 2026}, headers=AUTH)
    check("成效排名", r.status_code == 200, r.status_code)

print(f"\n===== PASS {len(PASS)} / FAIL {len(FAIL)} =====")
for n, dd in FAIL:
    print("  FAIL:", n, "|", str(dd)[:220])
sys.exit(1 if FAIL else 0)
