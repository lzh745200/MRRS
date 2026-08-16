"""
日志导出服务
功能：收集、脱敏、打包日志文件，生成诊断报告
"""

import logging
import os
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LogExportService:
    """日志导出服务"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.logs_dir = self.base_dir / "logs"
        self.export_dir = self.base_dir / "exports" / "error_reports"
        try:
            self.export_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"创建导出目录失败: {e}")

        # 脱敏规则
        self.sensitive_patterns = {
            "password": re.compile(
                r'("password"|"hashed_password"|password=|hashed_password=)["\']?[^"\'}\s,]+["\']?',
                re.IGNORECASE,
            ),
            "token": re.compile(
                r'("token"|"access_token"|"refresh_token"|token=|access_token=|refresh_token=)["\']?[^"\'}\s,]+["\']?',
                re.IGNORECASE,
            ),
            "secret": re.compile(
                r'("secret_key"|"api_key"|"secret"|secret_key=|api_key=)["\']?[^"\'}\s,]+["\']?',
                re.IGNORECASE,
            ),
            "authorization": re.compile(r"(Authorization:\s*Bearer\s+)[^\s]+", re.IGNORECASE),
        }

    def generate_report(
        self,
        report_id: Optional[str] = None,
        time_range_hours: int = 24,
        log_level: str = "ERROR",
    ) -> Dict:
        """
        生成错误报告

        Args:
            report_id: 报告ID（可选，自动生成）
            time_range_hours: 时间范围（小时）
            log_level: 日志级别过滤

        Returns:
            报告信息字典
        """
        try:
            # 生成报告ID
            if not report_id:
                report_id = f"ERR-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            logger.info(f"开始生成错误报告: {report_id}")

            # 创建报告目录
            report_dir = self.export_dir / report_id
            report_dir.mkdir(parents=True, exist_ok=True)

            # 收集日志文件
            log_files = self._collect_log_files(time_range_hours)
            logger.info(f"找到 {len(log_files)} 个日志文件")

            # 脱敏并复制日志
            sanitized_files = []
            for log_file in log_files:
                sanitized_file = self._sanitize_log_file(log_file, report_dir)
                if sanitized_file:
                    sanitized_files.append(sanitized_file)

            # 生成诊断报告
            self._generate_diagnostic_report(report_dir)

            # 打包为ZIP
            zip_path = self._create_zip_archive(report_id, report_dir, sanitized_files)

            # 清理临时文件
            self._cleanup_temp_files(report_dir)

            report_info = {
                "report_id": report_id,
                "generated_at": datetime.now().isoformat(),
                "zip_path": str(zip_path),
                "zip_size": zip_path.stat().st_size,
                "files_count": len(sanitized_files) + 1,  # +1 for diagnostic report
                "time_range_hours": time_range_hours,
            }

            logger.info(f"错误报告生成成功: {report_id}")
            return report_info

        except Exception as e:
            logger.error(f"生成错误报告失败: {e}", exc_info=True)
            raise

    def _collect_log_files(self, time_range_hours: int) -> List[Path]:
        """收集指定时间范围内的日志文件"""
        log_files = []
        cutoff_time = datetime.now() - timedelta(hours=time_range_hours)

        if not self.logs_dir.exists():
            logger.warning(f"日志目录不存在: {self.logs_dir}")
            return log_files

        for log_file in self.logs_dir.glob("*.log"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime >= cutoff_time:
                    log_files.append(log_file)
            except Exception as e:
                logger.warning(f"检查日志文件失败 {log_file}: {e}")

        return sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)

    def _sanitize_log_file(self, log_file: Path, output_dir: Path) -> Optional[Path]:
        """脱敏日志文件"""
        try:
            output_file = output_dir / log_file.name

            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # 应用脱敏规则
            sanitized_content = self._apply_sanitization(content)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(sanitized_content)

            return output_file

        except Exception as e:
            logger.error(f"脱敏日志文件失败 {log_file}: {e}")
            return None

    def _apply_sanitization(self, content: str) -> str:
        """应用脱敏规则"""
        sanitized = content

        # 密码字段
        sanitized = self.sensitive_patterns["password"].sub(r'\1"***REDACTED***"', sanitized)

        # Token字段
        sanitized = self.sensitive_patterns["token"].sub(r'\1"***TOKEN***"', sanitized)

        # 密钥字段
        sanitized = self.sensitive_patterns["secret"].sub(r'\1"***SECRET***"', sanitized)

        # Authorization头
        sanitized = self.sensitive_patterns["authorization"].sub(r"\1***BEARER_TOKEN***", sanitized)

        return sanitized

    def _write_system_info(self, f) -> None:
        """写入系统信息"""
        import platform
        import sys
        f.write("[系统信息]\n")
        f.write(f"操作系统: {platform.system()} {platform.release()}\n")
        f.write(f"Python版本: {sys.version}\n")
        f.write(f"架构: {platform.machine()}\n")
        f.write(f"处理器: {platform.processor()}\n\n")

    def _write_app_info(self, f) -> None:
        """写入应用信息"""
        f.write("[应用信息]\n")
        try:
            from app.core.config import settings
            f.write(f"项目名称: {settings.PROJECT_NAME}\n")
            f.write(f"项目版本: {settings.PROJECT_VERSION}\n")
            f.write(f"调试模式: {settings.DEBUG}\n")
        except Exception as e:
            f.write(f"无法获取应用信息: {e}\n")
        f.write("\n")

    def _write_performance_metrics(self, f) -> None:
        """写入性能指标"""
        f.write("[性能指标]\n")
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(os.environ.get("SystemDrive", "C:\\"))
            f.write(f"CPU使用率: {cpu_percent}%\n")
            memory_used_gb = memory.used / 1024 / 1024 / 1024
            memory_total_gb = memory.total / 1024 / 1024 / 1024
            f.write(f"内存使用: {memory_used_gb:.2f}GB / {memory_total_gb:.2f}GB ({memory.percent}%)\n")
            disk_used_gb = disk.used / 1024 / 1024 / 1024
            disk_total_gb = disk.total / 1024 / 1024 / 1024
            f.write(f"磁盘使用: {disk_used_gb:.2f}GB / {disk_total_gb:.2f}GB ({disk.percent}%)\n")
        except ImportError:  # pragma: no cover
            f.write("psutil未安装，无法获取性能指标\n")
        except Exception as e:
            f.write(f"获取性能指标失败: {e}\n")
        f.write("\n")

    def _write_db_status(self, f) -> None:
        """写入数据库状态"""
        f.write("[数据库状态]\n")
        try:
            from app.core.database import SessionLocal
            db = SessionLocal()
            try:
                from sqlalchemy import text
                db.execute(text("SELECT 1"))
                f.write("数据库连接: 正常\n")
            except Exception as e:
                f.write(f"数据库连接: 失败 - {e}\n")
            finally:
                db.close()
        except Exception as e:
            f.write(f"数据库检查失败: {e}\n")
        f.write("\n")

    def _write_env_vars(self, f) -> None:
        """写入环境变量（脱敏）"""
        f.write("[环境变量]\n")
        sensitive_env_keys = ["PASSWORD", "SECRET", "KEY", "TOKEN", "CREDENTIAL"]
        for key, value in sorted(os.environ.items()):
            if any(s in key.upper() for s in sensitive_env_keys):
                f.write(f"{key}=***REDACTED***\n")
            else:
                f.write(f"{key}={value}\n")
        f.write("\n")

    def _write_dependencies(self, f) -> None:
        """写入依赖包版本"""
        f.write("[依赖包版本]\n")
        try:
            import pkg_resources
            installed_packages = [f"{pkg.key}=={pkg.version}" for pkg in pkg_resources.working_set]
            for pkg in sorted(installed_packages):
                f.write(f"{pkg}\n")
        except Exception as e:
            f.write(f"获取依赖包版本失败: {e}\n")

    def _generate_diagnostic_report(self, output_dir: Path) -> Path:
        """生成诊断报告"""
        report_file = output_dir / "diagnostic_report.txt"

        try:
            with open(report_file, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n系统诊断报告\n" + "=" * 80 + "\n\n")
                self._write_system_info(f)
                self._write_app_info(f)
                self._write_performance_metrics(f)
                self._write_db_status(f)
                self._write_env_vars(f)
                self._write_dependencies(f)
                f.write("\n" + "=" * 80 + "\n报告生成时间: " + datetime.now().isoformat() + "\n" + "=" * 80 + "\n")
            return report_file
        except Exception as e:
            logger.error(f"生成诊断报告失败: {e}", exc_info=True)
            raise

    def _create_zip_archive(self, report_id: str, report_dir: Path, files: List[Path]) -> Path:
        """创建ZIP压缩包"""
        zip_path = self.export_dir / f"{report_id}.zip"

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # 添加诊断报告
                diagnostic_file = report_dir / "diagnostic_report.txt"
                if diagnostic_file.exists():
                    zipf.write(diagnostic_file, "diagnostic_report.txt")

                # 添加日志文件（只添加存在的文件）
                for file in files:
                    if file.exists():
                        zipf.write(file, f"logs/{file.name}")
                    else:
                        logger.warning(f"日志文件不存在，跳过: {file}")

            logger.info(f"ZIP压缩包创建成功: {zip_path}")
            return zip_path

        except Exception as e:
            logger.error(f"创建ZIP压缩包失败: {e}", exc_info=True)
            raise

    def _cleanup_temp_files(self, report_dir: Path):
        """清理临时文件"""
        try:
            import shutil

            if report_dir.exists():
                shutil.rmtree(report_dir, ignore_errors=True)
                logger.debug(f"临时目录已清理: {report_dir}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")

    def list_reports(self, limit: int = 10) -> List[Dict]:
        """列出所有错误报告"""
        reports = []

        try:
            for zip_file in sorted(
                self.export_dir.glob("ERR-*.zip"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )[:limit]:
                reports.append(
                    {
                        "report_id": zip_file.stem,
                        "created_at": datetime.fromtimestamp(zip_file.stat().st_mtime).isoformat(),
                        "size": zip_file.stat().st_size,
                        "path": str(zip_file),
                    }
                )

        except Exception as e:
            logger.error(f"列出错误报告失败: {e}")

        return reports

    def get_report_path(self, report_id: str) -> Optional[Path]:
        """获取报告文件路径"""
        zip_path = self.export_dir / f"{report_id}.zip"
        return zip_path if zip_path.exists() else None

    def delete_report(self, report_id: str) -> bool:
        """删除错误报告"""
        try:
            zip_path = self.export_dir / f"{report_id}.zip"
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except FileNotFoundError:
                    pass
                logger.info(f"错误报告已删除: {report_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除错误报告失败: {e}")
            return False

    def cleanup_old_reports(self, retention_days: int = 7):
        """清理过期的错误报告"""
        try:
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            deleted_count = 0

            for zip_file in self.export_dir.glob("ERR-*.zip"):
                mtime = datetime.fromtimestamp(zip_file.stat().st_mtime)
                if mtime < cutoff_time:
                    try:
                        zip_file.unlink()
                    except FileNotFoundError:
                        continue
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(f"已清理 {deleted_count} 个过期错误报告")

        except Exception as e:
            logger.error(f"清理过期报告失败: {e}")


# 全局实例
log_export_service = LogExportService()
