"""帮扶村年度数据回归测试（问题2 根因修复验证）

覆盖三处修复：
1. 遗留路由 POST /{id}/committee —— 按年隔离 + 成员子表正确落库
   （旧实现不带 year 过滤导致跨年覆盖，且对 members 关系属性 setattr dict → 500）
2. 变更历史字段级明细落库 —— record_changes 末尾 safe_commit
   （旧实现只 db.add 不 commit，业务 commit 之后才调用 → 明细全丢）
3. 列表返回 latest_year —— 列表页「最近年度」列数据源
"""
import pytest


def _create_village(client, name="测试村"):
    resp = client.post(
        "/api/v1/supported-villages",
        json={
            "village_name": name,
            "province": "贵州省",
            "city": "毕节市",
            "county": "大方县",
            "department": "某部",
            "support_unit": "某单位",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    data = body.get("data") or body
    return data["id"]


class TestCommitteeLegacyRoute:
    """遗留 committee 路由：成员保存 + 按年隔离。"""

    def test_members_saved_and_year_isolated(self, auth_client):
        if auth_client is None:
            pytest.skip("client fixture unavailable")
        vid = _create_village(auth_client)

        r1 = auth_client.post(
            f"/api/v1/supported-villages/{vid}/committee",
            json={
                "year": 2024,
                "overview": "2024年概况",
                "members": [
                    {"name": "张三", "position": "主任", "phone": "13800000001",
                     "isVeteran": True, "remark": ""}
                ],
            },
        )
        assert r1.status_code == 200, r1.text

        r2 = auth_client.post(
            f"/api/v1/supported-villages/{vid}/committee",
            json={
                "year": 2025,
                "overview": "2025年概况",
                "members": [
                    {"name": "李四", "position": "书记", "phone": "13800000002",
                     "isVeteran": False, "remark": ""},
                    {"name": "王五", "position": "委员", "phone": "13800000003",
                     "isVeteran": False, "remark": ""},
                ],
            },
        )
        assert r2.status_code == 200, r2.text

        g2024 = auth_client.get(f"/api/v1/supported-villages/{vid}/yearly/2024")
        assert g2024.status_code == 200
        c2024 = g2024.json()["data"]["committee"]
        assert c2024 is not None, "2024 年 committee 应存在"
        assert c2024["overview"] == "2024年概况"
        assert len(c2024["members"]) == 1
        assert c2024["members"][0]["name"] == "张三"

        g2025 = auth_client.get(f"/api/v1/supported-villages/{vid}/yearly/2025")
        c2025 = g2025.json()["data"]["committee"]
        assert c2025 is not None, "2025 年 committee 应存在"
        assert c2025["overview"] == "2025年概况"
        assert len(c2025["members"]) == 2

        # 再查 2024，确认未被 2025 年保存覆盖（旧 bug：跨年覆盖）
        g2024b = auth_client.get(f"/api/v1/supported-villages/{vid}/yearly/2024")
        c2024b = g2024b.json()["data"]["committee"]
        assert c2024b["overview"] == "2024年概况"
        assert len(c2024b["members"]) == 1


class TestChangeHistoryFieldDetails:
    """变更历史：字段级明细必须落库（record_changes 补 commit 修复验证）。"""

    def test_update_produces_field_level_changes(self, auth_client):
        if auth_client is None:
            pytest.skip("client fixture unavailable")
        vid = _create_village(auth_client, name="变更前村名")

        r = auth_client.put(
            f"/api/v1/supported-villages/{vid}",
            json={"village_name": "变更后村名"},
        )
        assert r.status_code == 200, r.text

        h = auth_client.get(f"/api/v1/supported-villages/{vid}/change-history")
        assert h.status_code == 200, h.text
        items = h.json()["data"]["items"]
        assert len(items) >= 1, "变更历史应至少有记录"
        # 至少一条记录带字段级明细（旧 bug：changes 永远为空）
        detailed = [it for it in items if it.get("changes")]
        assert detailed, f"变更历史缺少字段级明细: {items}"
        # 找到 update 记录中 villageName 的 old→new 明细（序列化键为 field）
        name_changes = [
            c
            for it in detailed
            for c in it["changes"]
            if c.get("field") in ("villageName", "village_name") and c.get("change_type") == "update"
        ]
        assert name_changes, f"应记录 village_name 的 update 变更: {detailed}"
        assert name_changes[0]["new_value"] == "变更后村名"


class TestLatestYear:
    """列表返回 latest_year（列表页「最近年度」列数据源）。"""

    def test_list_contains_latest_year(self, auth_client):
        if auth_client is None:
            pytest.skip("client fixture unavailable")
        vid = _create_village(auth_client)

        r = auth_client.post(
            f"/api/v1/supported-villages/{vid}/yearly/2023/income",
            json={"perCapitaIncome": 12345.0},
        )
        assert r.status_code == 200, r.text

        lst = auth_client.get("/api/v1/supported-villages", params={"page_size": 100})
        assert lst.status_code == 200, lst.text
        items = lst.json()["data"]["items"]
        target = next((v for v in items if v["id"] == vid), None)
        assert target is not None
        assert target.get("latest_year") == 2023 or target.get("latestYear") == 2023, (
            f"latest_year 应为 2023: { {k: v for k, v in target.items() if 'year' in k.lower()} }"
        )
