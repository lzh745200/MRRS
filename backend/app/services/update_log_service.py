"""系统更新日志服务

管理系统更新日志的CRUD操作和版本历史初始化。

功能：
- 记录系统更新日志
- 查询更新历史
- 初始化版本历史数据（从第一个版本到当前）
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.transaction import safe_commit
from app.models.system_config import SystemUpdateLog

logger = logging.getLogger(__name__)


# 版本历史静态数据（从第一个版本到当前版本的摘要记录）
VERSION_HISTORY_DATA = [
    # ==========================================================================
    # 第一阶段：项目启动与规划 (2025年7月 - 8月)
    # ==========================================================================
    {
        "version": "0.1.0",
        "date": "2025-07-30",
        "description": "项目立项与需求分析",
        "features": [
            "项目正式立项，确定建设目标与应用场景",
            "参与乡村振兴业务需求全面调研",
            "系统功能需求分析与优先级确认",
            "核心业务流程梳理与优化设计",
            "项目总体规划与技术路线确定",
        ],
    },
    {
        "version": "0.2.0",
        "date": "2025-08-31",
        "description": "技术选型与系统架构设计",
        "features": [
            "技术栈选型评估与确定（Python + FastAPI + SQLAlchemy）",
            "前端框架选型（Vue 3 + TypeScript + Element Plus）",
            "桌面壳选型（Electron 28，离线单机架构）",
            "系统架构设计（DDD领域驱动设计分层架构）",
            "数据库设计与ER建模（SQLite 55张表）",
            "前后端接口规范与API协议设计",
            "安全架构设计（JWT认证 + RBAC权限模型）",
        ],
    },

    # ==========================================================================
    # 第二阶段：基础框架搭建 (2025年9月 - 10月)
    # ==========================================================================
    {
        "version": "0.3.0",
        "date": "2025-09-30",
        "description": "后端核心框架搭建",
        "features": [
            "FastAPI应用框架搭建与基础配置",
            "SQLAlchemy 2.0 ORM数据模型定义",
            "JWT认证体系实现（python-jose + bcrypt 10轮加密）",
            "数据库迁移机制（Alembic + 自动列补齐双轨机制）",
            "Pydantic数据验证层（Schema定义与校验）",
            "统一异常处理与JSON响应格式",
            "Logging日志系统配置（按模块分级）",
        ],
    },
    {
        "version": "0.4.0",
        "date": "2025-10-31",
        "description": "前端核心框架搭建",
        "features": [
            "Vue 3 + TypeScript + Vite 项目搭建",
            "Element Plus 2.6 UI组件库集成与主题定制",
            "Vue Router路由配置与导航守卫",
            "Pinia状态管理与模块化Store设计",
            "Axios HTTP客户端封装（拦截器/自动Token刷新）",
            "Composition API模式确立与项目规范制定",
            "ESLint + Prettier代码质量工具链配置",
        ],
    },

    # ==========================================================================
    # 第三阶段：核心业务开发 (2025年11月 - 12月)
    # ==========================================================================
    {
        "version": "0.5.0",
        "date": "2025-11-30",
        "description": "核心业务模块开发 - Phase 1",
        "features": [
            "用户管理模块（注册/登录/Token管理/密码重置）",
            "组织机构管理（帮扶单位组织树，多层级结构）",
            "帮扶村基础信息管理（村庄CRUD + 年度数据录入）",
            "帮扶学校基础信息管理（学校CRUD + 关联村庄）",
            "系统基础配置管理（运行参数/安全策略）",
        ],
    },
    {
        "version": "0.6.0",
        "date": "2025-12-31",
        "description": "业务模块完善 - Phase 2",
        "features": [
            "帮扶项目全生命周期管理（申报/审批/进度/验收）",
            "帮扶资金台账管理（预算编制/收支记录/审计追踪）",
            "政策法规文件管理（分类/检索/附件管理）",
            "Excel数据批量导入导出（村庄/项目/资金数据）",
            "审计日志记录（操作追踪 + 数据变更溯源）",
            "审批工作流引擎（多级审批 + 自定义流程）",
        ],
    },

    # ==========================================================================
    # 第四阶段：功能完善与集成 (2026年1月 - 2月)
    # ==========================================================================
    {
        "version": "0.7.0",
        "date": "2026-01-20",
        "description": "数据可视化与分析功能",
        "features": [
            "Dashboard数据看板（ECharts统计可视化，8类核心指标）",
            "离线地图展示（Leaflet + 离线瓦片，帮扶分布可视化）",
            "数据质量检查与评估（完整性/准确性校验）",
            "报表模板管理与导出（PDF/Excel格式）",
            "消息通知系统（站内消息 + 审批提醒）",
        ],
    },
    {
        "version": "0.8.0",
        "date": "2026-02-10",
        "description": "Electron桌面集成与安装包构建",
        "features": [
            "Electron 28桌面壳集成（主进程/渲染进程通信）",
            "窗口管理（无边框/自适应/系统托盘）",
            "后端子进程管理（PyInstaller打包的FastAPI进程）",
            "前端Vite构建配置与Electron集成",
            "Windows NSIS安装包构建与签名",
            "麒麟V10 DEB安装包构建（x86_64 + ARM64）",
            "系统托盘菜单与快捷键绑定",
            "自动更新机制基础框架",
        ],
    },

    # ==========================================================================
    # 第五阶段：正式发布与迭代 (2026年2月 - 4月)
    # ==========================================================================
    {
        "version": "1.0.0",
        "date": "2026-02-20",
        "description": "首次正式发布 - 系统基础版",
        "features": [
            "基础架构搭建（FastAPI + Vue3 + Electron）",
            "用户认证与JWT授权体系",
            "村庄/学校/项目/资金CRUD管理",
            "SQLite离线单机数据库（55张业务表）",
            "组织管理树与基础数据管理",
            "Dashboard基础统计看板",
            "离线地图展示与帮扶分布",
            "政策法规文件管理",
        ],
    },
    {
        "version": "1.0.1",
        "date": "2026-02-28",
        "description": "功能增强 - 稳定性优化与导入导出",
        "features": [
            "Excel数据批量导入导出全面实现",
            "组织机构管理增强（树形结构/批量操作）",
            "Windows GBK编码兼容性修复",
            "PyInstaller打包路径问题修复",
            "SQLite数据库并发访问优化",
            "前端UI交互细节优化",
            "系统诊断工具完善",
        ],
    },
    {
        "version": "1.0.2",
        "date": "2026-03-05",
        "description": "资金管理增强与数据库优化",
        "features": [
            "资金预算管理模块（fund_budgets）",
            "资金生命周期管理（fund_lifecycle审批工作流）",
            "项目里程碑管理（project_milestones）",
            "工作日志记录功能（work_logs）",
            "数据库迁移双轨机制（Alembic + 自动列补齐）",
            "备份服务事务保护增强",
            "CSRF防护与安全加固",
        ],
    },
    {
        "version": "1.0.3",
        "date": "2026-03-10",
        "description": "性能优化 - 本地缓存与监控体系",
        "features": [
            "diskcache本地磁盘缓存替代内存缓存（100MB限制）",
            "Prometheus监控指标集成",
            "数据库连接池优化与SQLAlchemy N+1查询优化",
            "Metrics模块延迟加载（避免导入错误）",
            "系统性能监控API端点",
            "日志导出服务",
            "数据库健康检查与WAL模式优化",
            "增量备份功能",
        ],
    },
    {
        "version": "1.0.4",
        "date": "2026-03-20",
        "description": "安全加固与注册授权机制",
        "features": [
            "用户注册与通行码机制",
            "机器码绑定与授权验证",
            "登录失败锁定策略（10次失败锁定30分钟）",
            "前端TypeScript全面修复（365→0错误）",
            "CSRF SameSite=Lax + Secure 条件化配置",
            "版本管理与版本号统一",
            "资源限制服务与启动自检增强",
            "10轮全面安全审计与缺陷修复",
        ],
    },
    {
        "version": "1.1.0",
        "date": "2026-04-14",
        "description": "全面优化 - 数据权限体系与代码质量提升",
        "features": [
            "数据权限过滤体系（RBAC + Data Scope，四种范围级别）",
            "资金审批工作流（6个端点：审批/驳回/拨付/启用/完结/审计）",
            "页面跳转闪烁彻底消除（路由同步加载 + 背景色统一）",
            "N+1查询优化与数据库索引补充（高频查询字段全覆盖）",
            "API错误响应规范化（消除HTTP 200返回错误的反模式）",
            "Token刷新机制全面优化（双Token轮换）",
            "缓存失效机制完善（Dashboard/地图联动失效）",
            "中间件异常处理完善（EndOfStream安全处理）",
            "全栈代码质量优化与重复代码清理（22+文件）",
            "菜单权限管理系统（管理员可配置用户可见菜单）",
        ],
    },

    # ==========================================================================
    # 第六阶段：近期优化 (2026年4月22日 - 25日)
    # ==========================================================================
    {
        "version": "1.1.1",
        "date": "2026-04-25",
        "description": "系统功能完善与集成部署优化",
        "features": [
            "空页面功能实现（系统反馈/数据备份/缓存管理/系统监控/消息中心）",
            "离线Mock数据系统（5个村/4所学校/5个项目真实模拟数据）",
            "系统演示PPT自动生成脚本（10个培训演示文稿）",
            "孤儿页面路由全部接入（6个高价值页面）",
            "ConfirmDialog 和 FormBuilder 可访问性改进（ARIA标签/键盘导航）",
            "全面BUG修复（事务完整性/静态文件错误格式统一/测试修复）",
            "集成部署打包恢复（Docker多阶段构建/DEB构建/NSIS安装器）",
            "全平台版本号统一为1.1.0（frontend/electron/config三端同步）",
            "启动脚本编码修复（chcp 65001 + PYTHONIOENCODING=utf-8）",
            "麒麟ARM64构建脚本健壮性增强（Dockerfile.kylin-arm64深度优化）",
        ],
    },
]


class UpdateLogService:
    """系统更新日志服务"""

    def __init__(self, db: Session):
        self.db = db

    def record_update(
        self,
        version: str,
        description: str = "",
        updated_by: str = None,
    ) -> SystemUpdateLog:
        """
        记录一次系统更新

        Args:
            version: 版本号
            description: 更新描述
            updated_by: 更新人（可选）

        Returns:
            创建的更新日志记录
        """
        log_entry = SystemUpdateLog(
            id=str(uuid.uuid4()),
            version=version,
            description=description,
            updated_by=updated_by,
        )
        self.db.add(log_entry)
        safe_commit(self.db)
        self.db.refresh(log_entry)

        logger.info("系统更新已记录: %s", version)
        return log_entry

    def get_update_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by_desc: bool = True,
    ) -> List[SystemUpdateLog]:
        """
        查询更新日志列表

        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数
            order_by_desc: 是否按时间倒序排列

        Returns:
            更新日志记录列表
        """
        query = self.db.query(SystemUpdateLog)

        if order_by_desc:
            query = query.order_by(SystemUpdateLog.created_at.desc())
        else:
            query = query.order_by(SystemUpdateLog.created_at.asc())

        return query.offset(skip).limit(limit).all()

    def get_latest_update(self) -> Optional[SystemUpdateLog]:
        """
        获取最新的更新记录

        Returns:
            最新的更新日志记录，如果没有则返回None
        """
        return self.db.query(SystemUpdateLog).order_by(SystemUpdateLog.created_at.desc()).first()

    def get_update_by_version(self, version: str) -> Optional[SystemUpdateLog]:
        """
        根据版本号获取更新记录

        Args:
            version: 版本号

        Returns:
            更新日志记录，如果没有则返回None
        """
        return self.db.query(SystemUpdateLog).filter(SystemUpdateLog.version == version).first()

    def is_version_recorded(self, version: str) -> bool:
        """
        检查版本是否已记录

        Args:
            version: 版本号

        Returns:
            是否已记录
        """
        count = self.db.query(SystemUpdateLog).filter(SystemUpdateLog.version == version).count()
        return count > 0

    def get_update_count(self) -> int:
        """
        获取更新日志总数

        Returns:
            记录总数
        """
        return self.db.query(SystemUpdateLog).count()

    def _build_version_description(self, version_data: dict) -> str:
        """从版本数据构建完整描述文本"""
        description = version_data["description"]
        if version_data.get("features"):
            features_text = "\n".join(f"- {feature}" for feature in version_data["features"])
            description = f"{description}\n\n更新内容:\n{features_text}"
        return description

    def _create_version_entry(self, version_data: dict, updated_by: str) -> SystemUpdateLog:
        """创建单条版本日志记录"""
        description = self._build_version_description(version_data)
        log_entry = SystemUpdateLog(
            id=str(uuid.uuid4()),
            version=version_data["version"],
            description=description,
            updated_by=updated_by,
        )
        log_entry.created_at = datetime.fromisoformat(version_data["date"] + "T00:00:00")
        return log_entry

    def initialize_version_history(self, updated_by: str = "system", force: bool = False) -> Dict:
        """
        初始化版本历史数据
        如果数据库中没有更新日志记录，则从历史数据初始化

        Args:
            updated_by: 更新人标识
            force: 是否强制重新初始化（清空后重填）

        Returns:
            初始化结果统计
        """
        if force:
            # 强制重新初始化：清空所有记录（系统级操作，不受组织隔离限制）
            deleted = self.db.query(SystemUpdateLog).delete()
            safe_commit(self.db)
            logger.info("强制重新初始化：已删除 %s 条旧记录", deleted)

        # 检查是否已有记录
        existing_count = self.get_update_count()
        if existing_count > 0:
            logger.info("更新日志已存在 %s 条记录，跳过初始化", existing_count)
            return {
                "status": "skipped",
                "message": "更新日志已存在，跳过初始化",
                "existing_count": existing_count,
                "initialized_count": 0,
            }

        # 从历史数据创建记录
        initialized_count = 0
        for version_data in VERSION_HISTORY_DATA:
            log_entry = self._create_version_entry(version_data, updated_by)
            self.db.add(log_entry)
            initialized_count += 1

        if initialized_count > 0:
            safe_commit(self.db)
            logger.info("版本历史初始化完成，共创建 %s 条记录", initialized_count)
        else:
            logger.info("所有版本历史记录已存在，无需初始化")

        return {
            "status": "success",
            "message": f"成功初始化 {initialized_count} 条版本历史记录",
            "initialized_count": initialized_count,
        }

    def sync_version_history(self, updated_by: str = "system") -> Dict:
        """
        同步版本历史数据：检查 VERSION_HISTORY_DATA 中是否有未记录的版本并补充。
        保留已有记录，仅补充缺失版本。

        Args:
            updated_by: 更新人标识

        Returns:
            同步结果统计
        """
        synced_count = 0
        for version_data in VERSION_HISTORY_DATA:
            if not self.is_version_recorded(version_data["version"]):
                log_entry = self._create_version_entry(version_data, updated_by)
                self.db.add(log_entry)
                synced_count += 1

        if synced_count > 0:
            safe_commit(self.db)
            logger.info("版本历史同步完成，共补充 %s 条记录", synced_count)
        else:
            logger.info("版本历史已是最新，无需同步")

        return {
            "status": "success",
            "message": f"同步完成，共补充 {synced_count} 条版本历史记录",
            "synced_count": synced_count,
        }

    def check_and_record_version_change(
        self,
        current_version: str,
        updated_by: str = "system",
    ) -> Optional[Dict]:
        """
        检查版本变更并自动记录

        Args:
            current_version: 当前版本号（从version.json读取）
            updated_by: 更新人标识

        Returns:
            如果版本变更被记录，返回变更信息；否则返回None
        """
        latest = self.get_latest_update()

        if latest is None:
            # 没有任何记录，初始化历史
            result = self.initialize_version_history(updated_by)
            return {
                "action": "initialize",
                "result": result,
            }

        if latest.version != current_version:
            # 版本发生变化，查找版本描述
            description = "系统更新"
            for v_data in VERSION_HISTORY_DATA:
                if v_data["version"] == current_version:
                    description = self._build_version_description(v_data)
                    break

            # 记录更新
            self.record_update(
                version=current_version,
                description=description,
                updated_by=updated_by,
            )

            logger.info("检测到版本变更: %s -> %s", latest.version, current_version)
            return {
                "action": "record_change",
                "old_version": latest.version,
                "new_version": current_version,
            }

        return None  # 版本未变更
