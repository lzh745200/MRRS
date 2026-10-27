#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W21 菜单对齐门禁 —— 单一菜单源 v2（契约 §7 规则 A~E）

数据源：
- 唯一菜单源：`backend/app/api/v1/menus.py` 的 `MENU_DEFINITIONS` / `MENU_SECTIONS`
  （用 AST literal_eval 解析，不 import 后端应用，避免引入运行期依赖）；
- 前端已注册路由：`frontend/src/router/index.ts`（读取 path / alias / meta.menuKey）。

**不再读取** `frontend/src/config/menu-config.ts`（W21 已删除该第二套菜单配置）。

规则：
A. 后端每个带 path 的条目（page / console / group children / console tabs.path）
   必须命中前端已注册路由（含 alias 与可选参数段），否则 FAIL；
B. 前端每个 `meta.menuKey` 必须存在于后端 key 集合（含 children / tabs / 历史兼容 key），
   否则 FAIL；
C. 后端每个 key 必须“被前端消费”（防孤儿 key）：
   ① 某路由 meta.menuKey 命中；
   ② group / console 的任一子项命中（children 递归、tabs 见 ③）；
   ③ console tab 的 path 在前端路由中存在；
   历史兼容 key（section=None + legacy=True，无导航出口，仅用于权限包/历史配置校验）
   豁免本规则并列入 INFO；
D. 同一条路径不得出现两个菜单入口（page / children / tabs 全局唯一；
   契约允许的 redirect 路径豁免表见 REDIRECT_PATH_EXEMPT），否则 FAIL；
E. section key 唯一、section 内 order 单调（允许重复但 WARN，倒序 FAIL）；
   并校验条目结构（kind / path / children / tabs 与 key 唯一性），否则 FAIL。

退出码语义不变：0=通过，1=存在不一致。CI 调用方式不变：
    python scripts/check_menu_alignment.py
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_MENUS = ROOT / "backend" / "app" / "api" / "v1" / "menus.py"
FRONTEND_ROUTER = ROOT / "frontend" / "src" / "router" / "index.ts"

# 规则 D 的 redirect 路径豁免（契约 §7：/system/help 这类 redirect 除外）
# 后端菜单不直接下发 redirect 路径，此处留空表；如后续确有“同一路径双入口”的
# 兼容重定向需求，必须在此登记并写明理由。
REDIRECT_PATH_EXEMPT: frozenset[str] = frozenset()

VALID_KINDS = frozenset({"page", "group", "console"})

_ASSIGN_NAMES = ("MENU_DEFINITIONS", "MENU_SECTIONS")


def _load_backend_source(path: Path) -> dict:
    """用 AST literal_eval 读取后端菜单源的纯字面量定义（不 import 应用）。"""
    if not path.exists():
        raise SystemExit(f"[FAIL] 后端菜单源不存在: {path}")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in _ASSIGN_NAMES:
                values[node.target.id] = ast.literal_eval(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _ASSIGN_NAMES:
                    values[target.id] = ast.literal_eval(node.value)
    for name in _ASSIGN_NAMES:
        if name not in values:
            raise SystemExit(f"[FAIL] 后端菜单源缺少顶层字面量定义: {name}")
    return values


def _iter_entries(definitions: list) -> list:
    """展开全部条目，返回 [(entry, role)]；role ∈ top / child / tab。"""
    flattened = []
    for entry in definitions:
        flattened.append((entry, "top"))
        for child in entry.get("children") or []:
            flattened.append((child, "child"))
        for tab in entry.get("tabs") or []:
            flattened.append((tab, "tab"))
    return flattened


def _load_router(path: Path) -> dict:
    """解析前端路由：返回 {paths, menu_keys, path_titles}（path 含 alias）。

    ``path_titles`` 为「路由 path → meta.title」，供规则 F 比对菜单 label
    （meta.title 驱动面包屑与 document.title，与侧栏文案不一致会造成同页两名）。
    """
    if not path.exists():
        raise SystemExit(f"[FAIL] 前端路由文件不存在: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")

    route_paths: list[str] = []
    menu_keys: set[str] = set()
    path_titles: dict[str, str] = {}
    matches = list(re.finditer(r"\bpath:\s*['\"]([^'\"]+)['\"]", text))
    for index, match in enumerate(matches):
        # 本路由对象的文本片段：从 path 到下一个 path（足够覆盖同一对象的 meta/alias）
        chunk_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_prefix = text[line_start:match.start()].strip()
        if line_prefix.startswith("//") or line_prefix.startswith("*"):
            continue  # 跳过注释中的 path 示例
        route_path = match.group(1)
        chunk = text[match.end():chunk_end]
        route_paths.append(route_path)
        route_paths.extend(re.findall(r"\balias:\s*['\"]([^'\"]+)['\"]", chunk))
        menu_keys.update(re.findall(r"\bmenuKey:\s*['\"]([A-Za-z0-9_-]+)['\"]", chunk))
        title_match = re.search(r"\btitle:\s*['\"]([^'\"]+)['\"]", chunk)
        if title_match:
            path_titles.setdefault(route_path, title_match.group(1))

    # 兜底：菜单 key 不依赖路由片段切分，全文再扫一遍（防止 meta 位于 children 之后）
    menu_keys.update(re.findall(r"\bmenuKey:\s*['\"]([A-Za-z0-9_-]+)['\"]", text))
    return {"paths": route_paths, "menu_keys": menu_keys, "path_titles": path_titles}


def _path_matcher(route: str):
    """把前端路由 path 编译为匹配正则：:id -> 一段，:id? -> 可选段。"""
    route = route.rstrip("/")
    pattern = ""
    for segment in [s for s in route.split("/") if s]:
        if segment.startswith(":"):
            pattern += "(?:/[^/]+)?" if segment.endswith("?") else "/[^/]+"
        else:
            pattern += "/" + re.escape(segment)
    return re.compile("^" + (pattern or "/") + "/?$")


def _build_route_matchers(route_paths: list[str]) -> list:
    matchers = []
    for route in route_paths:
        # 排除通配/catch-all 与正则约束路由（如 /:pathMatch(.*)*）
        if not route.startswith("/") or "*" in route or "(" in route:
            continue
        matchers.append(_path_matcher(route))
    return matchers


def _path_registered(path: str, matchers: list) -> bool:
    if not path:
        return False
    normalized = path.rstrip("/") or "/"
    return any(matcher.match(normalized) for matcher in matchers)


def _check_rule_a(entries: list, matchers: list) -> list:
    errors = []
    for entry, _role in entries:
        path = entry.get("path")
        if not path:
            continue
        if not _path_registered(str(path), matchers):
            errors.append(
                f"[A] 后端菜单 '{entry.get('key')}' 的 path '{path}' 在前端路由中不存在（点击将 404）"
            )
    return errors


def _check_rule_b(entries: list, router_menu_keys: set) -> list:
    backend_keys = {entry.get("key") for entry, _role in entries}
    errors = []
    for menu_key in sorted(router_menu_keys):
        if menu_key not in backend_keys:
            errors.append(f"[B] 前端路由 meta.menuKey '{menu_key}' 在后端 MENU_DEFINITIONS 中不存在")
    return errors


def _check_rule_c(entries: list, router_menu_keys: set, matchers: list) -> tuple:
    """返回 (errors, legacy_exempt_keys)。"""

    def consumed(entry: dict, role: str) -> bool:
        key = entry.get("key")
        if key in router_menu_keys:
            return True
        kind = entry.get("kind")
        if kind == "group":
            return any(consumed(child, "child") for child in entry.get("children") or [])
        if kind == "console":
            return any(consumed(tab, "tab") for tab in entry.get("tabs") or [])
        if role == "tab":
            return _path_registered(str(entry.get("path") or ""), matchers)
        return False

    errors = []
    legacy_exempt: list[str] = []
    for entry, role in entries:
        if entry.get("legacy"):
            legacy_exempt.append(str(entry.get("key")))
            continue
        if not consumed(entry, role):
            errors.append(
                f"[C] 后端菜单 key '{entry.get('key')}' 未被前端消费"
                "（无路由 meta.menuKey 命中，且不是可消费的 group/console/tab）"
            )
    return errors, legacy_exempt


def _check_rule_d(entries: list) -> list:
    errors = []
    seen: dict[str, str] = {}
    for entry, _role in entries:
        path = entry.get("path")
        if not path:
            continue
        path = str(path)
        if path in REDIRECT_PATH_EXEMPT:
            continue
        if path in seen:
            errors.append(
                f"[D] 路径 '{path}' 出现两个菜单入口: '{seen[path]}' 与 '{entry.get('key')}'"
            )
            continue
        seen[path] = str(entry.get("key"))
    return errors


def _check_sections_definition(sections: list) -> list:
    """section key 唯一 + 板块 order 唯一且升序（便于前端稳定排序）"""
    errors = []
    section_keys = [section.get("key") for section in sections]
    if len(set(section_keys)) != len(section_keys):
        errors.append(f"[E] MENU_SECTIONS 存在重复 section key: {section_keys}")
    section_orders = [int(section.get("order") or 0) for section in sections]
    if section_orders != sorted(section_orders) or len(set(section_orders)) != len(section_orders):
        errors.append(f"[E] MENU_SECTIONS 的 order 必须唯一且升序: {section_orders}")
    return errors


def _check_kind_structure(key: str, kind: str, entry: dict) -> list:
    """单个条目按 kind 校验必填字段（契约 §2 字段规则）"""
    errors = []
    if kind == "page" and not entry.get("path"):
        errors.append(f"[E] page '{key}' 缺少 path")
    elif kind == "group":
        if entry.get("path"):
            errors.append(f"[E] group '{key}' 不允许 path（契约 §2）")
        if not entry.get("children"):
            errors.append(f"[E] group '{key}' 缺少 children")
    elif kind == "console":
        if not entry.get("path"):
            errors.append(f"[E] console '{key}' 缺少 path")
        if not entry.get("tabs"):
            errors.append(f"[E] console '{key}' 缺少 tabs")
    return errors


def _check_entry_structure(key: str, entry: dict, role: str, known_sections: set) -> list:
    """单个条目结构校验（tab / legacy / 普通条目）"""
    errors: list[str] = []
    if role == "tab":
        if not entry.get("path"):
            errors.append(f"[E] console tab '{key}' 缺少 path")
        return errors
    if entry.get("legacy"):
        # 历史兼容 key：约定 section=None 且无 path（不参与 sections 渲染）
        if entry.get("section") is not None or entry.get("path"):
            errors.append(f"[E] 历史兼容 key '{key}' 必须 section=None 且不带 path")
        return errors
    kind = entry.get("kind")
    if kind not in VALID_KINDS:
        errors.append(f"[E] 菜单 '{key}' 的 kind '{kind}' 非法（仅 page/group/console）")
        return errors
    errors.extend(_check_kind_structure(key, kind, entry))
    section = entry.get("section")
    if section is not None and section not in known_sections:
        errors.append(f"[E] 菜单 '{key}' 的 section '{section}' 未在 MENU_SECTIONS 中定义")
    return errors


def _check_section_orders(definitions: list, sections: list) -> tuple:
    """section 内顶层条目 order 单调（重复 WARN，倒序 FAIL）"""
    errors = []
    warnings = []
    for section in sections:
        section_key = section.get("key")
        items = [entry for entry, role in _iter_entries(definitions)
                 if role == "top" and entry.get("section") == section_key]
        orders = [int(entry.get("order") or 0) for entry in items]
        if orders != sorted(orders):
            errors.append(f"[E] section '{section_key}' 内 order 非单调升序: {orders}")
        duplicated_orders = {order for order in orders if orders.count(order) > 1}
        if duplicated_orders:
            warnings.append(
                f"[E] section '{section_key}' 内存在重复 order（允许，仅提示）: {sorted(duplicated_orders)}"
            )
    return errors, warnings


def _check_rule_e(definitions: list, sections: list) -> tuple:
    """返回 (errors, warnings)。"""
    errors = _check_sections_definition(sections)
    known_sections = {section.get("key") for section in sections}
    seen_keys: dict[str, str] = {}
    for entry, role in _iter_entries(definitions):
        key = entry.get("key")
        if key in seen_keys:
            errors.append(f"[E] 菜单 key 重复: '{key}'（{seen_keys[key]} 与 {role}）")
        else:
            seen_keys[key] = role
        errors.extend(_check_entry_structure(key, entry, role, known_sections))
    order_errors, warnings = _check_section_orders(definitions, sections)
    errors.extend(order_errors)
    return errors, warnings


def _check_rule_f(entries: list, path_titles: dict) -> list:
    """规则 F（2026-10-27 新增）：菜单 label ↔ 前端路由 meta.title 必须一致。

    缘起：``data-overview`` 侧栏叫「数据概览」、路由 meta.title 却写「数据管理」，
    于是**面包屑与 document.title 显示一个名字、侧栏与页头显示另一个名字**，
    同一页面两个称谓。同类不一致当时共 10 处，全部是 meta.title 落后于菜单改名。

    口径：``menus.py`` 是全站唯一菜单源 → 菜单 ``label`` 为准；只比对**两侧都存在**
    的条目（未声明 meta.title 的路由由规则 A/B 覆盖，不在本规则范围）。
    """
    errors: list[str] = []
    for entry, _role in entries:
        path = entry.get("path")
        label = entry.get("label")
        if not path or not label:
            continue
        title = path_titles.get(path)
        if title is None:
            continue
        if title != label:
            errors.append(
                f"[F] {path}: 菜单 label「{label}」≠ 路由 meta.title「{title}」"
                f"（面包屑/文档标题会与侧栏不一致）"
            )
    return errors


def main() -> int:
    source = _load_backend_source(BACKEND_MENUS)
    definitions = source["MENU_DEFINITIONS"]
    sections = source["MENU_SECTIONS"]
    router = _load_router(FRONTEND_ROUTER)

    entries = _iter_entries(definitions)
    matchers = _build_route_matchers(router["paths"])

    errors: list[str] = []
    warnings: list[str] = []

    rule_a = _check_rule_a(entries, matchers)
    rule_b = _check_rule_b(entries, router["menu_keys"])
    rule_c, legacy_exempt = _check_rule_c(entries, router["menu_keys"], matchers)
    rule_d = _check_rule_d(entries)
    rule_e, rule_e_warnings = _check_rule_e(definitions, sections)
    rule_f = _check_rule_f(entries, router["path_titles"])
    errors.extend(rule_a)
    errors.extend(rule_b)
    errors.extend(rule_c)
    errors.extend(rule_d)
    errors.extend(rule_e)
    errors.extend(rule_f)
    warnings.extend(rule_e_warnings)

    backend_keys = {entry.get("key") for entry, _role in entries}
    path_count = sum(1 for entry, _role in entries if entry.get("path"))
    print(
        "[INFO] 后端单一菜单源: %d 个板块 / %d 个 key / %d 个带 path 入口；"
        "前端路由 %d 条（含 alias）/ %d 个 meta.menuKey"
        % (len(sections), len(backend_keys), path_count, len(router["paths"]), len(router["menu_keys"]))
    )
    if legacy_exempt:
        print("[INFO] 历史兼容 key（section=None + legacy=True，无导航出口，规则 C 豁免 %d 个）:"
              % len(legacy_exempt))
        print("  - " + ", ".join(sorted(legacy_exempt)))

    for warning in warnings:
        print("[WARN]", warning)

    if errors:
        print("\n[FAIL] 前后端菜单对齐检查未通过，共 %d 项:" % len(errors))
        for rule_name in ("[A]", "[B]", "[C]", "[D]", "[E]", "[F]"):
            grouped = [error for error in errors if error.startswith(rule_name)]
            if not grouped:
                continue
            print("  规则 %s（%d 项）:" % (rule_name[1], len(grouped)))
            for error in grouped:
                print("    -", error)
        print(
            "\n[FAIL] 汇总: A=%d B=%d C=%d D=%d E=%d F=%d"
            % (len(rule_a), len(rule_b), len(rule_c), len(rule_d), len(rule_e), len(rule_f))
        )
        return 1

    print("[OK] 前后端菜单对齐检查通过（规则 A~F 全部满足）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
