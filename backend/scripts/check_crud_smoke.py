#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""隔离库端到端 CRUD 冒烟：登录/退出、设置保存、增删改查、上传下载、导出、备份。

## 为什么需要

check_endpoint_500.py 只发 GET，且大量端点在鉴权通过后就立刻返回 —— 它能证明
「没有 5xx」，但不能证明「写进去、读出来、删得掉」。历史上多次出现「单测绿、
真机废」的缺陷（上传端点返回裸 dict、软删后列表仍显示、审计枚举跨模块串类、
导出方法名不存在导致恒 500），都只有真实写入 + 回读才暴露。

本门禁在一次性库上起真实实例，按用户可见的主链路逐条断言：

- 登录 → 身份读取 → 登出 → 旧令牌立即失效；
- 设置项 批量写入 → 列表读回 → 单键更新 → 单键读回 → 删除 → 确认消失；
- 帮扶村 / 项目 / 政策 的 创建 → 详情 → 更新 → 软删 → 列表消失（帮扶村另验重复删除 409）；
- 文件上传 → 静态路径回读（字节级一致）；
- 报表导出（真实 xlsx，校验 ZIP 魔数）；
- 备份 创建 → 列表可见 → 完整性校验（database_verified）→ 删除 → 列表消失；
- 组织 创建（行政区划编码校验）→ 管理员绑定组织（数据包按组织隔离的前提）；
- 数据包 导出 → 下载 zip（PK 魔数）→ 回传导入（校验通过）→ 确认导入（导入导出闭环）。

任何一步不符预期即红。全部操作都在 .scratch/crud-smoke-* 的一次性库里，
进程退出即删除，绝不触碰真实数据。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import check_endpoint_500 as ep  # noqa: E402  （复用隔离库/端口/就绪等待，避免两套实现）

# 1x1 透明 PNG：够小、够真，且带明确魔数便于回读校验
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)


class SmokeFailure(Exception):
    """一步断言失败：由运行器记录为 Step(ok=False)，不中断其余场景。"""


@dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Response:
    status: int
    body: bytes
    headers: Dict[str, str]

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self) -> Any:
        try:
            return json.loads(self.text)
        except ValueError as exc:
            raise SmokeFailure("响应不是 JSON（HTTP %d）：%s" % (self.status, self.text[:200])) from exc


def expect(condition: Any, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def expect_status(resp: Response, allowed: Tuple[int, ...], what: str) -> Response:
    wanted = "/".join(str(code) for code in allowed)
    expect(
        resp.status in allowed,
        "%s 期望 HTTP %s，实际 %d：%s" % (what, wanted, resp.status, resp.text[:200]),
    )
    return resp


def payload_of(resp: Response) -> Dict[str, Any]:
    payload = resp.json()
    expect(isinstance(payload, dict), "响应信封不是对象：%s" % resp.text[:200])
    return payload


def data_of(resp: Response) -> Any:
    return payload_of(resp).get("data")


def items_of(resp: Response) -> List[Any]:
    """列表信封解包：兼容 data 为 list、data.items、顶层 items 三种形态。"""
    payload = payload_of(resp)
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    items = payload.get("items")
    return items if isinstance(items, list) else []


def ids_of(items: List[Any]) -> List[int]:
    out: List[int] = []
    for item in items:
        if isinstance(item, dict) and item.get("id") is not None:
            out.append(int(item["id"]))
    return out


def record(steps: List[Step], name: str, detail: str = "") -> None:
    steps.append(Step(name, True, detail))


def stamp() -> str:
    return time.strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6]


def created_id(resp: Response, label: str) -> int:
    data = data_of(resp)
    expect(
        isinstance(data, dict) and data.get("id") is not None,
        "%s创建响应缺少 id：%s" % (label, resp.text[:200]),
    )
    return int(data["id"])


# CSRF 双提交（见 app/middleware/csrf_middleware.py）：GET 取 raw token，
# 服务端把 HMAC 签名写进 csrftoken Cookie，写请求的 header 带 raw token。
CSRF_PATH = "/api/v1/auth/csrf-token"
CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "csrftoken"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class HttpClient:
    """极简 JSON/多部分客户端：4xx/5xx 不抛异常，交给断言判定。"""

    def __init__(self, base_url: str, token: Optional[str] = None, timeout: float = 60.0) -> None:
        self.base_url = base_url
        self.token = token
        self.timeout = timeout
        self.csrf_token: Optional[str] = None
        self.cookies: Dict[str, str] = {}
        self.org_id: Optional[int] = None
        self.db_path: Optional[str] = None

    def _cookie_header(self) -> str:
        return "; ".join("%s=%s" % (name, value) for name, value in self.cookies.items())

    def _absorb_cookies(self, headers: Dict[str, str]) -> None:
        """记住 Set-Cookie 的第一个 name=value（urllib 不维护 cookie 罐）。"""
        raw = headers.get("set-cookie", "")
        pair = raw.split(";")[0].strip()
        if "=" not in pair:
            return
        name, value = pair.split("=", 1)
        if name.strip():
            self.cookies[name.strip()] = value.strip()

    def fetch_csrf(self) -> str:
        """取 CSRF raw token，并收下服务端下发的签名 Cookie。"""
        resp = expect_status(self.get(CSRF_PATH), (200,), "CSRF 令牌获取")
        data = data_of(resp)
        expect(
            isinstance(data, dict) and isinstance(data.get("csrf_token"), str) and bool(data["csrf_token"]),
            "CSRF 响应缺少 csrf_token：%s" % resp.text[:200],
        )
        self.csrf_token = data["csrf_token"]
        expect(CSRF_COOKIE in self.cookies, "CSRF 响应未下发 csrftoken Cookie：%r" % self.cookies)
        return self.csrf_token

    def send(
        self,
        method: str,
        path: str,
        data: Optional[bytes] = None,
        content_type: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Response:
        headers: Dict[str, str] = {}
        if data is not None and content_type:
            headers["Content-Type"] = content_type
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if method.upper() not in SAFE_METHODS:
            if self.csrf_token:
                headers[CSRF_HEADER] = self.csrf_token
            cookies = self._cookie_header()
            if cookies:
                headers["Cookie"] = cookies
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as resp:
                response = Response(resp.status, resp.read(), {k.lower(): v for k, v in resp.headers.items()})
        except urllib.error.HTTPError as exc:
            body = exc.read()
            raw_headers = exc.headers.items() if exc.headers else []
            response = Response(exc.code, body, {k.lower(): v for k, v in raw_headers})
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise SmokeFailure("%s %s 连接失败：%s" % (method, path, exc)) from exc
        self._absorb_cookies(response.headers)
        return response

    def request(self, method: str, path: str, payload: Any = None, timeout: Optional[float] = None) -> Response:
        data = None
        content_type = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            content_type = "application/json"
        return self.send(method, path, data=data, content_type=content_type, timeout=timeout)

    def get(self, path: str, timeout: Optional[float] = None) -> Response:
        return self.request("GET", path, timeout=timeout)

    def post(self, path: str, payload: Any = None, timeout: Optional[float] = None) -> Response:
        return self.request("POST", path, payload, timeout=timeout)

    def put(self, path: str, payload: Any = None, timeout: Optional[float] = None) -> Response:
        return self.request("PUT", path, payload, timeout=timeout)

    def delete(self, path: str, timeout: Optional[float] = None) -> Response:
        return self.request("DELETE", path, timeout=timeout)

    def upload(
        self,
        path: str,
        filename: str,
        content: bytes,
        field: str = "file",
        form: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Response:
        boundary = "----crudsmoke" + uuid.uuid4().hex
        chunks: List[bytes] = []
        for key, value in (form or {}).items():
            chunks.append(
                (
                    '--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, key, value)
                ).encode("utf-8")
            )
        chunks.append(
            (
                '--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n" % (boundary, field, filename)
            ).encode("utf-8")
        )
        chunks.append(content)
        chunks.append(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
        return self.send(
            "POST",
            path,
            data=b"".join(chunks),
            content_type="multipart/form-data; boundary=" + boundary,
            timeout=timeout,
        )


# ── 场景 ────────────────────────────────────────────────────────────────────


def scenario_login(client: HttpClient, steps: List[Step]) -> None:
    """登录拿令牌，再读身份：证明登录链路与鉴权头都真的可用。"""
    resp = client.post(
        "/api/v1/auth/login",
        {"username": ep.FACTORY_ADMIN_USERNAME, "password": ep.FACTORY_ADMIN_PASSWORD},
    )
    expect_status(resp, (200,), "登录")
    data = data_of(resp)
    expect(isinstance(data, dict), "登录响应缺少 data：%s" % resp.text[:200])
    token = data.get("access_token") or data.get("accessToken")
    expect(isinstance(token, str) and token, "登录响应缺少 access_token：%s" % resp.text[:200])
    client.token = token
    record(steps, "登录（POST /auth/login 取令牌）")

    me = expect_status(client.get("/api/v1/auth/me"), (200,), "身份读取")
    info = data_of(me)
    expect(isinstance(info, dict), "GET /auth/me 缺少 data：%s" % me.text[:200])
    expect(
        info.get("username") == ep.FACTORY_ADMIN_USERNAME,
        "登录身份不符：%r" % info.get("username"),
    )
    expect(bool(info.get("is_superuser")), "播种管理员应为超级管理员（is_superuser=%r）" % info.get("is_superuser"))
    record(steps, "身份读取（GET /auth/me）")

    # 写请求统一要 CSRF 双提交（Cookie 签名 + header raw token），登录态不代表免校验
    client.fetch_csrf()
    record(steps, "CSRF 令牌获取（GET /auth/csrf-token）")


def scenario_organization(client: HttpClient, steps: List[Step]) -> None:
    """组织：创建（行政区划编码）→ 详情读回 → 把播种管理员绑定到该组织。

    为什么必须绑定：数据包导出/接收都以组织为隔离单位，而播种管理员默认没有组织
    （空库首启就是这样），不绑定则导出直接 400「当前用户未绑定组织」。这里直接改
    一次性库里的 users.organization_id（与生产「管理员属于某组织」一致），
    不引入额外的用户管理流程。
    """
    code = "522700"  # 黔南州：权威区划表内的市州级编码，可作为根组织
    name = "冒烟组织-" + stamp()
    created = expect_status(
        client.post("/api/v1/organizations", {"name": name, "code": code}),
        (200, 201),
        "创建组织",
    )
    org_id = created_id(created, "组织")
    detail = expect_status(client.get("/api/v1/organizations/%d" % org_id), (200,), "组织详情")
    detail_data = data_of(detail)
    expect(
        isinstance(detail_data, dict) and detail_data.get("code") == code,
        "组织详情编码不符：%s" % detail.text[:200],
    )
    record(steps, "组织创建（行政区划编码校验）", "id=%d code=%s" % (org_id, code))

    expect(isinstance(client.db_path, str) and client.db_path, "缺少一次性库路径，无法绑定管理员组织")
    conn = sqlite3.connect(str(client.db_path))
    try:
        conn.execute(
            "UPDATE users SET organization_id = ? WHERE username = ?",
            (org_id, ep.FACTORY_ADMIN_USERNAME),
        )
        conn.commit()
    finally:
        conn.close()

    me = expect_status(client.get("/api/v1/auth/me"), (200,), "组织绑定后身份读取")
    me_data = data_of(me)
    expect(
        isinstance(me_data, dict) and me_data.get("organization_id") == org_id,
        "管理员未绑定到新组织：%s" % me.text[:200],
    )
    client.org_id = org_id
    record(steps, "管理员绑定组织（数据包按组织隔离的前提）")


def scenario_settings(client: HttpClient, steps: List[Step]) -> None:
    """设置保存：批量写 → 列表读回 → 单键更新 → 单键读回 → 删除 → 确认消失。"""
    key = "crud_smoke_probe"
    client.delete("/api/v1/system/config/" + key)  # 清理上次异常退出的遗留；200/404 都接受

    batch = expect_status(
        client.put("/api/v1/system/config", {"configs": [{"key": key, "value": "on", "description": "端到端冒烟探针"}]}),
        (200,),
        "批量写入配置",
    )
    data = data_of(batch)
    expect(
        isinstance(data, dict) and data.get("updated_keys") == [key],
        "批量写入未回显 updated_keys：%s" % batch.text[:200],
    )
    record(steps, "设置项批量写入（PUT /system/config）")

    listing = expect_status(client.get("/api/v1/system/config"), (200,), "配置列表")
    values = {item.get("key"): item.get("value") for item in items_of(listing) if isinstance(item, dict)}
    expect(values.get(key) == "on", "配置列表读不到新值：%r" % values.get(key))
    record(steps, "设置项读回（GET /system/config）")

    single = expect_status(
        client.put("/api/v1/system/config/" + key + "?value=off"), (200,), "单键更新配置"
    )
    single_data = data_of(single)
    expect(
        isinstance(single_data, dict) and single_data.get("value") == "off",
        "单键更新未回显新值：%s" % single.text[:200],
    )
    got = expect_status(client.get("/api/v1/system/config/" + key), (200,), "单键读取配置")
    got_data = data_of(got)
    expect(
        isinstance(got_data, dict) and got_data.get("value") == "off",
        "单键读取不是更新后的值：%s" % got.text[:200],
    )
    record(steps, "设置项单键更新 + 读回（PUT/GET /system/config/{key}）")

    expect_status(client.delete("/api/v1/system/config/" + key), (200,), "删除配置")
    gone = client.get("/api/v1/system/config/" + key)
    expect(gone.status == 404, "删除后仍能读到配置项（HTTP %d）" % gone.status)
    record(steps, "设置项删除（回退默认）")


def scenario_village_crud(client: HttpClient, steps: List[Step]) -> None:
    """帮扶村：创建 → 详情 → 更新 → 软删 → 列表消失 → 重复删除 409。"""
    name = "冒烟帮扶村-" + stamp()
    created = expect_status(
        client.post("/api/v1/supported-villages", {"village_name": name, "province": "贵州省", "county": "都匀市"}),
        (200, 201),
        "创建帮扶村",
    )
    village_id = created_id(created, "帮扶村")
    record(steps, "帮扶村创建", "id=%d" % village_id)

    detail = expect_status(client.get("/api/v1/supported-villages/%d" % village_id), (200,), "帮扶村详情")
    detail_data = data_of(detail)
    expect(
        isinstance(detail_data, dict) and detail_data.get("village_name") == name,
        "帮扶村详情村名不符：%s" % detail.text[:200],
    )
    record(steps, "帮扶村详情读回")

    renamed = name + "（改）"
    expect_status(
        client.put("/api/v1/supported-villages/%d" % village_id, {"village_name": renamed}),
        (200,),
        "更新帮扶村",
    )
    updated = expect_status(client.get("/api/v1/supported-villages/%d" % village_id), (200,), "帮扶村更新后详情")
    updated_data = data_of(updated)
    expect(
        isinstance(updated_data, dict) and updated_data.get("village_name") == renamed,
        "帮扶村更新未生效：%s" % updated.text[:200],
    )
    record(steps, "帮扶村更新生效")

    expect_status(client.delete("/api/v1/supported-villages/%d" % village_id), (200,), "删除帮扶村")
    again = client.delete("/api/v1/supported-villages/%d" % village_id)
    expect(again.status == 409, "重复软删应 409（回收站守卫），实际 %d" % again.status)
    record(steps, "帮扶村软删 + 重复删除守卫")

    listing = expect_status(
        client.get("/api/v1/supported-villages?page=1&page_size=100"), (200,), "帮扶村列表"
    )
    expect(village_id not in ids_of(items_of(listing)), "软删后列表仍返回 id=%d" % village_id)
    record(steps, "软删后列表过滤")


def scenario_project_crud(client: HttpClient, steps: List[Step]) -> None:
    """项目：创建（201）→ 详情 → 更新进度 → 软删 → 列表消失。"""
    name = "冒烟项目-" + stamp()
    created = expect_status(
        client.post("/api/v1/projects", {"name": name, "budget": 10000, "progress": 0}),
        (201,),
        "创建项目",
    )
    project_id = created_id(created, "项目")
    record(steps, "项目创建", "id=%d" % project_id)

    expect_status(client.put("/api/v1/projects/%d" % project_id, {"progress": 30}), (200,), "更新项目")
    detail = expect_status(client.get("/api/v1/projects/%d" % project_id), (200,), "项目详情")
    detail_data = data_of(detail)
    expect(
        isinstance(detail_data, dict) and int(detail_data.get("progress") or 0) == 30,
        "项目进度更新未生效：%s" % detail.text[:200],
    )
    record(steps, "项目更新 + 详情读回")

    expect_status(client.delete("/api/v1/projects/%d" % project_id), (200,), "删除项目")
    listing = expect_status(client.get("/api/v1/projects?page=1&page_size=100"), (200,), "项目列表")
    expect(project_id not in ids_of(items_of(listing)), "软删后列表仍返回项目 id=%d" % project_id)
    record(steps, "项目软删 + 列表过滤")


def scenario_policy_crud(client: HttpClient, steps: List[Step]) -> None:
    """政策：创建 → 详情 → 更新标题 → 软删 → 列表消失。"""
    title = "冒烟政策-" + stamp()
    created = expect_status(
        client.post("/api/v1/policies", {"title": title, "content": "端到端冒烟政策正文"}),
        (200, 201),
        "创建政策",
    )
    policy_id = created_id(created, "政策")
    record(steps, "政策创建", "id=%d" % policy_id)

    detail = expect_status(client.get("/api/v1/policies/%d" % policy_id), (200,), "政策详情")
    detail_data = data_of(detail)
    expect(
        isinstance(detail_data, dict) and detail_data.get("title") == title,
        "政策详情标题不符：%s" % detail.text[:200],
    )
    record(steps, "政策详情读回")

    renamed = title + "（改）"
    expect_status(client.put("/api/v1/policies/%d" % policy_id, {"title": renamed}), (200,), "更新政策")
    updated = expect_status(client.get("/api/v1/policies/%d" % policy_id), (200,), "政策更新后详情")
    updated_data = data_of(updated)
    expect(
        isinstance(updated_data, dict) and updated_data.get("title") == renamed,
        "政策更新未生效：%s" % updated.text[:200],
    )
    record(steps, "政策更新生效")

    expect_status(client.delete("/api/v1/policies/%d" % policy_id), (200,), "删除政策")
    listing = expect_status(client.get("/api/v1/policies?page=1&page_size=100"), (200,), "政策列表")
    expect(policy_id not in ids_of(items_of(listing)), "软删后列表仍返回政策 id=%d" % policy_id)
    record(steps, "政策软删 + 列表过滤")


def scenario_upload_download(client: HttpClient, steps: List[Step]) -> None:
    """上传下载：上传 PNG → 按返回的静态 url 回读 → 字节级一致。"""
    uploaded = expect_status(
        client.upload("/api/v1/files/upload", "crud-smoke.png", PNG_1X1),
        (200, 201),
        "上传文件",
    )
    data = data_of(uploaded)
    expect(isinstance(data, dict), "上传响应缺少 data：%s" % uploaded.text[:200])
    url = data.get("url")
    expect(isinstance(url, str) and url.startswith("/"), "上传响应 url 非法：%r" % url)
    expect(int(data.get("file_size") or 0) == len(PNG_1X1), "上传回显文件大小不符：%r" % data.get("file_size"))
    record(steps, "文件上传", str(url))

    fetched = expect_status(client.get(str(url)), (200,), "回读上传文件")
    expect(fetched.body == PNG_1X1, "回读字节与上传不一致（%d vs %d 字节）" % (len(fetched.body), len(PNG_1X1)))
    record(steps, "上传文件静态回读（字节一致）")


def scenario_export(client: HttpClient, steps: List[Step]) -> None:
    """导出：真实 xlsx（ZIP 魔数 + 合理体积）。"""
    resp = expect_status(
        client.post("/api/v1/reports/export/excel", {"year": 2026}, timeout=240),
        (200,),
        "导出 Excel 报表",
    )
    expect(resp.body[:2] == b"PK", "导出内容不是 xlsx（缺少 ZIP 魔数）：%r" % resp.body[:8])
    expect(len(resp.body) > 1000, "导出文件过小：%d 字节" % len(resp.body))
    record(steps, "报表导出（POST /reports/export/excel）", "%d 字节" % len(resp.body))


def scenario_data_package(client: HttpClient, steps: List[Step]) -> None:
    """数据包：导出 → 下载 zip → 回传导入 → 确认导入（导入导出闭环）。

    这几步走的是用户真实的「上级导出 → 介质传递 → 下级接收」链路：
    导出接口 response_model 直出（无信封），所以这里用 payload_of 而不是 data_of；
    org_id 从详情接口取（导入必须显式指定目标组织，admin 播种账号没有默认组织）。
    """
    org_id = client.org_id
    expect(isinstance(org_id, int), "数据包场景前置：管理员尚未绑定组织（见「组织」场景）")

    village_name = "冒烟数据包村-" + stamp()
    expect_status(
        client.post("/api/v1/supported-villages", {"village_name": village_name}),
        (200, 201),
        "数据包准备：创建待导出帮扶村",
    )

    exported = expect_status(
        client.post(
            "/api/v1/data-packages/export",
            {"org_id": int(org_id), "data_types": ["villages"], "description": "端到端冒烟数据包"},
            timeout=300,
        ),
        (200,),
        "导出数据包",
    )
    export_data = payload_of(exported)
    package_id = export_data.get("package_id")
    expect(isinstance(package_id, int), "导出响应缺少 package_id：%s" % exported.text[:200])
    expect(int(export_data.get("file_size") or 0) > 0, "导出包大小为 0：%r" % export_data.get("file_size"))
    manifest = export_data.get("manifest") or {}
    counts = manifest.get("record_counts") or {}
    expect(int(counts.get("villages") or 0) >= 1, "导出包未包含待导出帮扶村：%r" % counts)
    record(steps, "数据包导出", "package_id=%d villages=%s" % (int(package_id), counts.get("villages")))

    downloaded = expect_status(
        client.get("/api/v1/data-packages/%d/download" % int(package_id), timeout=300),
        (200,),
        "下载数据包",
    )
    expect(downloaded.body[:2] == b"PK", "数据包不是 zip（缺少 PK 魔数）：%r" % downloaded.body[:8])
    record(steps, "数据包下载", "%d 字节" % len(downloaded.body))

    detail = expect_status(
        client.get("/api/v1/data-packages/%d" % int(package_id)), (200,), "数据包详情"
    )
    detail_org = payload_of(detail).get("org_id")
    expect(detail_org == org_id, "导出包组织归属不符：%r（期望 %r）" % (detail_org, org_id))

    imported = expect_status(
        client.upload(
            "/api/v1/data-packages/import?org_id=%d&force=true" % int(org_id),
            "crud-smoke-package.zip",
            downloaded.body,
            timeout=600,
        ),
        (200,),
        "导入数据包",
    )
    import_data = payload_of(imported)
    imported_id = import_data.get("package_id")
    expect(isinstance(imported_id, int), "导入响应缺少 package_id：%s" % imported.text[:200])
    validation = import_data.get("validation")
    expect(isinstance(validation, dict), "导入响应缺少 validation：%s" % imported.text[:300])
    expect(validation.get("is_valid") is True, "导入校验未通过：%s" % imported.text[:400])
    record(steps, "数据包导入（校验通过）", "package_id=%d" % int(imported_id))

    confirmed = expect_status(
        client.post(
            "/api/v1/data-packages/%d/confirm" % int(imported_id),
            {"confirm": True, "overwrite_existing": False},
            timeout=600,
        ),
        (200,),
        "确认导入数据包",
    )
    confirm_data = payload_of(confirmed)
    expect(confirm_data.get("success") is True, "确认导入失败：%s" % confirmed.text[:400])
    imported_counts = confirm_data.get("imported_counts") or {}
    skipped_counts = confirm_data.get("skipped_counts") or {}
    touched = sum(int(value) for value in list(imported_counts.values()) + list(skipped_counts.values()))
    expect(touched >= 1, "确认导入未处理任何记录：imported=%r skipped=%r" % (imported_counts, skipped_counts))
    record(
        steps,
        "确认导入（冲突策略生效）",
        "imported=%r skipped=%r" % (imported_counts, skipped_counts),
    )


def scenario_backup(client: HttpClient, steps: List[Step]) -> None:
    """备份：创建 → 列表可见 → 完整性校验 → 删除 → 列表消失。"""
    created = expect_status(
        client.post(
            "/api/v1/system/backup",
            {"description": "端到端冒烟备份", "include_uploads": True, "trigger": "manual"},
            timeout=600,
        ),
        (200,),
        "创建备份",
    )
    data = data_of(created)
    expect(isinstance(data, dict), "备份创建响应缺少 data：%s" % created.text[:200])
    filename = data.get("file_name")
    expect(isinstance(filename, str) and filename, "备份创建响应缺少 file_name：%s" % created.text[:200])
    expect(int(data.get("file_size") or 0) > 0, "备份文件大小为 0：%r" % data.get("file_size"))
    record(steps, "备份创建", str(filename))

    names = _backup_names(client)
    expect(str(filename) in names, "备份列表查不到刚创建的文件：%s" % sorted(names))
    record(steps, "备份列表可见")

    quoted = urllib.parse.quote(str(filename))
    verified = expect_status(
        client.post("/api/v1/system/backup/verify/" + quoted, timeout=240), (200,), "校验备份"
    )
    verify_data = data_of(verified)
    expect(isinstance(verify_data, dict), "备份校验响应缺少 data：%s" % verified.text[:200])
    expect(
        verify_data.get("status") == "ok" and verify_data.get("database_verified") is True,
        "备份完整性校验未通过：%s" % verified.text[:300],
    )
    record(steps, "备份完整性校验（database_verified）")

    expect_status(client.delete("/api/v1/system/backup/" + quoted, timeout=180), (200,), "删除备份")
    expect(str(filename) not in _backup_names(client), "备份删除后列表仍可见：%s" % str(filename))
    record(steps, "备份删除 + 列表消失")


def _backup_names(client: HttpClient) -> List[str]:
    listing = expect_status(client.get("/api/v1/system/backup"), (200,), "备份列表")
    return [str(item.get("file_name")) for item in items_of(listing) if isinstance(item, dict)]


def scenario_logout(client: HttpClient, steps: List[Step]) -> None:
    """登出：旧令牌必须立刻失效（token_version 递增 + 黑名单）。"""
    expect_status(client.post("/api/v1/auth/logout"), (200,), "登出")
    record(steps, "登出（POST /auth/logout）")
    after = client.get("/api/v1/auth/me")
    expect(after.status == 401, "登出后旧令牌仍可用（HTTP %d）" % after.status)
    record(steps, "登出后令牌立即失效")


SCENARIOS: List[Tuple[str, Any]] = [
    ("登录", scenario_login),
    ("组织与管理员绑定", scenario_organization),
    ("设置保存", scenario_settings),
    ("帮扶村增删改查", scenario_village_crud),
    ("项目增删改查", scenario_project_crud),
    ("政策增删改查", scenario_policy_crud),
    ("上传下载", scenario_upload_download),
    ("报表导出", scenario_export),
    ("数据包导入导出", scenario_data_package),
    ("备份", scenario_backup),
    ("登出", scenario_logout),
]


# ── 运行器 ──────────────────────────────────────────────────────────────────


def scratch_dir() -> Path:
    """隔离的可写落点（不用 %TEMP%：受限环境常不可写）。"""
    base = BACKEND.parent / ".scratch"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(os.path.join(str(base), "crud-smoke-" + uuid.uuid4().hex[:12]))
    scratch.mkdir(parents=True, exist_ok=False)
    return scratch


def isolated_env(scratch: Path) -> Dict[str, str]:
    """一次性库 + 隔离数据目录。

    DATABASE_URL 用绝对 sqlite URL；库文件名沿用生产的 rural_revitalization.db，
    这样备份包的 arcname（data/rural_revitalization.db）与生产一致，
    verify 的数据库完整性分支才会真的被执行到。
    """
    data_dir = scratch / "data"
    cache_dir = scratch / "cache"
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DATA_DIR"] = str(data_dir)
    env["CACHE_DIR"] = str(cache_dir)
    env["DATABASE_URL"] = "sqlite:///" + (data_dir / "rural_revitalization.db").as_posix()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def start_server(env: Dict[str, str], scratch: Path, port: int) -> subprocess.Popen:
    log_path = scratch / "server.log"
    with open(log_path, "wb") as log_file:
        return subprocess.Popen(
            [
                ep.venv_python(),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(BACKEND),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )


def stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)


def database_file(env: Dict[str, str]) -> Path:
    return Path(env["DATABASE_URL"][len("sqlite:///"):])


def run_scenarios(client: HttpClient, steps: List[Step], scenarios: List[Tuple[str, Any]]) -> List[Step]:
    """顺序跑场景：单个场景断言失败只记录，不拦断后续步骤（一次跑出全部问题）。"""
    for name, scenario in scenarios:
        try:
            scenario(client, steps)
        except SmokeFailure as exc:
            steps.append(Step(name, False, str(exc)))
    return steps


def print_report(steps: List[Step], verbose: bool) -> None:
    for step in steps:
        if verbose or not step.ok:
            mark = "[ok]  " if step.ok else "[FAIL]"
            suffix = (" — " + step.detail) if step.detail else ""
            print("  %s %s%s" % (mark, step.name, suffix))


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="隔离库端到端 CRUD 冒烟（登录/设置/增删改查/上传/导出/数据包导入导出/备份/登出）")
    parser.add_argument("--port", type=int, default=8801)
    parser.add_argument("--verbose", action="store_true", help="打印每一步（含通过项）")
    parser.add_argument("--keep-server", action="store_true", help="调试：结束后不杀进程、不删目录")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    scratch = scratch_dir()
    env = isolated_env(scratch)
    proc: Optional[subprocess.Popen] = None
    steps: List[Step] = []
    base_url = ""
    try:
        try:
            ep.prepare_schema(env)
            port = ep._pick_port(args.port)
            base_url = "http://127.0.0.1:%d" % port
            proc = start_server(env, scratch, port)
            ep.wait_ready(base_url)
            boot_token = ep.grant_admin_token(base_url, database_file(env))
        except (SmokeFailure, RuntimeError) as exc:
            print("[gate:crud_smoke] FAIL (实例准备失败：%s)" % exc)
            return 1

        client = HttpClient(base_url, token=boot_token)
        client.db_path = str(database_file(env))
        run_scenarios(client, steps, SCENARIOS)

        failures = [step for step in steps if not step.ok]
        print_report(steps, args.verbose)
        if failures:
            print("[gate:crud_smoke] FAIL (%d steps, %d failed)" % (len(steps), len(failures)))
            return 1
        print("[gate:crud_smoke] OK (isolation DB, modes=admin, %d steps)" % len(steps))
        return 0
    finally:
        if args.keep_server:
            print("[keep] 实例仍在 %s，临时目录 %s" % (base_url, scratch))
        else:
            if proc is not None:
                stop_server(proc)
            if not ep.cleanup_scratch(scratch):
                print("[warn] 临时目录未能删除：%s" % scratch)


if __name__ == "__main__":
    sys.exit(main())
