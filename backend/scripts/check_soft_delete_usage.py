"""软删除过滤静态扫描器（统计口径防线 · 第二道保险）。

扫描 backend/app/api 与 backend/app/services 中对软删模型
（SupportedVillage/Project/Fund/School）的 db.query() 调用，
若同一语句窗口内未出现 is_active 过滤则记为违规。

白名单（合法不过滤场景，自动豁免）：
- 按 id 取详情：filter(<M>.id == ...) / filter_by(id=...)
- 回收站管理：include_deleted、purge、restore、_require_village_in_recycle_bin
- 基础设施：query_guards.py 本身、cascade/purge 服务、retention 服务
  （操作对象就是软删数据）、batch_service、import/export 模板等

用法::

    python scripts/check_soft_delete_usage.py            # 对比基线，新增即失败
    python scripts/check_soft_delete_usage.py --baseline # 重新生成基线文件

基线：scripts/soft_delete_baseline.txt（每行一条 `相对路径:行号: 代码`）。
行号仅供人阅读定位；**比对键是 `相对路径 + 归一化代码`，忽略行号、按出现
次数计数**——因此无关编辑造成的行号漂移不会误报，而新增的未过滤查询（新键
或同键次数增加）依旧拦下。扫描中不再命中的基线条目会以 STALE 报告，表示该
豁免点已被修复，应跑 `--baseline` 收敛基线（棘轮只紧不松）。
历史遗留的豁免点收敛完毕后基线应趋于空文件。
"""

import re
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SCAN_DIRS = [BACKEND / "app" / "api", BACKEND / "app" / "services"]
BASELINE_FILE = Path(__file__).resolve().parent / "soft_delete_baseline.txt"

MODELS = ("SupportedVillage", "Project", "Fund", "School")
QUERY_RE = re.compile(r"\bdb(?:_)?\.query\(\s*(" + "|".join(MODELS) + r")\b")
SESSION_QUERY_RE = re.compile(r"\.(?:sess|session)\.query\(\s*(" + "|".join(MODELS) + r")\b")
ALL_QUERY_RE = re.compile(QUERY_RE.pattern + "|" + SESSION_QUERY_RE.pattern)

WINDOW_AHEAD = 6   # 同语句后续行数内寻找 is_active
WINDOW_BEHIND = 2  # 链式 .filter(...) 写在前几行的情况

ALLOWLIST_FILE_RE = re.compile(
    r"(query_guards|cascade_purge_service|retention_service|batch_service"
    r"|permission_package_service|report_templates|data_quality"
    r"|village_cascade_delete_service|machine_code)"
)
ALLOWLINE_RE = re.compile(
    r"include_deleted|purge|restore|is_active|active_filter"
    r"|filter_by\(\s*\w*\.?id\s*=|\.id\s*==|nosec:soft-delete"
)


def scan_file(path: Path) -> list:
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = str(path.relative_to(BACKEND))
    if ALLOWLIST_FILE_RE.search(rel):
        return []
    lines = text.splitlines()
    hits = []
    for i, line in enumerate(lines):
        m = ALL_QUERY_RE.search(line)
        if not m:
            continue
        window = "\n".join(lines[max(0, i - WINDOW_BEHIND): i + WINDOW_AHEAD + 1])
        if "is_active" in window or "active_filter" in window:
            continue
        if ALLOWLINE_RE.search(window):
            continue
        hits.append(f"{rel}:{i + 1}: {line.strip()[:100]}")
    return hits


def _entry_key(entry: str) -> str:
    """比对键 = 相对路径 + 归一化代码片段（**忽略行号**）。

    行号会随无关编辑漂移：曾用整串精确匹配，一次普通重构就让 6 个代码
    毫无变化的既有豁免点被误报为「新增违规」，门禁恒红，反而淹没了真实
    信号。改按 路径+代码 计数后，漂移不再误报，而真正新增的未过滤查询
    （新键，或同一键出现次数增加）依旧会被拦下——棘轮能力不减。
    """
    parts = entry.split(":", 2)
    code = parts[2].strip() if len(parts) == 3 else ""
    return f"{parts[0]}::{code}"


def main() -> int:
    baseline_mode = "--baseline" in sys.argv
    violations = []
    for d in SCAN_DIRS:
        for p in sorted(d.rglob("*.py")):
            violations.extend(scan_file(p))

    violations = [v.replace("\\", "/") for v in violations]

    if baseline_mode:
        BASELINE_FILE.write_text("\n".join(sorted(violations)) + "\n", encoding="utf-8")
        print(f"[baseline] {len(violations)} entries -> {BASELINE_FILE.name}")
        return 0

    known = []
    if BASELINE_FILE.exists():
        known = [
            l.strip() for l in BASELINE_FILE.read_text(encoding="utf-8").splitlines() if l.strip()
        ]

    known_counts = Counter(_entry_key(k) for k in known)
    seen = Counter()
    new = []
    for v in violations:
        k = _entry_key(v)
        seen[k] += 1
        if seen[k] > known_counts.get(k, 0):
            new.append(v)

    # 基线中已不再命中的条目 = 豁免点已被修复，属进展（不失败），
    # 但必须显式暴露，否则会永久留在基线里让棘轮松掉。
    stale = [
        e for e in known
        if known_counts[_entry_key(e)] > seen.get(_entry_key(e), 0)
    ]

    print(f"[scan] total={len(violations)} baseline={len(known)} NEW={len(new)}")
    for v in new:
        print("NEW VIOLATION:", v)
    if stale:
        print(f"[stale] {len(stale)} 条基线豁免点已不再命中（已修复），"
              f"建议 --baseline 收敛基线：")
        for e in stale:
            print("STALE BASELINE:", e)
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
