# -*- coding: utf-8 -*-
# 固化自 2026-09 深度探测循环（r9 轮）。
# 运行：python backend/tests/probe/probe_r9_quality_analytics_chunked.py
#      或一次跑全部：python backend/tests/probe/run_all.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 9 轮长尾模块：数据质量/分析/离线地图/机器码管理/分片上传/通知偏好（真实 HTTP）"""
import hashlib
import io
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="probe_r9_")
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

    r = client.post("/api/v1/supported-villages",
                    json={"village_name": "探针R9村", "province": "贵州省"}, headers=AUTH)
    vid = (unwrap(r.json()) or {}).get("id")
    check("创建村庄", bool(vid))

    # ═══ 链路 1：数据质量 ═══
    r = client.get("/api/v1/data-quality/report", headers=AUTH)
    check("数据质量报告", r.status_code == 200, (r.status_code, str(r.json())[:120]))
    r = client.post("/api/v1/data-quality/full-check", headers=AUTH)
    check("全面质量检查", r.status_code == 200, str(r.json())[:160])

    # ═══ 链路 2：数据分析 ═══
    r = client.get("/api/v1/analytics/dashboard", headers=AUTH)
    check("分析仪表板", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/analytics/village-analysis", headers=AUTH)
    check("村庄分析", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/analytics/funding-trends", headers=AUTH)
    check("经费趋势", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/analytics/performance-metrics", headers=AUTH)
    check("成效指标", r.status_code == 200, r.status_code)
    r = client.post("/api/v1/analytics/comparison",
                    json={"village_ids": [vid]}, headers=AUTH)
    check("村庄对比(分析)", r.status_code in (200, 400), (r.status_code, str(r.json())[:120]))

    # ═══ 链路 3：离线地图 ═══
    r = client.get("/api/v1/offline-map/status", headers=AUTH)
    check("离线瓦片状态", r.status_code == 200, r.status_code)
    r = client.delete("/api/v1/offline-map/clear", headers=AUTH)
    check("清除离线瓦片", r.status_code == 200, r.status_code)

    # ═══ 链路 4：机器码管理（管理员 CRUD）═══
    r = client.post("/api/v1/machine-code/admin/create",
                    json={"machine_code": "PROBER9MC0000000000000000000000",
                          "description": "探针机器码"}, headers=AUTH)
    mcj = r.json()
    mcd = unwrap(mcj) or {}
    mc_id = mcd.get("id") or mcd.get("machine_code_id")
    check("管理员录入机器码", bool(mc_id), mcj)
    r = client.get("/api/v1/machine-code/admin/list", headers=AUTH)
    lst = unwrap(r.json()) or []
    if isinstance(lst, dict):
        lst = lst.get("items") or lst.get("records") or []
    check("机器码列表", r.status_code == 200 and len(lst) >= 1, (r.status_code, len(lst)))
    r = client.post("/api/v1/machine-code/verify-machine-code",
                    json={"machine_code": "PROBER9MC0000000000000000000000",
                          "verification_code": "0000"}, headers=AUTH)
    check("校验码验证(错误码拒绝或200)", r.status_code in (200, 400), r.status_code)
    if mc_id:
        r = client.post(f"/api/v1/machine-code/admin/revoke/{mc_id}", headers=AUTH)
        check("吊销机器码", r.status_code == 200, str(r.json())[:120])

    # ═══ 链路 5：分片上传（init→chunk→merge 小文件全流程）═══
    payload = b"PROBE-CHUNKED-UPLOAD-CONTENT" * 100
    file_hash = hashlib.md5(payload).hexdigest()
    r = client.post("/api/v1/chunked-upload/init",
                    json={"file_name": "probe.bin", "file_size": len(payload),
                          "chunk_size": 1024, "file_hash": file_hash}, headers=AUTH)
    ij = r.json()
    ijd = unwrap(ij) or {}
    session_id = ijd.get("session_id")
    total_chunks = ijd.get("total_chunks", 0)
    check("分片初始化", r.status_code == 200 and bool(session_id), ij)
    if session_id and total_chunks:
        chunk_ok = True
        for idx in range(total_chunks):
            piece = payload[idx * ijd["chunk_size"]:(idx + 1) * ijd["chunk_size"]]
            r = client.post(f"/api/v1/chunked-upload/chunk/{session_id}/{idx}",
                            files={"file": (f"chunk{idx}", piece, "application/octet-stream")},
                            headers=AUTH)
            if r.status_code != 200:
                chunk_ok = False
                break
        check("分片上传", chunk_ok, str(r.json())[:120])
        r = client.get(f"/api/v1/chunked-upload/progress/{session_id}", headers=AUTH)
        check("分片进度", r.status_code == 200, r.status_code)
        r = client.post(f"/api/v1/chunked-upload/merge/{session_id}", headers=AUTH)
        mj = r.json()
        md = unwrap(mj) or {}
        check("分片合并", r.status_code == 200, str(mj)[:140])
        merged = md.get("file_path") or md.get("path")
        if merged and os.path.exists(merged):
            check("合并文件内容一致", open(merged, "rb").read() == payload)

    # ═══ 链路 6：通知偏好 PUT（R4 只探测了 GET）═══
    r = client.put("/api/v1/notifications/preferences",
                   json={"approval_notifications": True, "system_notifications": True},
                   headers=AUTH)
    check("更新通知偏好", r.status_code == 200, str(r.json())[:140])
    r = client.get("/api/v1/notifications/preferences", headers=AUTH)
    check("通知偏好回读", r.status_code == 200, r.status_code)

print(f"\n===== PASS {len(PASS)} / FAIL {len(FAIL)} =====")
for n, dd in FAIL:
    print("  FAIL:", n, "|", str(dd)[:220])
sys.exit(1 if FAIL else 0)
