"""账号开通包授权目录与授权矩阵推导（P-AP）。

设计约束（见 ``deliverables/跨机账号包-模块与权限设计.md``）：

* 不新增授权格式：授权仍是 ``Dict[str, str]``（key -> ``view``/``edit``），
  写入既有的 ``org_grants``；
* 页面级是唯一用户界面：管理员只勾“不开放/只读/可操作”，本模块把它推导成
  页面 key（控制菜单可见性）+ 后端模块 key（控制写接口）；
* 只允许 ``view`` / ``edit``，未知 key、未知级别、以及“没有写操作的页面却勾可操作”
  都必须整包拒绝；
* 包的权限是角色权限的上限：导入后由 ``effective_grant_service`` 与
  ``grant_guard`` 执行，而不是把权限码写进账号。

本模块只做纯函数推导/校验，不访问数据库，便于单元测试和离线包导入复用。
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Mapping

logger = logging.getLogger(__name__)

GRANT_VIEW = "view"
GRANT_EDIT = "edit"
GRANT_LEVELS: frozenset[str] = frozenset({GRANT_VIEW, GRANT_EDIT})

# 设计文档明确：工作台、大屏没有写模块，只能选只读。permission_catalog 把
# dashboard 视为可写模块（存在布局类写接口），但对账号包授权而言它不表达“功能权限”。
READ_ONLY_PAGES: frozenset[str] = frozenset({"dashboard", "bigscreen"})

# 与设计文档一致的稳定错误码；调用方会映射为 HTTP 400/409。
ERR_UNKNOWN_KEY = "AP_GRANT_INVALID"
ERR_INVALID_LEVEL = "AP_GRANT_INVALID"
ERR_EDIT_UNSUPPORTED = "AP_GRANT_INVALID"
ERR_EMPTY = "AP_GRANT_EMPTY"
ERR_BAD_SHAPE = "AP_GRANT_SHAPE"
ERR_MENU_NOT_ALLOWED = "AP_MENU_NOT_ALLOWED"


class AccountPackageAuthorizationError(ValueError):
    """授权目录/授权矩阵校验失败。"""

    def __init__(self, message: str, *, code: str = "AP_GRANT_INVALID"):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AuthorizationPage:
    key: str
    label: str
    section: str
    section_label: str
    kind: str
    modules: tuple[str, ...]
    tabs: tuple[tuple[str, str], ...] = ()

    @property
    def can_edit(self) -> bool:
        return bool(self.modules)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "section": self.section,
            "section_label": self.section_label,
            "kind": self.kind,
            "modules": list(self.modules),
            "can_edit": self.can_edit,
            "tabs": [{"key": key, "label": label} for key, label in self.tabs],
        }


def _section_meta() -> tuple[dict[str, dict[str, str]], list[str]]:
    """返回 section key -> 元信息，以及展示顺序。"""
    from app.api.v1.menus import MENU_SECTIONS

    sections: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for section in sorted(MENU_SECTIONS, key=lambda item: item.get("order", 0)):
        key = str(section.get("key") or "")
        if not key:
            continue
        sections[key] = {
            "key": key,
            "label": str(section.get("label") or key),
            "order": str(section.get("order", 0)),
        }
        order.append(key)
    # dashboard 不在 MENU_SECTIONS 中，但它是合法页面；补一个只读工作台分组。
    if "dashboard" not in sections:
        sections["dashboard"] = {"key": "dashboard", "label": "工作台", "order": "0"}
        order.insert(0, "dashboard")
    return sections, order


def _modules_of_page(page_key: str) -> tuple[str, ...]:
    from app.core.permission_catalog import get_catalog

    try:
        if page_key in READ_ONLY_PAGES:
            return ()
        catalog = get_catalog()
        # 只有真正带 write/delete 的页面才允许“可操作”。dashboard 等只读页
        # 在 permission_catalog 里也可能返回自身 key，不能仅凭 key 存在就判定可写。
        if "write" not in catalog.actions_of_page(page_key):
            return ()
        return tuple(sorted(catalog.modules_of_page(page_key)))
    except (ImportError, AttributeError, KeyError, TypeError, ValueError, RuntimeError):
        # 目录构建失败不应把整个授权接口打成 500；该页面按“无写操作”处理。
        logger.warning("账号包授权目录构建失败：page=%s", page_key, exc_info=True)
        return ()


@lru_cache(maxsize=1)
def _catalog_snapshot() -> dict[str, Any]:
    from app.api.v1.menus import MENU_DEFINITIONS

    sections, order = _section_meta()
    pages_by_key: dict[str, AuthorizationPage] = {}
    tree_sections: list[dict[str, Any]] = []
    index: dict[str, list[dict[str, Any]]] = {key: [] for key in order}

    def make_page(entry: Mapping[str, Any], section_key: str) -> AuthorizationPage | None:
        key = str(entry.get("key") or "").strip()
        if not key or not entry.get("path"):
            return None
        kind = str(entry.get("kind") or "page")
        if kind not in ("page", "console"):
            return None
        modules = _modules_of_page(key)
        tabs = tuple(
            (str(tab.get("key") or ""), str(tab.get("label") or tab.get("key") or ""))
            for tab in (entry.get("tabs") or [])
            if tab.get("key")
        )
        page = AuthorizationPage(
            key=key,
            label=str(entry.get("label") or key),
            section=section_key,
            section_label=str(sections.get(section_key, {}).get("label") or section_key),
            kind=kind,
            modules=modules,
            tabs=tabs,
        )
        pages_by_key[key] = page
        return page

    for entry in MENU_DEFINITIONS:
        section_key = str(entry.get("section") or "dashboard")
        if section_key not in index:
            continue
        kind = str(entry.get("kind") or "page")
        if kind == "group":
            children: list[dict[str, Any]] = []
            for child in entry.get("children") or []:
                page = make_page(child, section_key)
                if page is not None:
                    children.append(page.to_dict())
            if children:
                index[section_key].append(
                    {
                        "key": str(entry.get("key") or ""),
                        "label": str(entry.get("label") or entry.get("key") or ""),
                        "kind": "group",
                        "children": children,
                    }
                )
            continue
        page = make_page(entry, section_key)
        if page is not None:
            index[section_key].append(page.to_dict())

    for section_key in order:
        items = index.get(section_key) or []
        if not items:
            continue
        meta = sections.get(section_key) or {}
        tree_sections.append(
            {
                "key": section_key,
                "label": str(meta.get("label") or section_key),
                "items": items,
            }
        )

    pages = [page.to_dict() for page in pages_by_key.values()]
    all_modules: set[str] = set()
    try:
        from app.core.permission_catalog import get_catalog

        all_modules.update(get_catalog().module_actions.keys())
    except (ImportError, AttributeError, KeyError, TypeError, ValueError, RuntimeError):
        logger.warning("账号包授权目录模块清单构建失败，按空清单继续", exc_info=True)
    write_modules: set[str] = set(all_modules)
    write_modules.update(
        module for page in pages_by_key.values() for module in page.modules
    )
    modules = sorted(all_modules)
    canonical = json.dumps(
        {"sections": tree_sections, "modules": modules},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "catalog_version": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "sections": tree_sections,
        "pages": pages,
        "modules": modules,
        "pages_by_key": pages_by_key,
        "module_keys": frozenset(modules),
        "write_module_keys": frozenset(write_modules),
    }


def clear_authorization_catalog_cache() -> None:
    _catalog_snapshot.cache_clear()


def get_authorization_catalog() -> dict[str, Any]:
    """返回可 JSON 序列化的授权目录（不含内部索引）。"""
    snapshot = _catalog_snapshot()
    return {
        "catalog_version": snapshot["catalog_version"],
        "sections": snapshot["sections"],
        "pages": snapshot["pages"],
        "modules": snapshot["modules"],
    }


def _page_map() -> dict[str, AuthorizationPage]:
    return _catalog_snapshot()["pages_by_key"]


def _module_keys() -> frozenset[str]:
    return _catalog_snapshot()["module_keys"]


def _as_level(raw: Any) -> str:
    if not isinstance(raw, str):
        raise AccountPackageAuthorizationError("授权级别必须是字符串", code=ERR_INVALID_LEVEL)
    level = raw.strip().lower()
    if level not in GRANT_LEVELS:
        raise AccountPackageAuthorizationError(
            f"授权级别非法: {raw!r}（仅允许 view/edit）", code=ERR_INVALID_LEVEL
        )
    return level


def derive_grants(selections: Mapping[str, Any]) -> dict[str, str]:
    """把页面勾选推导为 ``org_grants``。

    ``selections`` 的 key 可以是页面 key，也可以是后端模块 key（兼容旧包/高级调用）；
    页面 ``edit`` 会自动补齐该页面映射的模块 ``edit``。空选择返回空字典，
    表示“不激活授权矩阵”。
    """
    if selections is None:
        return {}
    if not isinstance(selections, Mapping):
        raise AccountPackageAuthorizationError("授权配置必须是对象", code=ERR_BAD_SHAPE)

    pages = _page_map()
    modules = _module_keys()
    result: dict[str, str] = {}
    for raw_key, raw_level in selections.items():
        if not isinstance(raw_key, str):
            raise AccountPackageAuthorizationError("授权 key 必须是字符串", code=ERR_UNKNOWN_KEY)
        key = raw_key.strip()
        if not key:
            continue
        level = _as_level(raw_level)
        if key in pages:
            page = pages[key]
            if level == GRANT_EDIT and not page.can_edit:
                raise AccountPackageAuthorizationError(
                    f"页面「{page.label}」没有可写功能，不能设为可操作", code=ERR_EDIT_UNSUPPORTED
                )
            result[key] = level
            if level == GRANT_EDIT:
                for module in page.modules:
                    result[module] = GRANT_EDIT
            continue
        elif key in modules:
            # 页面 edit 已经推导出的模块 edit 不允许被同包内显式 module:view 降级。
            if level == GRANT_VIEW and result.get(key) == GRANT_EDIT:
                continue
            result[key] = level
        else:
            raise AccountPackageAuthorizationError(f"未知授权项: {key}", code=ERR_UNKNOWN_KEY)

    return dict(sorted(result.items()))


def validate_manifest_grants(raw: Any) -> dict[str, str]:
    """导入侧校验：未知 key/级别、非法可操作页面一律拒绝；页面 edit 自动补齐模块。"""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise AccountPackageAuthorizationError("包内 grants 必须是对象", code=ERR_BAD_SHAPE)
    return derive_grants(raw)


def authorization_summary(grants: Mapping[str, str]) -> dict[str, Any]:
    pages = _page_map()
    page_keys = [key for key in grants if key in pages]
    edit_pages = [key for key in page_keys if grants.get(key) == GRANT_EDIT]
    view_pages = [key for key in page_keys if grants.get(key) == GRANT_VIEW]
    write_modules = _catalog_snapshot()["write_module_keys"]
    module_keys = [key for key in grants if key in write_modules]
    canonical = json.dumps(dict(sorted(grants.items())), ensure_ascii=False, sort_keys=True)
    return {
        "page_count": len(page_keys),
        "edit_page_count": len(edit_pages),
        "view_page_count": len(view_pages),
        "module_count": len(module_keys),
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _known_menu_keys() -> frozenset[str]:
    """所有菜单 key（页面 + console tab + 历史 key），用于 allowed_menus 校验。"""
    from app.api.v1.menus import MENU_DEFINITIONS

    keys: set[str] = set()

    def walk(entry: Mapping[str, Any]) -> None:
        key = str(entry.get("key") or "").strip()
        if key:
            keys.add(key)
        for child in entry.get("children") or []:
            walk(child)
        for tab in entry.get("tabs") or []:
            walk(tab)

    for entry in MENU_DEFINITIONS:
        walk(entry)
    return frozenset(keys)


def _allowed_menu_keys_for_grants(grants: Mapping[str, str]) -> frozenset[str]:
    pages = _page_map()
    allowed: set[str] = set(grants)
    for key in grants:
        page = pages.get(key)
        if page is not None:
            allowed.update(tab_key for tab_key, _ in page.tabs)
    return frozenset(allowed)


def validate_menu_selection(raw: Any, grants: Mapping[str, str]) -> list[str] | None:
    """校验账号的 ``allowed_menus`` 必须是包内页面的子集。

    空列表返回 ``None``（表示不额外收窄，沿用角色默认）。旧包 grants 为空时
    只校验 key 存在，避免历史包无法导入。
    """
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple, set)):
        raise AccountPackageAuthorizationError("allowed_menus 必须是数组", code=ERR_BAD_SHAPE)
    known = _known_menu_keys()
    selected = [str(item).strip() for item in raw if str(item).strip()]
    if not selected:
        return None
    unknown = [key for key in selected if key not in known]
    if unknown:
        raise AccountPackageAuthorizationError(
            f"账号引用了未知菜单: {unknown[0]}", code=ERR_MENU_NOT_ALLOWED
        )
    if grants:
        ceiling = _allowed_menu_keys_for_grants(grants)
        outside = [key for key in selected if key not in ceiling]
        if outside:
            raise AccountPackageAuthorizationError(
                f"账号菜单超出包授权页面: {outside[0]}", code=ERR_MENU_NOT_ALLOWED
            )
    return selected


def menu_keys_for_pages(page_keys: Iterable[str]) -> frozenset[str]:
    """给定页面 key，返回界面可见的 key 集合（console 页面含其 tabs）。"""
    pages = _page_map()
    allowed: set[str] = set()
    for key in page_keys:
        if key in pages:
            allowed.add(key)
            allowed.update(tab_key for tab_key, _ in pages[key].tabs)
    return frozenset(allowed)
