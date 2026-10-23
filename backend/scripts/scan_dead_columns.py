#!/usr/bin/env python
"""死字段扫描（W27 P1）—— 找出"模型里声明、全仓零引用"的列。

## 为什么先扫描而不是直接删

W26 审计列了「12 个死字段」，但本轮已多次遇到**审计字段名与实际不符**的情况
（例如把 `household.annual_income`（户年收入，单位元）与已废弃的 `annual_income`
表混为一谈）。凭列表盲删迁移 = 高风险。故本工具先产出**可复核的确认清单**：

* 只统计列名在**模型定义之外**的出现次数（app/ 下的 .py，排除模型文件本身）；
* 区分"完全零引用"与"仅出现在 schema / 注释 / 另一模型"；
* 输出 CSV 风格清单，供人工逐条确认后再写迁移。

## 判定口径（保守，宁漏不误删）

一个列被判定为**疑似死字段**需同时满足：
1. 该列名在 `app/`（模型定义文件之外）**零次**出现；
2. 该列名在 `frontend/src` 下**零次**出现；
3. 不是主键/外键/审计列/软删列（这些即使零引用也必须保留）。

用法：
    python scripts/scan_dead_columns.py            # 摘要
    python scripts/scan_dead_columns.py --list     # 逐条清单
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_ROOT / "app"
MODELS_DIR = APP_DIR / "models"
REPO_ROOT = BACKEND_ROOT.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

# 无论是否被引用都必须保留的列（基础设施列）
ALWAYS_KEEP = {
    "id", "created_at", "updated_at", "created_by", "updated_by",
    "is_active", "deleted_at", "deleted_by", "sync_version",
    "organization_id", "supported_village_id", "village_id",
}


def _collect_columns() -> dict[str, list[str]]:
    """{列名: [模型.列 声明位置...]}"""
    found: dict[str, list[str]] = {}
    for path in sorted(MODELS_DIR.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            for stmt in cls.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                if not isinstance(stmt.value, ast.Call):
                    continue
                fn = stmt.value.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name not in ("Column", "mapped_column"):
                    continue
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        found.setdefault(target.id, []).append(
                            f"{path.relative_to(BACKEND_ROOT).as_posix()}:{cls.name}"
                        )
    return found


def _corpus(exclude: Path) -> str:
    """拼接 app/ 下（排除模型目录）所有 py 源码。"""
    chunks = []
    for path in APP_DIR.rglob("*.py"):
        if exclude in path.parents:
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError):
            continue
    return "\n".join(chunks)


def _frontend_corpus() -> str:
    if not FRONTEND_SRC.exists():
        return ""
    chunks = []
    for pattern in ("**/*.ts", "**/*.vue", "**/*.js"):
        for path in FRONTEND_SRC.glob(pattern):
            try:
                chunks.append(path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(chunks)


def main(argv: list[str]) -> int:
    list_mode = "--list" in argv
    columns = _collect_columns()
    backend_src = _corpus(MODELS_DIR)
    frontend_src = _frontend_corpus()

    suspected: list[tuple[str, str]] = []
    serialized: list[tuple[str, str]] = []
    for name, where in sorted(columns.items()):
        if name in ALWAYS_KEEP:
            continue
        if len(name) < 4:            # 过短的名字容易误判（如 a/b/x）
            continue
        pattern = re.compile(rf"\b{re.escape(name)}\b")
        if pattern.search(backend_src) or pattern.search(frontend_src):
            continue
        # 误报过滤：字段可能只在自己的模型文件里被 `to_dict()` 序列化后经 API 暴露
        # （此时 app/ 别处确实"零引用"，但它是实打实的接口字段，不能删）
        declared_in = {w.split(":")[0] for w in where}
        if any(
            (BACKEND_ROOT / p).exists()
            and len(pattern.findall((BACKEND_ROOT / p).read_text(encoding="utf-8-sig"))) > 1
            for p in declared_in
        ):
            serialized.append((name, ", ".join(where)))
            continue
        suspected.append((name, ", ".join(where)))

    print(f"[scan_dead_columns] 模型列总数: {len(columns)}")
    print(f"[scan_dead_columns] 疑似死字段: {len(suspected)}"
          f"（app/ 非模型代码 + frontend/src 皆零引用）")
    print(f"[scan_dead_columns] 已排除「仅被 to_dict 序列化」的字段: {len(serialized)}"
          f"（它们是 API 字段，不能删）")
    if suspected:
        print()
        print("需逐条人工确认后再写迁移（勿凭本清单直接删）：")
        for name, where in (suspected if list_mode else suspected[:20]):
            print(f"  - {name:<32} 声明于 {where}")
        if not list_mode and len(suspected) > 20:
            print(f"  ... 共 {len(suspected)} 条，用 --list 查看全部")
    if serialized and list_mode:
        print()
        print("以下字段仅被自身 to_dict 序列化（保留）：")
        for name, where in serialized:
            print(f"  - {name:<32} {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
