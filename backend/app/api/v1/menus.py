"""
菜单权限管理 API —— 单一菜单源 v2

契约：`.scratch/w21-nav-single-source/000-contract.md`（唯一权威）。

设计要点：
- `MENU_DEFINITIONS` 是**唯一**菜单权威（本文件），前端侧栏 / 移动端导航 /
  权限面板 / 权限包菜单树全部由后端下发数据驱动，不再维护第二套前端菜单配置；
- `MENU_SECTIONS` 定义 6 个导航板块（工作台 dashboard 由前端固定渲染，不入板块）；
- `/menus/accessible` 与 `/menus/all` 均返回 v2 结构：
  `{version: 2, sections: [...], flat_keys: [...]}`；
- 过滤优先级保持不变：superuser 全量 > user.allowed_menus > 启用中权限包 > 角色默认，
  之后无条件并入 `_PUBLIC_ACCESS_KEYS`（政策法规 / 数据分析公开 key 不变）；
- 旧 key 全部保留：可承载的并入 group children / console tabs；无导航出口的历史 key
  以 `section=None + legacy=True` 保留在定义中（仅用于权限包 / 历史 allowed_menus 校验，
  不参与 sections 渲染），避免旧权限配置失效。
"""

# security-audit: exempt data_scope — 按 User.id 主键定位的用户菜单配置（身份域），非组织数据枚举

import json
import logging
from functools import lru_cache
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.constants import normalize_role
from app.core.database import get_db
from app.core.permission_utils import is_admin as _is_admin  # 唯一管理员判定入口
from app.core.permission_utils import is_superuser as _is_superuser  # 超级管理员豁免菜单裁剪
from app.core.security import get_current_user
from app.core.transaction import safe_commit
from app.models.permission_pack import PermissionPack
from app.models.user import User
from app.services.work_log_service import write_work_log


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/menus", tags=["菜单权限管理"])

# v2 schema 版本号（前端据此识别单一菜单源结构）
MENU_SCHEMA_VERSION = 2


# ==================== 板块定义（契约 §4） ====================

MENU_SECTIONS: list[dict[str, Any]] = [
    {"key": "business", "label": "帮扶业务", "order": 10},
    {"key": "rural", "label": "乡村振兴", "order": 20},
    {"key": "collab", "label": "工作协同", "order": 30},
    {"key": "report", "label": "分析汇报", "order": 40},
    {"key": "data", "label": "数据管理", "order": 50},
    {"key": "system", "label": "系统管理", "order": 90},
]


# ==================== 菜单定义（唯一权威） ====================
# 字段：key / label / path / icon / order / section / kind / roles / children / tabs
# - kind: page（必须有 path）| group（必须有 children，不允许 path）| console（必须有 path + tabs）
# - roles: None = 所有角色可见；否则为角色白名单（normalize_role 语义）
# - section: 所属板块 key；None = 不进入 sections（工作台 / 历史兼容 key）
# - legacy: True = 历史兼容 key，无导航出口，仅供权限包 / 历史 allowed_menus 校验
# - tabs[].key 必须使用**旧 key**（权限包兼容），tab.path 为旧页面路由

MENU_DEFINITIONS: list[dict[str, Any]] = [
    # ── 工作台（前端固定渲染，不入 sections） ──
    {
        "key": "dashboard",
        "label": "工作台",
        "path": "/dashboard",
        "icon": "HomeFilled",
        "order": 0,
        "section": None,
        "kind": "page",
        "roles": None,
    },
    # ── business 帮扶业务（order 10） ──
    {
        "key": "villages",
        "label": "帮扶村管理",
        "path": "/supported-villages",
        "icon": "Location",
        "order": 10,
        "section": "business",
        "kind": "page",
        "roles": None,
    },
    {
        # W22（v1.14.0）：一户一档（家庭成员/帮扶责任人/风险类型/监测指标/预警/走访挂户）
        "key": "households",
        "label": "一户一档",
        "path": "/households",
        "icon": "House",
        "order": 15,
        "section": "business",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "projects",
        "label": "帮扶项目",
        "path": "/projects",
        "icon": "Folder",
        "order": 20,
        "section": "business",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "schools",
        "label": "帮扶学校",
        "path": "/schools",
        "icon": "School",
        "order": 30,
        "section": "business",
        "kind": "page",
        "roles": None,
    },
    {
        # 经费管理：分组保留旧 key funds-admin 等作为 children（权限包兼容），本次不整合经费页
        "key": "funds",
        "label": "经费管理",
        "path": None,
        "icon": "Money",
        "order": 40,
        "section": "business",
        "kind": "group",
        "roles": ["admin", "super_admin", "user", "viewer"],
        "children": [
            {
                "key": "funds-admin",
                "label": "经费台账",
                "path": "/funds",
                "icon": "Money",
                "order": 10,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
            {
                "key": "funds-user",
                "label": "经费申请",
                "path": "/funds/user",
                "icon": "Money",
                "order": 20,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
            {
                "key": "funds-lifecycle",
                "label": "资金周期",
                "path": "/funds/lifecycle",
                "icon": "Money",
                "order": 30,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
            {
                "key": "funds-settlement",
                "label": "决算结算",
                "path": "/funds/settlement",
                "icon": "Money",
                "order": 40,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
            {
                "key": "funds-budget",
                "label": "预算管理",
                "path": "/funds/budget",
                "icon": "Money",
                "order": 50,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
            {
                "key": "funds-contract",
                "label": "合同管理",
                "path": "/funds/contract",
                "icon": "Money",
                "order": 60,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
            {
                "key": "funds-transfer",
                "label": "转账凭证",
                "path": "/funds/transfer",
                "icon": "Money",
                "order": 70,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
            {
                "key": "funds-anomaly",
                "label": "异常资金",
                "path": "/funds/anomaly",
                "icon": "Money",
                "order": 80,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
            {
                "key": "funds-analysis",
                "label": "经费分析",
                "path": "/funds/analysis",
                "icon": "DataAnalysis",
                "order": 90,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
            {
                "key": "funds-report",
                "label": "资金报告",
                "path": "/funds/report",
                "icon": "Document",
                "order": 100,
                "kind": "page",
                "roles": ["admin", "super_admin", "user", "viewer"],
            },
        ],
    },
    {
        "key": "pairing",
        "label": "结对帮扶",
        "path": "/pairings",
        "icon": "Connection",
        "order": 50,
        "section": "business",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "donation",
        "label": "捐赠物资",
        "path": "/donations",
        "icon": "Box",
        "order": 60,
        "section": "business",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "policies",
        "label": "政策法规",
        "path": "/policies",
        "icon": "Document",
        "order": 70,
        "section": "business",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "handover",
        "label": "工作移交",
        "path": "/handover",
        "icon": "Switch",
        "order": 80,
        "section": "business",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "consumption",
        "label": "消费帮扶",
        "path": "/consumption",
        "icon": "ShoppingCart",
        "order": 85,
        "section": "business",
        "kind": "page",
        "roles": None,
    },
    # ── rural 乡村振兴（order 20） ──
    {
        "key": "rural-works",
        "label": "工作首页",
        "path": "/rural-works",
        "icon": "Sunny",
        "order": 10,
        "section": "rural",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "rural-works-list",
        "label": "工作列表",
        "path": "/rural-works/list",
        "icon": "List",
        "order": 20,
        "section": "rural",
        "kind": "page",
        "roles": None,
    },
    # ── collab 工作协同（order 30） ──
    {
        "key": "todos",
        "label": "待办事项",
        "path": "/todos",
        "icon": "Select",
        "order": 10,
        "section": "collab",
        "kind": "page",
        "roles": None,
    },
    {
        # 契约 §4 的 approval 分组：分组 key 沿用旧 key approval（权限包兼容）。
        # 契约中首个 child 写作 "approval /approval"（与分组 key 冲突），此处用
        # approval-overview 承载 /approval 路径，避免同树重复 key。
        "key": "approval",
        "label": "审批管理",
        "path": None,
        "icon": "Stamp",
        "order": 20,
        "section": "collab",
        "kind": "group",
        "roles": ["admin", "super_admin"],
        "children": [
            {
                "key": "approval-overview",
                "label": "审批总览",
                "path": "/approval",
                "icon": "Document",
                "order": 10,
                "kind": "page",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "approval-pending",
                "label": "待审批",
                "path": "/approval/pending",
                "icon": "Stamp",
                "order": 20,
                "kind": "page",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "approval-my",
                "label": "我的申请",
                "path": "/approval/my",
                "icon": "Edit",
                "order": 30,
                "kind": "page",
                "roles": None,
            },
            {
                "key": "approval-history",
                "label": "审批历史",
                "path": "/approval/history",
                "icon": "List",
                "order": 40,
                "kind": "page",
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "work-calendar",
        "label": "工作日历",
        "path": "/work-calendar",
        "icon": "Calendar",
        "order": 30,
        "section": "collab",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "reminder",
        "label": "提醒中心",
        "path": "/reminder",
        "icon": "Bell",
        "order": 40,
        "section": "collab",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "messages",
        "label": "消息中心",
        "path": "/message",
        "icon": "Message",
        "order": 50,
        "section": "collab",
        "kind": "page",
        "roles": None,
    },
    # ── report 分析汇报（order 40） ──
    {
        "key": "bigscreen",
        "label": "汇报大屏",
        "path": "/bigscreen",
        "icon": "Monitor",
        "order": 10,
        "section": "report",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "analytics",
        "label": "数据分析",
        "path": None,
        "icon": "DataAnalysis",
        "order": 20,
        "section": "report",
        "kind": "group",
        "roles": None,
        "children": [
            {
                "key": "analytics-dashboard",
                "label": "分析仪表盘",
                "path": "/data-analysis/dashboard",
                "icon": "DataAnalysis",
                "order": 10,
                "kind": "page",
                "roles": None,
            },
            {
                "key": "analytics-map",
                "label": "地图可视化",
                "path": "/data-analysis/map",
                "icon": "MapLocation",
                "order": 20,
                "kind": "page",
                "roles": None,
            },
            {
                "key": "work-analysis",
                "label": "工作分析",
                "path": "/data-analysis/reports",
                "icon": "TrendCharts",
                "order": 30,
                "kind": "page",
                "roles": None,
            },
            {
                "key": "effectiveness-rankings",
                "label": "成效排名",
                "path": "/effectiveness/rankings",
                "icon": "Trophy",
                "order": 40,
                "kind": "page",
                "roles": None,
            },
            {
                "key": "effectiveness-evaluate",
                "label": "成效评估",
                "path": "/effectiveness/evaluate",
                "icon": "Checked",
                "order": 50,
                "kind": "page",
                "roles": None,
            },
        ],
    },
    {
        "key": "report-templates",
        "label": "报表模板",
        "path": "/report/templates",
        "icon": "Document",
        "order": 30,
        "section": "report",
        "kind": "page",
        "roles": ["admin", "super_admin"],
    },
    {
        "key": "report-export",
        "label": "报表导出",
        "path": "/export/report",
        "icon": "Download",
        "order": 40,
        "section": "report",
        "kind": "page",
        "roles": ["admin", "super_admin"],
    },
    {
        # W22（v1.14.0）：影像库（村/校/项目/时间/标签归档 + 多期照片对比）
        "key": "media-library",
        "label": "影像库",
        "path": "/media",
        "icon": "PictureFilled",
        "order": 50,
        "section": "report",
        "kind": "page",
        "roles": None,
    },
    # ── data 数据管理（order 50） ──
    {
        "key": "data-overview",
        "label": "数据概览",
        "path": "/data-management",
        "icon": "DataBoard",
        "order": 10,
        "section": "data",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "data-sync-export",
        "label": "数据导出",
        "path": "/data-sync/export",
        "icon": "Download",
        "order": 20,
        "section": "data",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "data-sync-import",
        "label": "数据导入",
        "path": "/data-sync/import",
        "icon": "Upload",
        "order": 30,
        "section": "data",
        "kind": "page",
        "roles": None,
    },
    {
        # 旧 key data-package-list 的页面路径被本 key 接管（见文件末尾 legacy 定义）
        "key": "data-package",
        "label": "数据包与批量导入",
        "path": "/data-package",
        "icon": "FolderOpened",
        "order": 40,
        "section": "data",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "data-verify",
        "label": "数据校验",
        "path": "/data-verify",
        "icon": "Checked",
        "order": 50,
        "section": "data",
        "kind": "page",
        "roles": ["admin", "super_admin"],
    },
    {
        "key": "comprehensive-entry",
        "label": "综合数据录入",
        "path": "/data-entry",
        "icon": "Edit",
        "order": 70,
        "section": "data",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "batch-operations",
        "label": "批量操作",
        "path": "/batch",
        "icon": "Operation",
        "order": 80,
        "section": "data",
        "kind": "page",
        "roles": None,
    },
    {
        "key": "data-upload",
        "label": "数据上报",
        "path": None,
        "icon": "Upload",
        "order": 90,
        "section": "data",
        "kind": "group",
        "roles": None,
        "children": [
            {
                "key": "data-package-report",
                "label": "数据上报",
                "path": "/data-package/report",
                "icon": "Upload",
                "order": 10,
                "kind": "page",
                "roles": None,
            },
            {
                "key": "data-package-receive",
                "label": "接收数据包",
                "path": "/data-package/receive",
                "icon": "Download",
                "order": 20,
                "kind": "page",
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "data-package-version",
                "label": "版本管理",
                "path": "/data-package/version",
                "icon": "Refresh",
                "order": 30,
                "kind": "page",
                "roles": None,
            },
        ],
    },
    # ── system 系统管理（order 90）：6 个聚合页 console ──
    # 聚合页 path 为新增的聚合路由；tabs[].path 为旧页面路由（深链保留）
    {
        "key": "system-console-org",
        "label": "组织与权限",
        "path": "/system/console/org",
        "icon": "OfficeBuilding",
        "order": 10,
        "section": "system",
        "kind": "console",
        "roles": ["admin", "super_admin"],
        "tabs": [
            {
                "key": "users-orgs",
                "label": "用户与组织",
                "path": "/system/users",
                "icon": "User",
                "order": 10,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "roles",
                "label": "角色管理",
                "path": "/system/roles",
                "icon": "UserFilled",
                "order": 20,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "menus",
                "label": "菜单管理",
                "path": "/system/menus",
                "icon": "Menu",
                "order": 30,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "system-permission-packs",
                "label": "权限包管理",
                "path": "/system/permission-packs",
                "icon": "Key",
                "order": 40,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "organizations",
                "label": "组织机构",
                "path": "/organization",
                "icon": "OfficeBuilding",
                "order": 50,
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "system-console-security",
        "label": "安全与审计",
        "path": "/system/console/security",
        "icon": "Lock",
        "order": 20,
        "section": "system",
        "kind": "console",
        "roles": ["admin", "super_admin"],
        "tabs": [
            {
                "key": "audit",
                "label": "安全审计",
                "path": "/system/audit",
                "icon": "Document",
                "order": 10,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "zero-trust",
                "label": "零信任",
                "path": "/system/zero-trust",
                "icon": "Lock",
                "order": 20,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "secrets",
                "label": "密钥管理",
                "path": "/system/secrets",
                "icon": "Key",
                "order": 30,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "data-tier",
                "label": "数据分级",
                "path": "/system/data-tier",
                "icon": "Coin",
                "order": 40,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "encryption",
                "label": "加密设置",
                "path": "/system/encryption",
                "icon": "Lock",
                "order": 50,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "machine-code",
                "label": "机器码管理",
                "path": "/admin/machine-code/management",
                "icon": "Cpu",
                "order": 60,
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "system-console-ops",
        "label": "运维与监控",
        "path": "/system/console/ops",
        "icon": "Monitor",
        "order": 30,
        "section": "system",
        "kind": "console",
        "roles": ["admin", "super_admin"],
        "tabs": [
            {
                "key": "system-overview",
                "label": "系统总览",
                "path": "/system/overview",
                "icon": "Odometer",
                "order": 10,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "health-check",
                "label": "健康检查",
                "path": "/system/health-check",
                "icon": "CircleCheck",
                "order": 20,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "monitor",
                "label": "系统监控",
                "path": "/system/monitoring",
                "icon": "Monitor",
                "order": 30,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "cache",
                "label": "缓存管理",
                "path": "/system/cache",
                "icon": "Refresh",
                "order": 40,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "tasks",
                "label": "后台任务",
                "path": "/system/tasks",
                "icon": "Timer",
                "order": 50,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "environment",
                "label": "运行环境",
                "path": "/system/environment",
                "icon": "Cpu",
                "order": 60,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "error-reports",
                "label": "错误上报",
                "path": "/system/error-reports",
                "icon": "Warning",
                "order": 70,
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "system-console-storage",
        "label": "备份与存储",
        "path": "/system/console/storage",
        "icon": "FolderOpened",
        "order": 40,
        "section": "system",
        "kind": "console",
        "roles": ["admin", "super_admin"],
        "tabs": [
            {
                # 旧产品要求：普通用户只读可见备份管理（写操作仍由后端 require_admin 把关）
                "key": "backup",
                "label": "备份管理",
                "path": "/system/backup",
                "icon": "Folder",
                "order": 10,
                "roles": ["admin", "super_admin", "user"],
            },
            {
                "key": "chunked-upload",
                "label": "分片上传",
                "path": "/system/chunked-upload",
                "icon": "Upload",
                "order": 20,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "map-tiles",
                "label": "地图瓦片",
                "path": "/system/map-tiles",
                "icon": "MapLocation",
                "order": 30,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "control-package",
                "label": "管控配置包",
                "path": "/system/control-package",
                "icon": "Files",
                "order": 40,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "config-package",
                "label": "系统配置",
                "path": "/system/config",
                "icon": "Setting",
                "order": 50,
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "system-console-settings",
        "label": "系统设置",
        "path": "/system/console/settings",
        "icon": "Setting",
        "order": 50,
        "section": "system",
        "kind": "console",
        "roles": ["admin", "super_admin"],
        "tabs": [
            {
                "key": "update-logs",
                "label": "更新日志",
                "path": "/system/update-logs",
                "icon": "Document",
                "order": 10,
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    {
        "key": "system-console-about",
        "label": "关于与反馈",
        "path": "/system/console/about",
        "icon": "InfoFilled",
        "order": 60,
        "section": "system",
        "kind": "console",
        "roles": ["admin", "super_admin"],
        "tabs": [
            {
                # 关于/帮助保留全角色旧语义（roles=None），普通用户仍可从侧栏进入帮助中心
                "key": "about",
                "label": "关于系统",
                "path": "/system/about",
                "icon": "InfoFilled",
                "order": 10,
                "roles": None,
            },
            {
                "key": "feedback",
                "label": "反馈管理",
                "path": "/system/feedback",
                "icon": "ChatDotRound",
                "order": 20,
                "roles": ["admin", "super_admin"],
            },
            {
                "key": "help",
                "label": "帮助中心",
                "path": "/help",
                "icon": "QuestionFilled",
                "order": 30,
                "roles": None,
            },
            {
                "key": "admin-dashboard",
                "label": "管理面板",
                "path": "/admin/dashboard",
                "icon": "DataBoard",
                "order": 40,
                "roles": ["admin", "super_admin"],
            },
        ],
    },
    # ── W22（v1.14.0）：移除导航出口的历史 key（保留定义以兼容权限包 / allowed_menus）──
    {
        "key": "checkin",
        "label": "驻村工作台（已移除）",
        "path": None,
        "icon": "Location",
        "order": 991,
        "section": None,
        "kind": "page",
        "roles": None,
        "legacy": True,
    },
    {
        "key": "i18n",
        "label": "多语言（已移除）",
        "path": None,
        "icon": "Reading",
        "order": 992,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin"],
        "legacy": True,
    },
    {
        "key": "email",
        "label": "邮件设置（已移除）",
        "path": None,
        "icon": "Message",
        "order": 993,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin"],
        "legacy": True,
    },
    {
        "key": "validation-rules",
        "label": "校验规则（已合并到数据校验）",
        "path": None,
        "icon": "Document",
        "order": 994,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin"],
        "legacy": True,
    },
    {
        "key": "sentiment",
        "label": "舆情监测（已改为消费帮扶）",
        "path": None,
        "icon": "ChatDotRound",
        "order": 995,
        "section": None,
        "kind": "page",
        "roles": None,
        "legacy": True,
    },
    # ── 历史兼容 key（section=None + legacy=True，无导航出口） ──
    # 契约 §3：所有旧 key 保留在定义中（即使不直接出现在 sections 的 items 里），
    # 保证权限包 / 历史 allowed_menus 不失效。以下 key 在新信息架构中已被
    # 板块 / 新 key / 聚合页 tab 取代，保留定义仅用于合法性校验与权限兼容。
    {
        "key": "helpData",
        "label": "帮扶数据管理（历史兼容）",
        "path": None,
        "icon": "TrendCharts",
        "order": 900,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin", "user"],
        "legacy": True,
    },
    {
        "key": "batch-import",
        "label": "数据批量导入（历史兼容）",
        "path": None,
        "icon": "Upload",
        "order": 901,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin"],
        "legacy": True,
    },
    {
        "key": "data-package-list",
        "label": "数据包列表（历史兼容）",
        "path": None,
        "icon": "FolderOpened",
        "order": 902,
        "section": None,
        "kind": "page",
        "roles": None,
        "legacy": True,
    },
    {
        "key": "data",
        "label": "数据管理（历史兼容）",
        "path": None,
        "icon": "FolderOpened",
        "order": 903,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin"],
        "legacy": True,
    },
    {
        "key": "data-logs",
        "label": "操作日志（历史兼容）",
        "path": None,
        "icon": "Document",
        "order": 904,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin"],
        "legacy": True,
    },
    {
        "key": "data-analysis",
        "label": "数据分析（历史兼容）",
        "path": None,
        "icon": "DataAnalysis",
        "order": 905,
        "section": None,
        "kind": "page",
        "roles": None,
        "legacy": True,
    },
    {
        "key": "system",
        "label": "系统管理（历史兼容）",
        "path": None,
        "icon": "Setting",
        "order": 906,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin"],
        "legacy": True,
    },
    {
        "key": "system-config",
        "label": "系统配置（历史兼容）",
        "path": None,
        "icon": "Setting",
        "order": 907,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin"],
        "legacy": True,
    },
    {
        "key": "pass-code",
        "label": "通行码管理（历史兼容）",
        "path": None,
        "icon": "Key",
        "order": 908,
        "section": None,
        "kind": "page",
        "roles": ["admin", "super_admin"],
        "legacy": True,
    },
    {
        "key": "effectiveness",
        "label": "帮扶成效（历史兼容）",
        "path": None,
        "icon": "TrendCharts",
        "order": 909,
        "section": None,
        "kind": "page",
        "roles": None,
        "legacy": True,
    },
]

# 历史兼容 key（section=None + legacy=True）：无导航出口，仅参与 key 合法性校验
_LEGACY_MENU_KEYS: frozenset[str] = frozenset(
    entry["key"] for entry in MENU_DEFINITIONS if entry.get("legacy")
)


# ==================== 菜单 key / 树工具 ====================


def _iter_definition_keys() -> list[str]:
    """按定义顺序展开全部 key（含 children / tabs / 历史兼容 key）

    key 唯一性由门禁脚本 `scripts/check_menu_alignment.py` 规则 E 保证，此处不再去重。
    """
    ordered: list[str] = []

    def walk(items: list[dict[str, Any]]) -> None:
        for item in items:
            ordered.append(item["key"])
            walk(item.get("children") or [])
            walk(item.get("tabs") or [])

    walk(MENU_DEFINITIONS)
    return ordered


def _flatten_menu_keys(menus: list[dict[str, Any]]) -> set[str]:
    """扁平化菜单树为 key 集合（含 children / tabs）

    仍被 `permission_packs` 复用做权限包 menu_keys 合法性校验；传入
    `MENU_DEFINITIONS` 时会包含历史兼容 key，保证旧权限包不因升级失效。
    """
    keys: set[str] = set()

    def traverse(items: list[dict[str, Any]]) -> None:
        for item in items:
            keys.add(item["key"])
            if item.get("children"):
                traverse(item["children"])
            if item.get("tabs"):
                traverse(item["tabs"])

    traverse(menus)
    return keys


# ==================== 菜单定义 → v2 响应结构 ====================


def _page_payload(entry: dict[str, Any]) -> dict[str, Any]:
    """page 条目响应载荷"""
    return {
        "key": entry["key"],
        "label": entry["label"],
        "path": entry["path"],
        "icon": entry.get("icon"),
        "order": entry.get("order", 0),
        "kind": entry["kind"],
        "roles": entry.get("roles"),
    }


def _group_payload(entry: dict[str, Any], children: list[dict[str, Any]]) -> dict[str, Any]:
    """group 条目响应载荷（group 不下发 path，契约 §2）"""
    return {
        "key": entry["key"],
        "label": entry["label"],
        "icon": entry.get("icon"),
        "order": entry.get("order", 0),
        "kind": entry["kind"],
        "roles": entry.get("roles"),
        "children": children,
    }


def _console_payload(entry: dict[str, Any], tabs: list[dict[str, Any]]) -> dict[str, Any]:
    """console 条目响应载荷（聚合页，path + tabs）"""
    return {
        "key": entry["key"],
        "label": entry["label"],
        "path": entry["path"],
        "icon": entry.get("icon"),
        "order": entry.get("order", 0),
        "kind": entry["kind"],
        "roles": entry.get("roles"),
        "tabs": tabs,
    }


def _child_payload(child: dict[str, Any]) -> dict[str, Any]:
    """group child 响应载荷（含 kind）"""
    return {
        "key": child["key"],
        "label": child["label"],
        "path": child["path"],
        "icon": child.get("icon"),
        "order": child.get("order", 0),
        "kind": child.get("kind", "page"),
        "roles": child.get("roles"),
    }


def _tab_payload(tab: dict[str, Any]) -> dict[str, Any]:
    """console tab 响应载荷（不含 kind，契约 §2）"""
    return {
        "key": tab["key"],
        "label": tab["label"],
        "path": tab["path"],
        "icon": tab.get("icon"),
        "order": tab.get("order", 0),
        "roles": tab.get("roles"),
    }


def _filter_entry(entry: dict[str, Any], allowed_keys: set[str]) -> dict[str, Any] | None:
    """按用户可见 key 过滤单个条目；不可见返回 None。

    契约 §3：
    - group 可见 = 任一 child 可见；children 裁掉不可见项，children 为空则不出现；
    - console 可见 = console.key ∈ allowed 或任一 tab.key ∈ allowed；
      console.key 被勾选时其全部 tabs 可见，否则仅下发 tab.key ∈ allowed 的 tabs。
    """
    kind = entry["kind"]
    if kind == "group":
        children = [c for c in entry.get("children") or [] if c["key"] in allowed_keys]
        if not children:
            return None
        return _group_payload(entry, [_child_payload(c) for c in children])
    if kind == "console":
        console_allowed = entry["key"] in allowed_keys
        tabs = [
            tab for tab in entry.get("tabs") or []
            if console_allowed or tab["key"] in allowed_keys
        ]
        if not tabs:
            return None
        return _console_payload(entry, [_tab_payload(t) for t in tabs])
    if entry["key"] not in allowed_keys:
        return None
    return _page_payload(entry)


def _serialize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """完整序列化单个条目（/menus/all 不做用户级过滤）"""
    kind = entry["kind"]
    if kind == "group":
        return _group_payload(entry, [_child_payload(c) for c in entry.get("children") or []])
    if kind == "console":
        return _console_payload(entry, [_tab_payload(t) for t in entry.get("tabs") or []])
    return _page_payload(entry)


def _section_entries(section_key: str) -> list[dict[str, Any]]:
    """取某个板块下的顶层条目（保持 section 归属）"""
    return [entry for entry in MENU_DEFINITIONS if entry.get("section") == section_key]


def _build_sections(allowed_keys: Optional[set[str]] = None) -> list[dict[str, Any]]:
    """按板块组装 v2 sections

    allowed_keys=None 表示不过滤（/menus/all）；过滤后 items 为空的板块不出现。
    """
    sections: list[dict[str, Any]] = []
    for section in sorted(MENU_SECTIONS, key=lambda s: s["order"]):
        items: list[dict[str, Any]] = []
        for entry in sorted(_section_entries(section["key"]), key=lambda e: e.get("order", 0)):
            item = _serialize_entry(entry) if allowed_keys is None else _filter_entry(entry, allowed_keys)
            if item is not None:
                items.append(item)
        if not items:
            continue
        sections.append({
            "key": section["key"],
            "label": section["label"],
            "order": section["order"],
            "items": items,
        })
    return sections


def _visible_keys(sections: list[dict[str, Any]]) -> list[str]:
    """收集 sections 中实际下发的全部 key（含 group/console 本身 + children + tabs）"""
    keys: list[str] = []
    for section in sections:
        for item in section["items"]:
            keys.append(item["key"])
            for child in item.get("children") or []:
                keys.append(child["key"])
            for tab in item.get("tabs") or []:
                keys.append(tab["key"])
    return keys


def _build_flat_keys(
    sections: list[dict[str, Any]],
    allowed_keys: Optional[set[str]] = None,
) -> list[str]:
    """组装 flat_keys（供前端 canAccessMenu 与权限面板使用）

    - allowed_keys=None：/menus/all，返回全部定义 key（含历史兼容 key）；
    - 否则：dashboard（若允许）+ 实际下发的可见 key + 允许的历史兼容 key
      （历史兼容 key 无导航出口，但保留其守卫语义，避免旧链接/历史配置失效）。
    """
    definition_keys = _iter_definition_keys()
    if allowed_keys is None:
        return definition_keys
    visible = set(_visible_keys(sections))
    flat: list[str] = []
    if "dashboard" in allowed_keys:
        flat.append("dashboard")
    flat.extend(key for key in definition_keys if key in visible)
    flat.extend(
        key for key in definition_keys
        if key in _LEGACY_MENU_KEYS and key in allowed_keys
    )
    return flat


# ==================== 权限解析 ====================


@lru_cache(maxsize=8)
def _get_role_default_menu_keys(role: str) -> frozenset[str]:
    """根据角色返回默认可见的菜单 key 集合（含 children / tabs / 历史兼容 key）"""
    role = normalize_role(role)  # 兼容旧角色值（manager/approval_leader→admin, operator→user）
    role_menu_keys: set[str] = set()

    def traverse(items: list[dict[str, Any]]) -> None:
        for item in items:
            allowed_roles = item.get("roles")
            if allowed_roles is None or role in allowed_roles:
                role_menu_keys.add(item["key"])
            children = item.get("children")
            if children:
                traverse(children)
            tabs = item.get("tabs")
            if tabs:
                traverse(tabs)

    traverse(MENU_DEFINITIONS)
    return frozenset(role_menu_keys)


def _get_user_bound_pack(user: User, db: Session) -> PermissionPack | None:
    """获取用户绑定的启用中权限包（未绑定/已停用/包不存在时返回 None）"""
    pack_id = getattr(user, "permission_pack_id", None)
    # 防御：仅接受真实 int（Mock 用户/脏数据直接跳过，回落角色默认）
    if not isinstance(pack_id, int) or isinstance(pack_id, bool) or pack_id <= 0:
        return None
    return (
        db.query(PermissionPack)
        .filter(PermissionPack.id == pack_id, PermissionPack.is_active.is_(True))
        .first()
    )


# 全角色公开模块（2026-08-15 产品要求）：
# 政策法规与数据分析对普通用户（user/viewer）与管理员完全一致，
# 不受用户级 allowed_menus / 权限包 / 角色默认配置的裁剪。
_PUBLIC_ACCESS_KEYS: frozenset[str] = frozenset({
    "policies",                    # 政策法规
    "helpData",                    # 数据分析的父级（帮扶数据管理，历史兼容 key）
    "data-analysis",               # 数据统计分析（历史兼容 key）
    "analytics",                   # 数据分析
    "analytics-dashboard",         # 分析仪表盘
    "analytics-map",               # 地图可视化
    "work-analysis",               # 工作分析
})


def _get_user_accessible_menu_keys(user: User, db: Session) -> set[str]:
    """获取用户实际可见的菜单 key 集合

    优先级：用户级 allowed_menus 配置 > 绑定的启用中权限包 > 角色默认。
    之后无条件并入 _PUBLIC_ACCESS_KEYS（政策法规/数据分析全角色公开）。

    超级管理员豁免：不受 allowed_menus / 权限包 / 角色默认裁剪，始终返回全量菜单
    （修复 2026-09-12 admin 被 allowed_menus 旧配置或权限包裁剪，导致
    /menus/accessible 只下发少量菜单、而权限配置弹窗读取的 /menus/all 是全量，
    出现"弹窗全勾选、菜单看不到"的不一致）。
    """
    if _is_superuser(user):
        return _flatten_menu_keys(MENU_DEFINITIONS)

    allowed = user.allowed_menus_list
    if allowed is not None:
        # 用户级别配置优先
        keys = set(allowed)
    else:
        # 其次：绑定的启用中权限包（菜单套餐）
        pack = _get_user_bound_pack(user, db)
        if pack is not None:
            keys = set(pack.menu_keys_list)
        else:
            # 否则继承角色默认
            keys = set(_get_role_default_menu_keys(user.role))
    # 公开模块强制并入，保证普通用户政策法规/数据分析与管理员一致
    keys |= _PUBLIC_ACCESS_KEYS
    return keys


# ==================== 请求模型 ====================


class UserMenuUpdate(BaseModel):
    """设置用户菜单权限"""
    menu_keys: Optional[list[str]] = None  # None = 恢复角色默认菜单


# ==================== API 接口 ====================


@router.get(
    "/accessible",
    summary="获取当前用户可见菜单（v2 单一菜单源）",
    response_model=dict,
)
async def get_accessible_menus(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """返回当前登录用户可访问的 v2 菜单结构（sections + flat_keys）。

    过滤逻辑（优先级不变）：
    1. 用户设置了 allowed_menus -> 使用用户配置（source="user"）
    2. 用户绑定了启用中的权限包 -> 使用权限包菜单（source="pack"）
    3. 用户未设置 -> 使用角色默认菜单（source="role"）
    4. superuser 豁免上述裁剪，始终全量
    5. 之后并入 _PUBLIC_ACCESS_KEYS（政策法规/数据分析公开）
    """
    allowed_keys = _get_user_accessible_menu_keys(current_user, db)
    sections = _build_sections(allowed_keys)
    if current_user.allowed_menus_list is not None:
        source = "user"
    elif _get_user_bound_pack(current_user, db) is not None:
        source = "pack"
    else:
        source = "role"
    logger.debug(
        "菜单查询: user=%s role=%s source=%s keys=%s",
        current_user.username, current_user.role, source, sorted(allowed_keys),
    )
    return {
        "success": True,
        "source": source,
        "data": {
            "version": MENU_SCHEMA_VERSION,
            "sections": sections,
            "flat_keys": _build_flat_keys(sections, allowed_keys),
        },
    }


@router.get(
    "/all",
    summary="获取所有菜单定义（管理员，v2 单一菜单源）",
    response_model=dict,
)
async def get_all_menus(
    current_user: User = Depends(get_current_user),
) -> dict:
    """返回完整 v2 菜单结构（不做用户级过滤，含完整 roles/tabs），供权限面板/权限包菜单树"""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    sections = _build_sections()
    return {
        "success": True,
        "data": {
            "version": MENU_SCHEMA_VERSION,
            "sections": sections,
            "flat_keys": _build_flat_keys(sections),
        },
    }


@router.get(
    "/user-menus/{user_id}",
    summary="获取指定用户的菜单权限配置",
    response_model=dict,
)
async def get_user_menu_config(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """获取用户的菜单权限配置详情"""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 用户当前配置
    user_menu_keys = user.allowed_menus_list  # None = 使用角色默认
    role_default_keys = _get_role_default_menu_keys(user.role)
    all_valid_keys = _iter_definition_keys()

    return {
        "success": True,
        "data": {
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "mode": "custom" if user_menu_keys is not None else "role_default",
            "menu_keys": user_menu_keys if user_menu_keys is not None else list(role_default_keys),
            "is_customized": user_menu_keys is not None,
            "role_default_keys": list(role_default_keys),
            "all_valid_keys": all_valid_keys,
        },
    }


@router.put(
    "/user-menus/{user_id}",
    summary="设置用户的菜单权限",
    response_model=dict,
)
async def set_user_menu_config(
    user_id: int,
    data: UserMenuUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    设置用户的菜单权限。

    - menu_keys = None: 恢复角色默认菜单（即删除用户级配置）
    - menu_keys = []: 清空用户所有菜单
    - menu_keys = ["key1", "key2"]: 自定义菜单配置
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 不能修改自己的菜单配置（防止管理员锁死自己）
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的菜单权限")

    # 获取所有有效的菜单 key（含历史兼容 key，保证旧配置可再次保存）
    all_valid_keys = set(_iter_definition_keys())

    if data.menu_keys is None:
        # 恢复角色默认 -> 清除 allowed_menus 字段
        user.allowed_menus = None
        mode = "role_default"
        message = "已恢复角色默认菜单"
    elif len(data.menu_keys) == 0:
        # 清空 -> 无菜单
        user.allowed_menus = json.dumps([])
        mode = "custom"
        message = "已清空用户菜单权限（用户将无法访问任何菜单）"
    else:
        # 验证所有 key 是否有效
        invalid_keys = [k for k in data.menu_keys if k not in all_valid_keys]
        if invalid_keys:
            raise HTTPException(
                status_code=400,
                detail=f"存在无效的菜单key: {', '.join(invalid_keys)}",
            )
        user.allowed_menus = json.dumps(data.menu_keys)
        mode = "custom"
        message = f"已设置用户菜单权限（共 {len(data.menu_keys)} 个菜单）"

    safe_commit(db)
    try:
        write_work_log(db, "menu", "update_menus", user.id, f"设置用户菜单权限: {user.username}",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:
        logger.debug("记录工作日志失败")
    logger.info(f"管理员 {current_user.username} 设置用户 {user.username} 菜单权限: {mode}")

    return {
        "success": True,
        "message": message,
        "mode": mode,
    }


@router.get(
    "/role-defaults",
    summary="获取所有角色的默认菜单配置",
    response_model=dict,
)
async def get_role_default_menus(
    current_user: User = Depends(get_current_user),
) -> dict:
    """返回所有角色的默认菜单配置，用于管理员参考"""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    all_roles = [
        "super_admin", "admin", "user", "viewer",
    ]
    role_menus: dict[str, list[str]] = {}
    for role in all_roles:
        keys = sorted(_get_role_default_menu_keys(role))
        role_menus[role] = keys

    return {
        "success": True,
        "data": role_menus,
    }
