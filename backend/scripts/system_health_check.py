#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统健康检查脚本
检查系统配置、依赖、数据库、文件权限等
"""
import sys
import sqlite3
from pathlib import Path
import importlib.util

# 设置Windows控制台UTF-8编码
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

class SystemHealthChecker:
    """系统健康检查器"""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []

    def check_python_version(self):
        """检查Python版本"""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 11):
            self.errors.append(f"Python版本过低: {version.major}.{version.minor}, 需要 >= 3.11")
        else:
            self.info.append(f"[OK] Python版本: {version.major}.{version.minor}.{version.micro}")

    def check_dependencies(self):
        """检查关键依赖"""
        required_packages = [
            'fastapi',
            'uvicorn',
            'sqlalchemy',
            'pydantic',
            'bcrypt',
            'jwt',  # PyJWT（替代 python-jose）
            'httpx',
            'openpyxl',
            'pandas'
        ]

        for package in required_packages:
            try:
                spec = importlib.util.find_spec(package)
                if spec is None:
                    self.errors.append(f"缺少依赖包: {package}")
                else:
                    self.info.append(f"[OK] 依赖包已安装: {package}")
            except Exception as e:
                self.errors.append(f"检查依赖包 {package} 失败: {e}")

    def check_directories(self):
        """检查必要的目录"""
        base_dir = Path(__file__).parent.parent.parent
        required_dirs = [
            'data',
            'logs',
            'uploads',
            'backups',
            'exports'
        ]

        for dir_name in required_dirs:
            dir_path = base_dir / dir_name
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self.info.append(f"[OK] 创建目录: {dir_name}")
                except Exception as e:
                    self.errors.append(f"无法创建目录 {dir_name}: {e}")
            else:
                # 检查写权限
                test_file = dir_path / '.write_test'
                try:
                    test_file.touch()
                    test_file.unlink()
                    self.info.append(f"[OK] 目录可写: {dir_name}")
                except Exception as e:
                    self.errors.append(f"目录 {dir_name} 无写权限: {e}")

    def check_database(self):
        """检查数据库"""
        base_dir = Path(__file__).parent.parent.parent
        db_path = base_dir / 'data' / 'rural_revitalization.db'

        if not db_path.exists():
            self.warnings.append(f"数据库文件不存在: {db_path}")
            self.info.append("首次运行时将自动创建数据库")
        else:
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()

                # 检查表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()

                if len(tables) == 0:
                    self.warnings.append("数据库为空，需要运行迁移")
                else:
                    self.info.append(f"[OK] 数据库包含 {len(tables)} 个表")

                # 检查数据库大小
                db_size = db_path.stat().st_size / (1024 * 1024)  # MB
                self.info.append(f"[OK] 数据库大小: {db_size:.2f} MB")

                conn.close()
            except Exception as e:
                self.errors.append(f"数据库检查失败: {e}")

    def check_env_file(self):
        """检查环境变量文件"""
        base_dir = Path(__file__).parent.parent.parent
        env_file = base_dir / '.env'
        env_example = base_dir / '.env.example'

        if not env_file.exists():
            if env_example.exists():
                self.warnings.append(".env 文件不存在，请复制 .env.example 并配置")
            else:
                self.errors.append(".env 和 .env.example 文件都不存在")
        else:
            self.info.append("[OK] .env 文件存在")

            # 检查关键配置项
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()

            required_keys = ['SECRET_KEY', 'DATABASE_URL']
            for key in required_keys:
                if key not in content:
                    self.warnings.append(f".env 缺少配置项: {key}")
                elif 'change-in-production' in content or 'your-secret-key' in content:
                    self.warnings.append(f"请修改 {key} 的默认值")

    def check_port_availability(self):
        """检查端口可用性"""
        import socket

        ports_to_check = [8000]  # 后端端口

        for port in ports_to_check:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()

            if result == 0:
                self.warnings.append(f"端口 {port} 已被占用")
            else:
                self.info.append(f"[OK] 端口 {port} 可用")

    def run_all_checks(self):
        """运行所有检查"""
        print("=" * 60)
        print("系统健康检查")
        print("=" * 60)
        print()

        checks = [
            ("Python版本", self.check_python_version),
            ("依赖包", self.check_dependencies),
            ("目录结构", self.check_directories),
            ("数据库", self.check_database),
            ("环境配置", self.check_env_file),
            ("端口可用性", self.check_port_availability)
        ]

        for name, check_func in checks:
            print(f"检查 {name}...")
            try:
                check_func()
            except Exception as e:
                self.errors.append(f"{name} 检查失败: {e}")
            print()

        # 输出结果
        print("=" * 60)
        print("检查结果")
        print("=" * 60)
        print()

        if self.info:
            print("[OK] 信息:")
            for msg in self.info:
                print(f"  {msg}")
            print()

        if self.warnings:
            print("[WARN] 警告:")
            for msg in self.warnings:
                print(f"  {msg}")
            print()

        if self.errors:
            print("[ERROR] 错误:")
            for msg in self.errors:
                print(f"  {msg}")
            print()
            print("系统存在严重问题，请修复后再启动")
            return False
        elif self.warnings:
            print("系统可以运行，但建议修复警告项")
            return True
        else:
            print("[OK] 系统健康，可以正常运行")
            return True

if __name__ == '__main__':
    checker = SystemHealthChecker()
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)
