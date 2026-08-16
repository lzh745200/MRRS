# -*- coding: utf-8 -*-
"""权限包控制 + 数据上报接收 + 自动校验纠正 全链路验证（隔离库 permflow_test.db : 8001）"""
import json
import time
import io
import zipfile
import httpx

BASE = "http://127.0.0.1:8001/api/v1"
TS = int(time.time())
results = []


def record(name, passed, detail=""):
    results.append({"test": name, "passed": bool(passed), "detail": str(detail)[:400]})
    print(("PASS" if passed else "FAIL"), "|", name, "|", str(detail)[:180])


c = httpx.Client(base_url=BASE, timeout=120)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""


def login(u, p):
    r = c.post("/auth/login", json={"username": u, "password": p})
    return r.json().get("data", {}).get("access_token")


ADMIN = login("admin", "Admin@12345")
print("admin login:", bool(ADMIN))
AH = {"Authorization": "Bearer " + ADMIN}

# ================= Part A 权限包 =================
# A1 管理员取全量菜单（/menus/accessible 为前端实际消费端点）
r = c.get("/menus/accessible", headers=AH)
j = r.json()
menus_data = j.get("data") or j
def flat_keys(node):
    if not isinstance(node, list):
        node = [node]
    keys = []
    for m in node:
        if isinstance(m, dict):
            k = m.get("key") or m.get("menuKey") or m.get("id")
            if k:
                keys.append(str(k))
            for sub in (m.get("children") or []):
                if isinstance(sub, dict) and (sub.get("key") or sub.get("menuKey") or sub.get("id")):
                    keys.append(str(sub.get("key") or sub.get("menuKey") or sub.get("id")))
    return keys
all_keys = flat_keys(menus_data) if isinstance(menus_data, list) else []
record("A1 管理员菜单全量获取", r.status_code == 200 and len(all_keys) > 5, f"keys={len(all_keys)} sample={all_keys[:8]}")

# A2 创建权限包（合法key子集）
pack_keys = all_keys[:2]
r = c.post("/permission-packs", json={"name": f"受限板块包{TS}", "menu_keys": pack_keys, "description": "仅开放前两个板块"}, headers=AH)
pack_id = ((r.json().get("data") or {}) or {}).get("id")
record("A2 创建权限包", r.status_code in (200, 201) and pack_id, f"id={pack_id} body={r.text[:150]}")

# A3 非法 key 拒绝
r = c.post("/permission-packs", json={"name": "非法包", "menu_keys": ["no-such-key-xyz"]}, headers=AH)
record("A3 非法菜单key被拒422", r.status_code == 422, f"status={r.status_code} body={r.text[:150]}")

# A4 绑定普通用户
r = c.post(f"/permission-packs/{pack_id}/bind-users", json={"user_ids": [2]}, headers=AH)
record("A4 权限包绑定用户", r.status_code == 200, r.text[:150])

# A5 绑定管理员被拒
r = c.post(f"/permission-packs/{pack_id}/bind-users", json={"user_ids": [1]}, headers=AH)
record("A5 绑定管理员被拒400", r.status_code == 400, f"status={r.status_code} body={r.text[:120]}")

# A6 普通用户登录 → 菜单受限
SUB = login("subuser1", "Sub@123456")
SH = {"Authorization": "Bearer " + SUB}
r = c.get("/menus/accessible", headers=SH)
j = r.json()
user_menus = j.get("data") or j
user_keys = flat_keys(user_menus) if isinstance(user_menus, list) else []
in_pack = set(user_keys).issubset(set(pack_keys)) and bool(user_keys)
record("A6 用户菜单仅含包内板块", r.status_code == 200 and in_pack,
       f"user_keys={user_keys} pack={pack_keys}")

# A7 解绑 → 菜单恢复角色默认
r = c.post(f"/permission-packs/{pack_id}/unbind-users", json={"user_ids": [2]}, headers=AH)
r2 = c.get("/menus/accessible", headers=SH)
j2 = r2.json()
um2 = j2.get("data") or j2
uk2 = flat_keys(um2) if isinstance(um2, list) else []
record("A7 解绑后菜单恢复默认", r.status_code == 200 and len(uk2) > len(user_keys),
       f"before={len(user_keys)} after={len(uk2)}")

# 重新绑定供后续测试
c.post(f"/permission-packs/{pack_id}/bind-users", json={"user_ids": [2]}, headers=AH)

# ================= Part B 数据包上报/接收 =================
# B1 下级录入数据
r = c.post("/supported-villages", json={"village_name": f"下级上报村A{TS}", "code": f"RPA{TS}",
           "province": "贵州省", "city": "毕节市", "county": "织金县", "population": 520}, headers=SH)
vid = ((r.json().get("data") or {})).get("id")
record("B1 下级录入帮扶村", r.status_code in (200, 201) and vid, f"vid={vid} body={r.text[:120]}")

r = c.post("/funds", json={"name": f"下级经费{TS}", "planned_amount": 80000}, headers=SH)
fid = ((r.json().get("data") or {})).get("id")
record("B2 下级录入经费", r.status_code in (200, 201) and fid, f"fid={fid}")

# B3 一键上报
r = c.post("/data-packages/one-click-report", json={"remarks": f"下级甲全量上报{TS}"}, headers=SH)
exported_pkg_id = r.headers.get("X-Package-Id")
rec_count = int(r.headers.get("X-Record-Count") or 0)
zip_bytes = r.content
record("B3 一键生成上报包", r.status_code == 200 and exported_pkg_id and len(zip_bytes) > 1000,
       f"pkg={exported_pkg_id} records={rec_count} zip={len(zip_bytes)}B")

# B4 下级可见自己的包
r = c.get("/data-packages", params={"page": 1, "page_size": 50}, headers=SH)
j = r.json()
_data = j.get("data") if isinstance(j.get("data"), dict) else j
items = _data.get("items") or []
own = [i for i in items if str(i.get("id")) == str(exported_pkg_id)]
record("B4 下级列表可见上报包", r.status_code == 200 and len(own) >= 1, f"own={len(own)} total={len(items)}")

# B5 管理员导入接收（上传zip）
files = {"file": ("report.zip", zip_bytes, "application/zip")}
r = c.post("/data-packages/import", files=files, headers=AH)
j = r.json()
imp_pkg_id = ((j.get("data") or {}) or {}).get("id") or j.get("package_id")
record("B5 管理员上传接收数据包", r.status_code in (200, 201) and imp_pkg_id, f"pkg={imp_pkg_id} body={r.text[:200]}")

# B6 校验（自动校验）
r = c.post(f"/data-packages/{imp_pkg_id}/validate", headers=AH)
j = r.json()
valid = j.get("is_valid")
field_stats = j.get("field_validation") or j.get("fields") or {}
record("B6 数据包自动校验", r.status_code == 200 and valid is True, f"valid={valid} body={r.text[:250]}")

# B7 预览
r = c.get(f"/data-packages/{imp_pkg_id}/preview", headers=AH)
j = r.json()
preview_rows = j if isinstance(j, list) else (j.get("data") if isinstance(j, dict) else None)
record("B7 数据包预览", r.status_code == 200 and isinstance(preview_rows, list) and len(preview_rows) >= 1,
       f"rows={len(preview_rows) if isinstance(preview_rows, list) else 'n/a'}")

# B8 确认导入保存
r = c.post(f"/data-packages/{imp_pkg_id}/confirm", json={"overwrite_existing": False, "selected_types": []}, headers=AH)
j = r.json()
imported_total = sum((j.get("imported_counts") or {}).values()) if isinstance(j.get("imported_counts"), dict) else 0
record("B8 确认导入保存(数据完整)", r.status_code == 200 and imported_total >= rec_count,
       f"exported={rec_count} imported={imported_total} body={r.text[:300]}")

# B9 管理员侧数据可见（保存生效）
r = c.get("/supported-villages", params={"keyword": f"下级上报村A{TS}", "page": 1, "page_size": 5}, headers=AH)
items = (r.json().get("data") or {}).get("items", [])
record("B9 接收数据已保存可查", r.status_code == 200 and len(items) >= 1, f"found={len(items)}")

# B10 自动校验纠正：篡改包内 villages 数据（1行可纠正 + 1行不可修复）
try:
    bio = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(bio) as z:
        names = z.namelist()
        print("   zip entries:", names[:10])
        # 找 villages 数据文件
        vfile = next((n for n in names if "village" in n.lower() and n.endswith(".json")), None)
        content = z.read(vfile) if vfile else b"{}"
    vdata = json.loads(content.decode("utf-8"))
    rows = vdata if isinstance(vdata, list) else (vdata.get("data") or vdata.get("items") or [])
    print("   villages rows:", json.dumps(rows, ensure_ascii=False)[:300])
    if isinstance(rows, list) and rows:
        # 修改：首行村名加首尾空格（自动纠正 trim）；追加一行缺必填 village_name（拒绝）
        if isinstance(rows[0], dict) and rows[0].get("village_name"):
            rows[0]["village_name"] = "  " + str(rows[0]["village_name"]) + "  "
        rows.append({"population": 100, "province": "贵州省"})  # 缺必填 village_name → rejected
        new_content = json.dumps(rows, ensure_ascii=False).encode("utf-8")
        out = io.BytesIO()
        with zipfile.ZipFile(bio) as zin, zipfile.ZipFile(out, "w") as zout:
            for n in zin.namelist():
                data = zin.read(n)
                if n == vfile:
                    data = new_content
                zout.writestr(n, data)
        tampered = out.getvalue()
        r = c.post("/data-packages/import", files={"file": ("tampered.zip", tampered, "application/zip")}, headers=AH)
        tpkg = (((r.json().get("data") or {}) or {}).get("id")) or r.json().get("package_id")
        if tpkg:
            rv = c.post(f"/data-packages/{tpkg}/validate", headers=AH)
            jv = rv.json()
            warn_text = "\n".join(jv.get("warnings") or [])
            has_corrected = "纠正" in warn_text and "已自动纠正" in warn_text
            has_rejected = "拒绝" in warn_text and "校验未通过" in warn_text
            # 确认导入：纠正行入库、拒绝行跳过
            rc = c.post(f"/data-packages/{tpkg}/confirm", json={"overwrite_existing": False, "selected_types": []}, headers=AH)
            jc = rc.json()
            imp_v = (jc.get("imported_counts") or {}).get("villages", 0)
            sk_v = (jc.get("skipped_counts") or {}).get("villages", 0)
            record("B10 自动校验纠正", rv.status_code == 200 and has_corrected and has_rejected
                   and rc.status_code == 200 and imp_v >= 1 and sk_v >= 1,
                   f"corrected_evt={has_corrected} rejected_evt={has_rejected} imported_v={imp_v} skipped_v={sk_v}\n  warnings={warn_text[:300]}")
        else:
            record("B10 自动校验纠正", False, f"import fail: {r.status_code} {r.text[:200]}")
    else:
        record("B10 自动校验纠正", False, "villages rows 为空，无法构造篡改样本")
except Exception as e:
    record("B10 自动校验纠正", False, repr(e)[:200])

# B11 逐一接收：第二个下级用户的包独立接收
SUB2 = login("subuser2", "Sub@123456")
SH2 = {"Authorization": "Bearer " + SUB2}
r = c.post("/supported-villages", json={"village_name": f"下级上报村B{TS}", "code": f"RPB{TS}",
           "province": "贵州省", "city": "遵义市", "county": "仁怀市"}, headers=SH2)
r = c.post("/data-packages/one-click-report", json={"remarks": f"下级乙上报{TS}"}, headers=SH2)
zip2 = r.content
rec2 = int(r.headers.get("X-Record-Count") or 0)
r = c.post("/data-packages/import", files={"file": ("report2.zip", zip2, "application/zip")}, headers=AH)
imp2 = (((r.json().get("data") or {}) or {}).get("id")) or r.json().get("package_id")
r = c.post(f"/data-packages/{imp2}/confirm", json={"overwrite_existing": False, "selected_types": []}, headers=AH)
j = r.json()
imp2_total = sum((j.get("imported_counts") or {}).values()) if isinstance(j.get("imported_counts"), dict) else 0
r = c.get("/supported-villages", params={"keyword": f"下级上报村B{TS}", "page": 1, "page_size": 5}, headers=AH)
items = (r.json().get("data") or {}).get("items", [])
record("B11 逐一接收第二包并保存", imp2 and imp2_total >= rec2 and len(items) >= 1,
       f"rec2={rec2} imported={imp2_total} found={len(items)}")

# ================= Part C 数据上报审批流 =================
r = c.post("/data-reports", json={"title": f"甲单位月度上报{TS}", "report_type": "monthly",
           "package_id": int(exported_pkg_id), "target_org_id": 1}, headers=SH)
rep_id = (r.json().get("id") or (r.json().get("data") or {}).get("id"))
record("C1 创建上报", r.status_code in (200, 201) and rep_id, f"rep={rep_id} body={r.text[:150]}")

r = c.post(f"/data-reports/{rep_id}/submit", headers=SH)
record("C2 提交上报", r.status_code == 200, f"body={r.text[:150]}")

r = c.get("/data-reports", params={"direction": "received", "page": 1, "page_size": 20}, headers=AH)
j = r.json()
_data = j.get("data") if isinstance(j.get("data"), dict) else j
items = _data.get("items") or []
has = any(str(i.get("id")) == str(rep_id) for i in items)
record("C3 上级收到上报(received)", r.status_code == 200 and has, f"found={has} total={len(items)}")

r = c.get("/data-reports/pending", headers=AH)
j = r.json()
_data = j.get("data") if isinstance(j.get("data"), dict) else j
items = _data.get("items") or []
has = any(str(i.get("id")) == str(rep_id) for i in items)
record("C4 待处理列表包含", r.status_code == 200 and has, f"found={has}")

r = c.post(f"/data-reports/{rep_id}/review", json={"action": "approve", "comment": "数据完整，通过"}, headers=AH)
st = (r.json().get("status") or (r.json().get("data") or {}).get("status"))
record("C5 审批通过", r.status_code == 200 and st in ("approved", "通过"), f"status={st} body={r.text[:150]}")

# 驳回流
r = c.post("/data-reports", json={"title": f"乙单位上报{TS}", "report_type": "monthly",
           "package_id": int(exported_pkg_id), "target_org_id": 1}, headers=SH2)
rep2 = (r.json().get("id") or (r.json().get("data") or {}).get("id"))
if rep2 is None:
    record("C6 审批驳回", False, f"create failed: {r.status_code} {r.text[:200]}")
else:
    c.post(f"/data-reports/{rep2}/submit", headers=SH2)
    r = c.post(f"/data-reports/{rep2}/review", json={"action": "reject", "comment": "数据不全", "rejection_reason": "缺少经费明细"}, headers=AH)
    st2 = (r.json().get("status") or (r.json().get("data") or {}).get("status"))
    record("C6 审批驳回", r.status_code == 200 and st2 in ("rejected", "驳回"), f"status={st2} body={r.text[:150]}")

r = c.get("/data-reports", params={"direction": "submitted", "page": 1, "page_size": 20}, headers=SH)
j = r.json()
_data = j.get("data") if isinstance(j.get("data"), dict) else j
items = _data.get("items") or []
sts = {str(i.get("id")): i.get("status") for i in items}
record("C7 下级查看上报状态", r.status_code == 200 and str(rep_id) in sts, f"statuses={sts}")

summary = {"total": len(results), "passed": sum(1 for x in results if x["passed"]),
           "failed": sum(1 for x in results if not x["passed"]), "results": results}
print("===SUMMARY===")
print(json.dumps(summary, ensure_ascii=False))
