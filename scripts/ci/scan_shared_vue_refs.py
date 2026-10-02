"""扫描「被覆盖率门禁锁定的 .vue 是否被多个测试文件引用」。

背景（frontend/vitest.config.ts 注释 (A)）：
  v8 覆盖率分片在满量合并时按函数 id 对齐。同一 .vue 若被两个测试文件执行，
  两处产出的 v8 fnMap 长度不同（bare import 17 个函数 vs 全渲染 19 个函数），
  按 id 合并即错位 → 部分内联处理器计数归零 → functions 跌穿 100% 门禁。
  该故障仅在 Linux CI 复现（OS 间 v8 函数 id 顺序差异），Windows 本地恒绿。
  ⇒ 不变量：凡被门禁锁定的 .vue，全仓只允许**一个**测试文件执行它。

用法：python scripts/ci/scan_shared_vue_refs.py [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

# 与 vitest.config.ts 的 coverage.thresholds 保持一致（仅含 .vue 的两组）
LOCKED_GLOBS = {
    "src/views": "src/views/**/*.vue",
    "src/components": "src/components/**/*.vue",
    "src/layouts": "src/layouts/**/*.vue",
}

# 测试文件集合（与 vitest.config.ts 的 test.include 对齐）
TEST_PATTERNS = [
    "tests/unit/**/*.test.ts",
    "tests/*.test.ts",
    "tests/property/**/*.test.ts",
    "src/**/__tests__/**/*.spec.ts",
]

# 疑似「执行」该 .vue 的引用形式：
#   import X from '...Foo.vue'
#   import('...Foo.vue')
#   路由表里的 () => import('@/views/...')  亦会被上面那条覆盖
#   mount(Foo) 需要先 import，故不单独匹配
IMPORT_RE = re.compile(
    r"""(?:from|import)\s*\(?\s*['"](?P<spec>[^'"]+\.vue)['"]""",
    re.VERBOSE,
)


def _norm(spec: str, test_file: Path) -> str | None:
    """把 import 说明符解析成 frontend 相对路径（posix），解析不到返回 None。"""
    spec = spec.split("?")[0].strip()
    if spec.startswith("@/"):
        rel = "src/" + spec[2:]
    elif spec.startswith("."):
        base = test_file.parent
        try:
            rel = (base / spec).resolve().relative_to(FRONTEND).as_posix()
        except ValueError:
            return None
    else:
        return None  # 第三方或裸模块
    # 折叠 ../
    parts: list[str] = []
    for seg in rel.split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg in ("", "."):
            continue
        else:
            parts.append(seg)
    return "/".join(parts)


def collect_test_files() -> list[Path]:
    files: set[Path] = set()
    for pat in TEST_PATTERNS:
        files.update(FRONTEND.glob(pat))
    return sorted(f for f in files if f.is_file())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    test_files = collect_test_files()

    # vue 相对路径 -> 引用它的测试文件集合
    refs: dict[str, set[str]] = defaultdict(set)
    for tf in test_files:
        try:
            text = tf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if ".vue" not in text:
            continue
        rel_test = tf.relative_to(FRONTEND).as_posix()
        for m in IMPORT_RE.finditer(text):
            rel_vue = _norm(m.group("spec"), tf)
            if rel_vue is None:
                continue
            refs[rel_vue].add(rel_test)

    # 只保留被门禁锁定的 .vue
    locked = {
        v: sorted(t) for v, t in refs.items()
        if any(v.startswith(p + "/") for p in LOCKED_GLOBS)
    }
    shared = {v: t for v, t in locked.items() if len(t) > 1}

    result = {
        "test_files_scanned": len(test_files),
        "locked_vue_referenced": len(locked),
        "shared_violations": shared,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 78)
    print("被覆盖率门禁锁定的 .vue —— 多测试文件引用扫描")
    print("=" * 78)
    print(f"扫描测试文件            : {len(test_files)}")
    print(f"被引用的受锁定 .vue     : {len(locked)}")
    print(f"仅单文件引用（安全）    : {len(locked) - len(shared)}")
    print(f"多文件引用（违规候选）  : {len(shared)}")
    print("-" * 78)
    if shared:
        for v in sorted(shared, key=lambda x: (-len(shared[x]), x)):
            print(f"\n  ⚠ {v}   ({len(shared[v])} 个测试文件)")
            for t in shared[v]:
                print(f"      - {t}")
    else:
        print("\n  ✅ 无不变量违规")
    print("=" * 78)
    return 1 if shared else 0


if __name__ == "__main__":
    sys.exit(main())
