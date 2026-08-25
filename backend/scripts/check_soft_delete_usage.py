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

基线：scripts/soft_delete_baseline.txt（每行一条 `相对路径:行号`）。
历史遗留的豁免点收敛完毕后基线应趋于空文件。
"""

import re
import sys
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


def main() -> int:
    baseline_mode = "--baseline" in sys.argv
    violations = []
    for d in SCAN_DIRS:
        for p in sorted(d.rglob("*.py")):
            violations.extend(scan_file(p))

    violations = [v.replace("\\", "/") for v in violations]

    if baseline_mode:
        BASELINE_FILE.write_text("\n".join(sorted(v.replace("\\", "/") for v in violations)) + "\n", encoding="utf-8")
        print(f"[baseline] {len(violations)} entries -> {BASELINE_FILE.name}")
        return 0

    known = set()
    if BASELINE_FILE.exists():
        known = {
            l.strip() for l in BASELINE_FILE.read_text(encoding="utf-8").splitlines() if l.strip()
        }
    new = [v for v in violations if v.split(":")[0] + ":" + v.split(":")[1] not in
           {k.rsplit(":", 1)[0] for k in known} or v not in known]
    # 以“整条匹配”为准：不在基线中的即视为新增
    new = [v for v in violations if v not in known]

    print(f"[scan] total={len(violations)} baseline={len(known)} NEW={len(new)}")
    for v in new:
        print("NEW VIOLATION:", v)
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
