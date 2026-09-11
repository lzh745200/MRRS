#!/usr/bin/env python3
"""
综合安全审计脚本 — CI 门禁

检查项:
  1. 裸 db.commit() — app/ 全目录（API + services + core + middleware）
  2. 缺少 filter_by_data_scope 的组织模型查询
  3. 写操作缺少 write_work_log
  4. 列表端点未使用 ok_list()
  5. 跨组织批量删除（db.query(Model).delete() 无 filter）

用法:
  python scripts/security_audit.py [--strict] [--verbose]
  --strict: 发现任何违规即返回非零退出码（CI 模式）
  --verbose: 打印详细信息（含被豁免项）

受控豁免（见下方 EXEMPTION_RE）:
  在模块内以顶层注释声明 `# security-audit: exempt <rule> — <reason>` 可将
  该模块从对应扫描项豁免；理由须 ≥8 字符，否则标记不生效。豁免项不计入
  total，故 --strict 在真阳性全部修复后退出 0。
"""

import os
import re
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_APP = PROJECT_ROOT / "backend" / "app"

# 带有 organization_id 的模型
ORG_MODELS = {
    "fund", "fund_allocation_order", "fund_budget", "machine_code",
    "project", "school", "supported_village", "user", "user_organization", "village",
}

# 需要审计写操作的模块
WRITE_OP_MODULES = [
    "ai", "ai_enhanced", "approval", "batch_operations", "data_quality",
    "effectiveness", "encryption", "feedback", "machine_code", "map",
    "menus", "messages", "messages_extended", "offline_map", "organization",
    "performance", "permission_package", "policy", "project_milestones",
    "rural_tasks", "sentiment", "supported_village", "todos",
    "user_permissions", "validation",
]

# ── 受控豁免机制（R26-T01）──────────────────────────────────────────────
# 豁免指令约定：位于模块文件内任意位置（推荐文件头 docstring 之后 / import 之前），
# 必须携带【不可为空且 ≥8 字符】的理由，否则标记不生效：
#     # security-audit: exempt <rule> — <reason>
# <rule> ∈ {commit, work_log, data_scope}
#
# 防滥用硬约束：
#   1. 理由串必须 ≥8 字符；无理由/空理由的标记【不生效】。
#   2. --verbose/--strict 下被豁免项仍打印（`exempt: <rel_path> — <reason>`），
#      保持可见、不可静默。
#   3. 豁免项【不计入 total】，使 --strict 在真阳性全部修复后可退出 0。
EXEMPTION_RE = re.compile(
    r"#\s*security-audit:\s*exempt\s+(commit|work_log|data_scope)\b[^\n]*?[—\-–:]\s*(\S.{7,})"
)

EXEMPTION_RULES = ("commit", "work_log", "data_scope")


def _find_exemption(content: str, rule: str) -> str | None:
    """返回豁免理由（≥8 字符）；无有效豁免返回 None。

    仅当标记的规则名与 ``rule`` 完全一致时才视为命中——规则名不匹配
    不会误伤其它扫描项。无理由（或理由 <8 字符）的标记【不生效】。
    """
    for m in EXEMPTION_RE.finditer(content):
        if m.group(1) == rule:
            return m.group(2).strip()
    return None


def scan_bare_db_commit(verbose=False):
    """扫描 app/ 全目录的裸 db.commit()"""
    violations = []
    # 排除 transaction.py —— safe_commit/transactional/with_transaction 的实现文件，
    # 其内部的 db.commit() 是事务管理本身的核心调用，不应使用 safe_commit（递归）
    EXCLUDE_FILES = {'transaction.py'}
    for root, dirs, files in os.walk(BACKEND_APP):
        for f in files:
            if not f.endswith(".py"):
                continue
            if f in EXCLUDE_FILES:
                continue
            fp = os.path.join(root, f)
            rel_path = os.path.relpath(fp, PROJECT_ROOT)
            try:
                with open(fp, encoding="utf-8") as fh:
                    content = fh.read()
            except Exception:
                continue

            # 查找裸 db.commit()（不在 try/except 内的）
            # 跳过带 # noqa 注释的行（DDL/PRAGMA 操作允许直接 commit）
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped == "db.commit()":
                    violations.append(f"  {rel_path}:{i} — bare db.commit()")
                elif stripped.startswith("db.commit()") and "# noqa" in stripped:
                    pass  # 显式标记为 noqa，跳过
    if verbose:
        if violations:
            print(f"[bare db.commit] Found {len(violations)} violations")
        else:
            print("[bare db.commit] OK — all commits use safe_commit()")
    return violations


def scan_cross_org_delete(verbose=False):
    """扫描跨组织批量删除（db.query(Model).delete() 无 filter）"""
    violations = []
    pattern = re.compile(r"db\.query\((\w+)\)\.delete\(\)")
    for root, dirs, files in os.walk(BACKEND_APP):
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(root, f)
            rel_path = os.path.relpath(fp, PROJECT_ROOT)
            try:
                with open(fp, encoding="utf-8") as fh:
                    content = fh.read()
            except Exception:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                m = pattern.search(line)
                if m:
                    model_name = m.group(1).lower()
                    # 只检查有 organization_id 的模型——系统级模型（如 SystemUpdateLog）
                    # 不受组织隔离限制，无需 filter
                    if model_name not in ORG_MODELS:
                        continue
                    # 检查前一行是否有 filter
                    lines = content.splitlines()
                    prev_line = lines[i - 2] if i >= 2 else ""
                    if "filter" not in prev_line.lower() and "filter_by_data_scope" not in prev_line.lower():
                        violations.append(
                            f"  {rel_path}:{i} — db.query({m.group(1)}).delete() without filter"
                        )
    if verbose:
        if violations:
            print(f"[cross-org delete] Found {len(violations)} violations")
        else:
            print("[cross-org delete] OK — all deletes are filtered")
    return violations


def scan_missing_ok_list(verbose=False):
    """扫描列表端点未使用 ok_list()"""
    violations = []
    # 匹配 return {"items": ..., "total": ...} 模式（bare dict 而非 ok_list）
    pattern = re.compile(r'return\s*\{[^}]*"items"[^}]*"total"')
    for root, dirs, files in os.walk(BACKEND_APP / "api"):
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(root, f)
            rel_path = os.path.relpath(fp, PROJECT_ROOT)
            try:
                with open(fp, encoding="utf-8") as fh:
                    content = fh.read()
            except Exception:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"  {rel_path}:{i} — bare dict with items/total, use ok_list()")
    if verbose:
        if violations:
            print(f"[ok_list] Found {len(violations)} violations")
        else:
            print("[ok_list] OK — all list endpoints use ok_list()")
    return violations


def scan_missing_write_work_log(verbose=False):
    """扫描写操作缺少 write_work_log 的模块"""
    violations = []
    for module_name in WRITE_OP_MODULES:
        # 查找模块文件
        module_paths = [
            BACKEND_APP / "api" / "v1" / f"{module_name}.py",
            BACKEND_APP / "api" / "v1" / "system" / f"{module_name}.py",
            BACKEND_APP / "api" / "v1" / "auth" / f"{module_name}.py",
        ]
        for fp in module_paths:
            if not fp.exists():
                continue
            rel_path = os.path.relpath(fp, PROJECT_ROOT)
            try:
                with open(fp, encoding="utf-8") as fh:
                    content = fh.read()
            except Exception:
                continue

            # 检查是否有写操作（POST/PUT/DELETE 路由）
            has_write_ops = bool(
                re.search(r'@router\.(post|put|delete|patch)', content)
            )
            if not has_write_ops:
                continue

            # 受控豁免：显式豁免标记（须带 ≥8 字符理由）在 has_work_log 判定【之前】生效。
            # 豁免项不计入 total，但仍需可见（--verbose/--strict 时打印理由）。
            exemption = _find_exemption(content, "work_log")
            if exemption:
                if verbose:
                    print(f"  exempt: {rel_path} — {exemption}")
                break

            # 检查是否调用了 write_work_log
            has_work_log = "write_work_log" in content

            if not has_work_log:
                violations.append(
                    f"  {rel_path} — has write operations but no write_work_log call"
                )
            break
    if verbose:
        if violations:
            print(f"[write_work_log] Found {len(violations)} violations")
        else:
            print("[write_work_log] OK — all write modules call write_work_log")
    return violations


def scan_missing_data_scope(verbose=False):
    """扫描有组织模型的查询缺少 filter_by_data_scope"""
    violations = []
    for root, dirs, files in os.walk(BACKEND_APP / "api"):
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(root, f)
            rel_path = os.path.relpath(fp, PROJECT_ROOT)
            try:
                with open(fp, encoding="utf-8") as fh:
                    content = fh.read()
            except Exception:
                continue

            # 检查是否查询了有 organization_id 的模型
            has_org_model_query = False
            for model in ORG_MODELS:
                # 类名首字母大写
                class_name = "".join(
                    w.capitalize() for w in model.split("_")
                )
                if f"db.query({class_name})" in content or f"db.query({class_name}," in content:
                    has_org_model_query = True
                    break

            if not has_org_model_query:
                continue

            # 受控豁免：显式豁免标记（须带 ≥8 字符理由）在 has_data_scope 判定【之前】生效。
            # 豁免项不计入 total，但仍需可见（--verbose/--strict 时打印理由）。
            exemption = _find_exemption(content, "data_scope")
            if exemption:
                if verbose:
                    print(f"  exempt: {rel_path} — {exemption}")
                continue

            # 检查是否调用了任何形式的数据权限过滤
            # 项目有三种等效实现：filter_by_data_scope / apply_data_scope / OrgScopeFilter.filter_by_org_ids
            has_data_scope = any(pattern in content for pattern in [
                "filter_by_data_scope",
                "apply_data_scope",
                "apply_scope_filter",
                "filter_by_org_ids",
                "apply_scope_to_query",
            ])

            if not has_data_scope:
                violations.append(
                    f"  {rel_path} — queries org models but may not use filter_by_data_scope"
                )
    if verbose:
        if violations:
            print(f"[filter_by_data_scope] Found {len(violations)} warnings")
        else:
            print("[filter_by_data_scope] OK — all org model queries use filter_by_data_scope")
    return violations


def main():
    strict = "--strict" in sys.argv
    verbose = "--verbose" in sys.argv or strict

    print("=" * 60)
    print("综合安全审计")
    print("=" * 60)

    all_violations = []

    print("\n--- Scan 1: Bare db.commit() (app/ 全目录) ---")
    v = scan_bare_db_commit(verbose)
    all_violations.extend(v)
    for item in v:
        print(item)
    if not v:
        print("  OK")

    print("\n--- Scan 2: Cross-org batch delete ---")
    v = scan_cross_org_delete(verbose)
    all_violations.extend(v)
    for item in v:
        print(item)
    if not v:
        print("  OK")

    print("\n--- Scan 3: List endpoints not using ok_list() ---")
    v = scan_missing_ok_list(verbose)
    all_violations.extend(v)
    for item in v:
        print(item)
    if not v:
        print("  OK")

    print("\n--- Scan 4: Write operations without write_work_log ---")
    v = scan_missing_write_work_log(verbose)
    all_violations.extend(v)
    for item in v:
        print(item)
    if not v:
        print("  OK")

    print("\n--- Scan 5: Missing filter_by_data_scope (org model queries) ---")
    v = scan_missing_data_scope(verbose)
    all_violations.extend(v)
    for item in v:
        print(item)
    if not v:
        print("  OK")

    print("\n" + "=" * 60)
    total = len(all_violations)
    print(f"Total issues: {total}")
    print("=" * 60)

    if strict and total > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
