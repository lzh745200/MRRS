"""
数据库健康检查服务
功能：定期检查数据库完整性、性能和状态
"""

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DatabaseHealthService:
    """数据库健康检查服务"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.db_path = self._get_db_path()
        self.monitoring = False
        self._stop_event = threading.Event()
        self.monitor_thread: Optional[threading.Thread] = None

        # 配置参数
        self.integrity_check_interval = 86400  # 完整性检查间隔（秒，默认24小时）
        self.quick_check_interval = 3600  # 快速检查间隔（秒，默认1小时）
        self.vacuum_interval = 604800  # VACUUM间隔（秒，默认7天）
        # WAL checkpoint 间隔（秒，默认1小时）：每小时主动回收 -wal，防止长运行膨胀
        # （历史上每 6 小时的维护因含 VACUUM 被禁用，导致仅剩每日 3:00 一次 checkpoint）
        self.wal_checkpoint_interval = 3600
        # WAL 体积告警阈值（字节，默认 50MB）：超过则记录 WARNING 便于运维察觉
        self.wal_size_warning_bytes = 50 * 1024 * 1024

        # 统计信息
        self.stats = {
            "last_integrity_check": None,
            "last_quick_check": None,
            "last_vacuum": None,
            "last_wal_checkpoint": None,
            "integrity_errors": 0,
            "slow_queries": 0,
            "lock_timeouts": 0,
        }

        # 健康状态
        self.health_status = {
            "status": "unknown",
            "last_check": None,
            "issues": [],
        }

    def _get_db_path(self) -> Path:
        """获取数据库文件路径

        正确处理 config.py model_post_init 转换后的绝对路径，
        以及测试环境中可能出现的 PostgreSQL URL。
        """
        try:
            from app.core.config import settings

            db_url = settings.DATABASE_URL

            if not db_url:
                logger.debug("DATABASE_URL 为空，使用默认路径")
                return self.base_dir / "data" / "rural_revitalization.db"

            # 解析 SQLite URL: sqlite:///path/to/db.db
            if db_url.startswith("sqlite:///"):
                db_file = db_url.replace("sqlite:///", "", 1)
                db_path = Path(db_file)
                # 如果路径已经是绝对路径，直接使用；否则拼接 base_dir
                if db_path.is_absolute():
                    return db_path
                return self.base_dir / db_path

            # 非 SQLite URL（如 PostgreSQL，通常仅在测试中出现）
            # 不记录 ERROR，避免在测试环境中产生大量噪音日志
            logger.debug("非 SQLite 数据库 URL，健康检查使用默认 SQLite 路径: %s", db_url)
            return self.base_dir / "data" / "rural_revitalization.db"
        except Exception as e:
            logger.debug("获取数据库路径失败，使用默认路径: %s", e)
            return self.base_dir / "data" / "rural_revitalization.db"

    def start_monitoring(self):
        """启动健康监控"""
        if self.monitoring:
            logger.warning("数据库健康监控已在运行")
            return

        self._stop_event.clear()
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("数据库健康监控已启动")

    def stop_monitoring(self):
        """停止健康监控 — 通过 Event 立即唤醒监控线程（不再阻塞 5s）"""
        self.monitoring = False
        self._stop_event.set()  # 立即唤醒 sleep 中的监控线程
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        logger.info("数据库健康监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        last_integrity_check = datetime.min
        last_quick_check = datetime.min
        last_vacuum = datetime.min
        last_wal_checkpoint = datetime.min

        while not self._stop_event.is_set():
            try:
                now = datetime.now()

                # 完整性检查（每天一次）— 关闭中跳过
                if not self._stop_event.is_set() and \
                   (now - last_integrity_check).total_seconds() >= self.integrity_check_interval:
                    self.check_integrity()
                    last_integrity_check = now

                # 快速检查（每小时一次）— 关闭中跳过
                if not self._stop_event.is_set() and \
                   (now - last_quick_check).total_seconds() >= self.quick_check_interval:
                    self.quick_check()
                    last_quick_check = now

                # VACUUM优化（每周一次）— 关闭中跳过，避免生成临时文件
                if not self._stop_event.is_set() and \
                   (now - last_vacuum).total_seconds() >= self.vacuum_interval:
                    self.vacuum_database()
                    last_vacuum = now

                # WAL checkpoint（每小时一次）— 关闭中跳过；轻量、不生成临时文件，
                # 主动回收 -wal，防止其随运行时长无限膨胀
                if not self._stop_event.is_set() and \
                   (now - last_wal_checkpoint).total_seconds() >= self.wal_checkpoint_interval:
                    self.checkpoint_wal()
                    last_wal_checkpoint = now

                # 休眠 — 用 Event.wait 替代 time.sleep，stop 时立即唤醒
                self._stop_event.wait(60)

            except Exception as e:
                logger.error(f"数据库健康监控异常: {e}", exc_info=True)
                self._stop_event.wait(60)

    def check_integrity(self) -> Dict:
        """执行完整性检查"""
        logger.info("开始数据库完整性检查...")

        try:
            if not self.db_path.exists():
                error_msg = f"数据库文件不存在: {self.db_path}"
                logger.error(error_msg)
                self.stats["integrity_errors"] += 1
                return {"status": "error", "message": error_msg}

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 执行完整性检查
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()

            conn.close()

            if result and result[0] == "ok":
                logger.info("数据库完整性检查通过")
                self.stats["last_integrity_check"] = datetime.now().isoformat()
                self.health_status = {
                    "status": "healthy",
                    "last_check": datetime.now().isoformat(),
                    "issues": [],
                }
                return {"status": "healthy", "message": "数据库完整性正常"}
            else:
                error_msg = f"数据库完整性检查失败: {result}"
                logger.error(error_msg)
                self.stats["integrity_errors"] += 1
                self.health_status = {
                    "status": "error",
                    "last_check": datetime.now().isoformat(),
                    "issues": [error_msg],
                }
                return {"status": "error", "message": error_msg}

        except Exception as e:
            error_msg = f"数据库完整性检查异常: {e}"
            logger.error(error_msg, exc_info=True)
            self.stats["integrity_errors"] += 1
            self.health_status = {
                "status": "error",
                "last_check": datetime.now().isoformat(),
                "issues": [error_msg],
            }
            return {"status": "error", "message": error_msg}

    def quick_check(self) -> Dict:
        """快速检查（检查数据库连接和基本状态）"""
        logger.debug("执行数据库快速检查...")

        try:
            if not self.db_path.exists():
                return {"status": "error", "message": "数据库文件不存在"}

            conn = sqlite3.connect(str(self.db_path), timeout=5)
            cursor = conn.cursor()

            # 检查数据库是否可访问
            cursor.execute("SELECT 1")
            cursor.fetchone()

            # 获取数据库大小
            db_size = self.db_path.stat().st_size

            # 获取表数量
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]

            conn.close()

            self.stats["last_quick_check"] = datetime.now().isoformat()

            return {
                "status": "ok",
                "db_size": db_size,
                "db_size_mb": round(db_size / 1024 / 1024, 2),
                "table_count": table_count,
            }

        except Exception as e:
            error_msg = f"数据库快速检查失败: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

    def vacuum_database(self) -> Dict:
        """执行VACUUM优化"""
        logger.info("开始数据库VACUUM优化...")

        try:
            if not self.db_path.exists():
                return {"status": "error", "message": "数据库文件不存在"}

            # 获取优化前的大小
            size_before = self.db_path.stat().st_size

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 执行VACUUM
            cursor.execute("VACUUM")

            conn.close()

            # 获取优化后的大小
            size_after = self.db_path.stat().st_size
            saved = size_before - size_after

            self.stats["last_vacuum"] = datetime.now().isoformat()

            logger.info(f"数据库VACUUM完成，节省空间: {saved / 1024 / 1024:.2f}MB")

            return {
                "status": "ok",
                "size_before": size_before,
                "size_after": size_after,
                "saved": saved,
                "saved_mb": round(saved / 1024 / 1024, 2),
            }

        except Exception as e:
            error_msg = f"数据库VACUUM失败: {e}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}

    def checkpoint_wal(self) -> Dict:
        """执行 WAL checkpoint（TRUNCATE）并检查 -wal 体积。

        轻量操作：仅将 WAL 内容写回主库并将 -wal 截断，不生成临时文件，
        因此可高频（默认每小时）执行，避免长运行导致 -wal 无限膨胀。
        """
        try:
            if not self.db_path.exists():
                return {"status": "error", "message": "数据库文件不存在"}

            wal_path = Path(str(self.db_path) + "-wal")
            size_before = wal_path.stat().st_size if wal_path.exists() else 0

            conn = sqlite3.connect(str(self.db_path), timeout=5)
            cursor = conn.cursor()
            # TRUNCATE：checkpoint 并将 -wal 截断为 0 字节
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            result = cursor.fetchone()
            conn.close()

            size_after = wal_path.stat().st_size if wal_path.exists() else 0
            self.stats["last_wal_checkpoint"] = datetime.now().isoformat()

            if size_after > self.wal_size_warning_bytes:
                logger.warning(
                    "WAL 文件偏大: %.2f MB（阈值 %.0f MB），可能存在长事务或持续写入",
                    size_after / 1024 / 1024,
                    self.wal_size_warning_bytes / 1024 / 1024,
                )

            logger.debug("WAL checkpoint 完成: %s → %s 字节", size_before, size_after)
            return {
                "status": "ok",
                "size_before": size_before,
                "size_after": size_after,
                "checkpoint_result": result,
            }
        except Exception as e:
            error_msg = f"WAL checkpoint 失败: {e}"
            logger.warning(error_msg)
            return {"status": "error", "message": error_msg}

    def check_indexes(self) -> Dict:
        """检查索引完整性"""
        logger.info("检查数据库索引...")

        try:
            if not self.db_path.exists():
                return {"status": "error", "message": "数据库文件不存在"}

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 获取所有索引
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
            indexes = cursor.fetchall()

            # 检查每个索引
            issues = []
            for (index_name,) in indexes:
                try:
                    cursor.execute(f"PRAGMA index_info({index_name})")
                    cursor.fetchall()
                except Exception as e:
                    issues.append(f"索引 {index_name} 异常: {e}")

            conn.close()

            if issues:
                return {
                    "status": "warning",
                    "index_count": len(indexes),
                    "issues": issues,
                }
            else:
                return {
                    "status": "ok",
                    "index_count": len(indexes),
                    "message": "所有索引正常",
                }

        except Exception as e:
            error_msg = f"检查索引失败: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

    def analyze_database(self) -> Dict:
        """分析数据库统计信息"""
        logger.info("分析数据库统计信息...")

        try:
            if not self.db_path.exists():
                return {"status": "error", "message": "数据库文件不存在"}

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 执行ANALYZE
            cursor.execute("ANALYZE")

            conn.close()

            logger.info("数据库统计信息分析完成")

            return {"status": "ok", "message": "统计信息已更新"}

        except Exception as e:
            error_msg = f"分析数据库失败: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

    def get_database_info(self) -> Dict:
        """获取数据库详细信息"""
        try:
            if not self.db_path.exists():
                return {"status": "error", "message": "数据库文件不存在"}

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 数据库大小
            db_size = self.db_path.stat().st_size

            # 表数量
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]

            # 索引数量
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
            index_count = cursor.fetchone()[0]

            # 页大小
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            # 页数量
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]

            # 空闲页数量
            cursor.execute("PRAGMA freelist_count")
            freelist_count = cursor.fetchone()[0]

            conn.close()

            return {
                "status": "ok",
                "db_path": str(self.db_path),
                "db_size": db_size,
                "db_size_mb": round(db_size / 1024 / 1024, 2),
                "table_count": table_count,
                "index_count": index_count,
                "page_size": page_size,
                "page_count": page_count,
                "freelist_count": freelist_count,
                "fragmentation": (round(freelist_count / page_count * 100, 2) if page_count > 0 else 0),
            }

        except Exception as e:
            error_msg = f"获取数据库信息失败: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

    def get_health_status(self) -> Dict:
        """获取健康状态"""
        return {
            **self.health_status,
            "stats": self.stats,
            "monitoring": self.monitoring,
        }

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.stats.copy()

    def startup_check(self) -> Dict:
        """
        启动自检：立即执行一次 quick_check（不阻塞启动，异常不抛出）。

        单机场景：硬盘故障/断电可能损坏数据库，启动自检可在第一时间
        发现问题并提示用户用最近备份恢复。
        """
        try:
            return self.quick_check()
        except Exception as e:  # pragma: no cover - 防御性兜底
            logger.error("启动自检失败: %s", e)
            return {"status": "error", "message": f"启动自检失败: {e}"}


# 全局实例
database_health_service = DatabaseHealthService()
