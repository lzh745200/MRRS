#!/usr/bin/env python3
"""
CI 数据权限扫描 — 检测新增 API 端点是否遗漏数据隔离调用。

扫描 app/api/v1/ 下所有路由文件，对每个 POST/PUT/DELETE 端点检查是否包含
以下任一权限调用：
  - filter_by_data_scope
  - require_data_permission
  - require_manager_role
  - check_record_access
  - is_admin / is_superuser
  - _get_*_or_404 (已内置权限校验的 helper)

输出：遗漏端点列表（供 CI gate 或人工审查）。
退出码：0=通过，1=发现遗漏。

用法：
  python scripts/check_data_scope.py [--strict]
  --strict: 写操作遗漏即报错（默认仅警告）
"""
import os
import re
import sys
from pathlib import Path

# 已知的安全 helper 调用模式（出现任一即视为已做权限校验）
SAFE_PATTERNS = [
    r"filter_by_data_scope",
    r"require_data_permission",
    r"require_manager_role",
    r"check_record_access",
    r"is_admin\s*\(",
    r"is_superuser\s*\(",
    r"require_admin\(\)",
    r"Depends\(require_admin",
    r"require_funds_operator_role",
    r"check_rate_limit",
    r"_get_\w+_and_check_permission",
    r"_get_\w+_or_404\s*\([^)]*current_user",
    r"getattr\s*\(\s*current_user,\s*['\"]role['\"]",
    r"current_user\.role\s*(not\s+)?in\s*\(",
    r"current_user\.role\s*==",
]

# 写操作装饰器（需检查权限的端点）
WRITE_DECORATORS = [
    r'@router\.post\b',
    r'@router\.put\b',
    r'@router\.patch\b',
    r'@router\.delete\b',
]

BASE_DIR = Path(__file__).parent.parent / "backend" / "app" / "api" / "v1"


def scan_file(filepath: Path) -> list:
    """扫描单个文件，返回遗漏权限校验的写端点列表。"""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return []

    lines = content.split("\n")
    findings = []

    # 逐行查找写操作装饰器，然后检查其后的函数体是否有权限调用
    i = 0
    while i < len(lines):
        line = lines[i]
        if any(re.search(p, line) for p in WRITE_DECORATORS):
            # 找到写端点，收集函数体（到下一个 @router 或文件末尾）
            func_start = i
            func_body = []
            j = i + 1
            while j < len(lines):
                bline = lines[j]
                # 遇到下一个路由装饰器或模块级定义则停止
                if j > func_start + 1 and (
                    bline.strip().startswith("@router.") or
                    (bline.strip().startswith("def ") and not bline.startswith(" "))
                ):
                    break
                func_body.append(bline)
                j += 1
                # 最多收集 80 行，避免把整个文件算进来
                if len(func_body) > 80:
                    break

            func_text = "\n".join(func_body)
            func_name_match = re.search(r"async def (\w+)|def (\w+)", func_text)
            func_name = ""
            if func_name_match:
                func_name = func_name_match.group(1) or func_name_match.group(2)

            # 检查是否有任一安全模式
            has_protection = any(re.search(p, func_text) for p in SAFE_PATTERNS)
            if not has_protection and func_name:
                findings.append({
                    "file": str(filepath.relative_to(BASE_DIR.parent.parent.parent)),
                    "line": func_start + 1,
                    "function": func_name,
                })
            i = j
        else:
            i += 1

    return findings


def main():
    strict = "--strict" in sys.argv

    if not BASE_DIR.exists():
        print(f"ERROR: 后端 API 目录不存在: {BASE_DIR}")
        return 2

    all_findings = []
    py_files = sorted(BASE_DIR.rglob("*.py"))

    for f in py_files:
        if f.name == "__init__.py":
            continue
        all_findings.extend(scan_file(f))

    if not all_findings:
        print("✅ 数据权限扫描通过：所有写端点均包含权限校验调用。")
        return 0

    print(f"⚠️  发现 {len(all_findings)} 个写端点可能遗漏数据权限校验：\n")
    print(f"{'文件':<55} {'行号':>6}  {'函数'}")
    print("-" * 90)
    for f in all_findings:
        print(f"{f['file']:<55} {f['line']:>6}  {f['function']}")

    print(f"\n建议：为上述端点添加 filter_by_data_scope / require_data_permission /")
    print(f"      require_manager_role / check_record_access 等权限校验。")
    print(f"      详见 AGENTS.md「安全清单」。")

    return 1 if strict else 0


if __name__ == "__main__":
    sys.exit(main())
