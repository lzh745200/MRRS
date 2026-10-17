# -*- coding: utf-8 -*-
r"""升级排练（upgrade rehearsal）—— 拿**上一个发布版本**的真实库结构跑一次真实升级。

为什么需要它（P0-8，2026-10-17）：发布前的自动化验证里有安装包冒烟（能起、能看健康页），
但**没有**「老版本用户的库升到新版本后数据还在吗」。历史上这个风险点靠人工在测试机
装旧版→装新版→点几下确认；一旦漏做，用户升级后发现某张表被清空/迁移链断裂，
现场没有回退路径（打包环境只有当前版本）。

本脚本的排练语义（**不用安装包，直接排练真正会出事的那一段**）：

1. `git worktree` 取出 `--old-ref`（默认＝最近发布标签）的代码，用**旧代码自己的
   alembic** 在临时库上建出"老用户库"（旧版本 head 的真实 schema）；
2. 反射旧库全部表，**每张表插一行**（NOT NULL 列按类型填占位值；插不进的表登记跳过）——
   这样升级后任何一张表的行被清掉都会被第 5 步抓到；
3. 用**当前代码**的 alembic 对同一个库执行 `upgrade head`（这就是用户升级时发生的事）；
4. 校验：迁移链可从旧 head 解析、`PRAGMA integrity_check == ok`、旧表集合无丢失、
   已播种表行数不变；
5. 输出报告；任何一项不达标 → 退出码 1（CI 直接红）。

用法：
  python backend/scripts/upgrade_rehearsal.py                 # 默认取最近标签
  python backend/scripts/upgrade_rehearsal.py --old-ref v1.12.17 --keep
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

# ── Windows CI/本地控制台编码兜底：脚本输出中文，cp936/cp1252 下会 UnicodeEncodeError ──
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


def run(cmd, cwd, env=None, timeout=900):
    """执行子进程并返回 (returncode, 合并输出)。"""
    merged = dict(os.environ)
    if env:
        merged.update(env)
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), env=merged, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after %ss: %s" % (timeout, " ".join(str(c) for c in cmd))
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def resolve_old_ref(explicit):
    """默认取最近发布标签（v* 按版本号排序）。"""
    if explicit:
        return explicit
    code, out = run(["git", "tag", "--sort=-v:refname"], REPO_ROOT)
    if code != 0:
        raise RuntimeError("无法列出 git tag（需要完整克隆）：%s" % out.strip()[-200:])
    for line in out.splitlines():
        tag = line.strip()
        if tag.startswith("v"):
            return tag
    raise RuntimeError("仓库里没有形如 v* 的发布标签，无法确定升级基线")


def dummy_value(column):
    """给 NOT NULL 且无默认值的列造一个占位值（按 SQLAlchemy 类型）。"""
    from sqlalchemy import Boolean, Date, DateTime, Float, Integer, JSON, Numeric, String, Text

    col_type = column.type
    if isinstance(col_type, (Integer,)):
        return 1
    if isinstance(col_type, (Float, Numeric)):
        return 1.0
    if isinstance(col_type, Boolean):
        return True
    if isinstance(col_type, DateTime):
        return datetime(2026, 1, 1, tzinfo=timezone.utc)
    if isinstance(col_type, Date):
        return date(2026, 1, 1)
    if isinstance(col_type, JSON):
        return {}
    if isinstance(col_type, (String, Text)):
        return "rehearsal"
    raise TypeError("不支持的列类型: %s" % type(col_type).__name__)


def _needs_value(table, column) -> bool:
    """该列是否必须由我们显式填值（NOT NULL 且不会自己产生值）。

    单一 INTEGER 主键是唯一的例外：SQLite 的 ``INTEGER PRIMARY KEY`` 会自增，
    而**字符串/UUID 主键**（file_blobs.sha256、rbac_*.id 这类）不会 —— 早期版本
    把"主键列"一律跳过，导致 9 张表插不进去（2026-10-17 实测）。
    """
    from sqlalchemy import Integer

    if column.default is not None or column.server_default is not None:
        return False
    if column.nullable:
        return False
    if column.primary_key and len(table.primary_key.columns) == 1 and isinstance(column.type, Integer):
        return False
    return True


def seed_all_tables(engine):
    """反射并给每张表插一行；返回 (已播种表集, 跳过表 {表名: 原因})。"""
    from sqlalchemy import MetaData, func, select

    metadata = MetaData()
    metadata.reflect(bind=engine)
    seeded, skipped = [], {}
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name == "alembic_version":
                continue
            values = {}
            try:
                for column in table.columns:
                    if _needs_value(table, column):
                        values[column.name] = dummy_value(column)
                conn.execute(table.insert().values(**values))
                count = conn.execute(select(func.count()).select_from(table)).scalar() or 0
                if count < 1:
                    skipped[table.name] = "插入后行数为 0"
                    continue
                seeded.append(table.name)
            except Exception as exc:  # noqa: BLE001 - 任何一张表插不进去都不该中断排练
                # 带一行原因（CHECK/Not-NULL 约束名），否则"为什么跳过"只能靠猜
                skipped[table.name] = "%s: %s" % (type(exc).__name__, str(exc).splitlines()[0][:160])
    return set(seeded), skipped


def table_state(engine):
    """当前库的表集合 + 各表行数 + 完整性检查。"""
    from sqlalchemy import MetaData, func, select, text

    metadata = MetaData()
    metadata.reflect(bind=engine)
    counts = {}
    table_names = set()
    with engine.connect() as conn:
        for table in metadata.sorted_tables:
            table_names.add(table.name)
            try:
                counts[table.name] = conn.execute(select(func.count()).select_from(table)).scalar() or 0
            except Exception:  # noqa: BLE001
                counts[table.name] = -1
        integrity = str(conn.execute(text("PRAGMA integrity_check")).scalar())
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    return {"tables": table_names, "counts": counts, "integrity": integrity, "version": version}


def main() -> int:
    parser = argparse.ArgumentParser(description="升级排练：旧版本库 → 当前代码 head")
    parser.add_argument("--old-ref", default=None, help="升级基线（默认：最近 v* 标签）")
    parser.add_argument("--workdir", default=None, help="临时工作目录（默认自动创建）")
    parser.add_argument("--keep", action="store_true", help="保留临时目录与 worktree（排障用）")
    args = parser.parse_args()

    from sqlalchemy import create_engine

    started = time.time()
    warnings: list = []
    failures: list = []
    report: dict = {"old_ref": None, "steps": []}

    try:
        old_ref = resolve_old_ref(args.old_ref)
    except RuntimeError as exc:
        print("ERROR: %s" % exc)
        return 2
    report["old_ref"] = old_ref
    print("=== 升级排练：%s -> %s ===" % (old_ref, "当前工作树"))

    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="upgrade-rehearsal-"))
    worktree = workdir / "old"
    db_file = workdir / "rehearsal.db"
    db_url = "sqlite:///" + db_file.as_posix()
    worktree_added = False

    def step(name, ok, detail=""):
        report["steps"].append({"name": name, "ok": bool(ok), "detail": detail})
        print("[%s] %s%s" % ("OK" if ok else "FAIL", name, (" - " + detail) if detail else ""))

    try:
        code, out = run(["git", "worktree", "add", "--detach", str(worktree), old_ref], REPO_ROOT)
        worktree_added = code == 0
        step("取出旧版本代码", code == 0, old_ref if code == 0 else out.strip()[-300:])
        if code != 0:
            failures.append("worktree")
            return report_and_exit(report, failures, warnings, started)

        backend_env = {"DATABASE_URL": db_url, "SECRET_KEY": "rehearsal-secret-key-32-chars-min!!"}
        code, out = run([sys.executable, "-m", "alembic", "upgrade", "head"], worktree / "backend", backend_env)
        step(
            "旧版本建库（旧 alembic upgrade head）",
            code == 0,
            out.strip().splitlines()[-1] if code == 0 else out.strip()[-300:],
        )
        if code != 0:
            failures.append("old_upgrade")
            return report_and_exit(report, failures, warnings, started)

        engine = create_engine(db_url)
        try:
            old_state = table_state(engine)
            seeded, skipped = seed_all_tables(engine)
            for name, reason in sorted(skipped.items()):
                warnings.append("跳过播种 %s（%s）" % (name, reason))
            # 行数基线必须在**播种之后**取：升到 head 后逐表比对"数据有没有丢"。
            seeded_state = table_state(engine)
            step("旧库播种（每表一行）", len(seeded) > 0, "已播种 %d 表 / 跳过 %d 表" % (len(seeded), len(skipped)))
            if not seeded:
                failures.append("seed")
                return report_and_exit(report, failures, warnings, started)
        finally:
            engine.dispose()

        code, out = run([sys.executable, "-m", "alembic", "upgrade", "head"], BACKEND_DIR, backend_env)
        step("当前代码升级同一库（upgrade head）", code == 0, out.strip().splitlines()[-1] if code == 0 else out.strip()[-300:])
        if code != 0:
            failures.append("upgrade")
            return report_and_exit(report, failures, warnings, started)

        engine = create_engine(db_url)
        try:
            new_state = table_state(engine)
        finally:
            engine.dispose()

        step("完整性检查", new_state["integrity"] == "ok", new_state["integrity"])

        lost_tables = sorted(old_state["tables"] - new_state["tables"])
        step("无表丢失", not lost_tables, ",".join(lost_tables) if lost_tables else "%d 表完好" % len(old_state["tables"]))
        if lost_tables or new_state["integrity"] != "ok":
            failures.append("schema")

        lost_rows = sorted(
            name for name in seeded
            if new_state["counts"].get(name, -1) != seeded_state["counts"].get(name, -2)
        )
        step("已播种表行数不变", not lost_rows, ",".join(lost_rows) if lost_rows else "%d 表数据完好" % len(seeded))
        if lost_rows:
            failures.append("data")

        code, head_out = run([sys.executable, "-m", "alembic", "heads"], BACKEND_DIR, backend_env)
        code_heads = {line.split()[0] for line in head_out.splitlines() if line.strip() and not line.startswith("INFO")}
        at_code_head = code == 0 and new_state["version"] in code_heads
        step("升级后落在当前代码的 head", at_code_head,
             "旧=%s 新=%s 代码 head=%s" % (old_state["version"], new_state["version"], ",".join(sorted(code_heads)) or "?"))
        if not at_code_head:
            failures.append("head")
        report["old_version"] = old_state["version"]
        report["new_version"] = new_state["version"]
        report["seeded_tables"] = len(seeded)
        report["skipped_tables"] = sorted(skipped)
    finally:
        if worktree_added and not args.keep:
            run(["git", "worktree", "remove", "--force", str(worktree)], REPO_ROOT)
            run(["git", "worktree", "prune"], REPO_ROOT)
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            print("临时目录保留在: %s（--keep）" % workdir)

    return report_and_exit(report, failures, warnings, started)


def report_and_exit(report, failures, warnings, started) -> int:
    report["failures"] = failures
    report["warnings"] = warnings
    report["duration_sec"] = round(time.time() - started, 1)
    print("\n=== 排练报告 ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        print("\nERROR: 升级排练失败（%s）—— 这类缺陷会直接打在真实升级的新版本安装包上" % ", ".join(failures))
        for item in warnings:
            print("  警告: %s" % item)
        return 1
    print("\nOK: 旧版本库可被当前代码完整接管（表/数据/完整性均通过）")
    for item in warnings:
        print("  警告: %s" % item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
