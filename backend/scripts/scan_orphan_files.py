#!/usr/bin/env python3
"""孤立附件扫描/清理脚本（P2-2）。

用途
----
遍历 ``settings.UPLOAD_DIR`` 下的物理文件，与数据库中的「引用集合」比对，
列出**没有任何 DB 引用**的孤立文件（路径、大小、mtime）与汇总统计。

引用集合来源（取并集，宁多勿少）
--------------------------------
1. ``file_blobs.path``（内容去重表，覆盖经 ``save_upload_file(db=...)`` 登记的文件）；
2. 各业务表的附件路径列（``fund_attachments.file_path``、``project_files.filepath``、
   ``school_attachments.file_path``、``village_attachments.file_path``、
   ``policies.file_path``）——覆盖历史上直接把路径写进业务表的情形；
3. ``policies.attachment_urls``（JSON 数组字符串，形如 ``/uploads/...``）。

安全原则
--------
**宁可漏报，不可误删**：
- 默认**只读**，不删除任何文件；
- 仅当显式传入 ``--delete`` 才执行删除，并逐条打印删除清单；
- 若任一引用来源查询失败（表缺失 / DB 异常），则**拒绝删除**（返回码 2），
  避免「引用集合不完整 → 误删在用文件」。

用法::

    python scripts/scan_orphan_files.py                 # 只读扫描
    python scripts/scan_orphan_files.py --delete        # 扫描并删除孤儿文件
    python scripts/scan_orphan_files.py --upload-dir /data/uploads
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

# 添加项目根目录到 Python 路径（脚本直接运行时）
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config import settings  # noqa: E402

# ── 业务表附件路径列：(模块, 类名, 列名) ──
# 采用「字符串懒加载」避免脚本导入期加载全部模型。
_REFERENCE_COLUMNS: List[Tuple[str, str, str]] = [
    ("app.models.fund", "FundAttachment", "file_path"),
    ("app.models.project", "ProjectFile", "filepath"),
    ("app.models.school", "SchoolAttachment", "file_path"),
    ("app.models.supported_village", "VillageAttachment", "file_path"),
    ("app.models.policy", "Policy", "file_path"),
]


def _norm(path: str) -> str:
    """归一化为绝对路径（用于引用比对）。"""
    return os.path.normpath(os.path.abspath(path))


def resolve_reference(value: Optional[str], upload_dir: str) -> Optional[str]:
    """把一条 DB 中的引用值解析为物理文件的绝对路径。

    支持三种形态：
    - ``/uploads/xxx/yyy.pdf``（静态 URL）→ 映射到 ``upload_dir`` 下；
    - 绝对/相对本地路径 → 归一化为绝对路径；
    - 空值 → ``None``。
    """
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    if v.startswith("/uploads/"):
        rel = v[len("/uploads/"):].replace("/", os.sep)
        return _norm(os.path.join(upload_dir, rel))
    if v.startswith("uploads/"):
        rel = v[len("uploads/"):].replace("/", os.sep)
        return _norm(os.path.join(upload_dir, rel))
    return _norm(v)


def _iter_column_values(db, column) -> List[str]:
    """取出某列的全部非空字符串值。

    兼容 SQLAlchemy ``Row``（非 tuple 子类）、tuple/list 与标量三种返回形态。
    """
    out: List[str] = []
    for row in db.query(column).all():
        value = row[0] if hasattr(row, "__getitem__") and not isinstance(row, str) else row
        if isinstance(value, str) and value:
            out.append(value)
    return out


def _collect_from_sources(
    db,
    upload_dir: str,
    referenced: Set[str],
    errors: List[str],
) -> None:
    """收集全部引用来源（FileBlob + 业务表列 + policy 附件 URL）。"""
    # 1. FileBlob（内容去重表）
    _try_collect(
        errors, "file_blobs.path", _iter_blob_paths, db, upload_dir, referenced
    )
    # 2. 业务表附件路径列
    for spec in _REFERENCE_COLUMNS:
        module_path, class_name, column_name = spec
        _try_collect(
            errors,
            f"{class_name}.{column_name}",
            _iter_model_column_values,
            db,
            upload_dir,
            referenced,
            spec,
        )
    # 3. policies.attachment_urls（JSON 数组字符串）
    _try_collect(
        errors, "Policy.attachment_urls", _iter_policy_attachment_urls,
        db, upload_dir, referenced,
    )


def _try_collect(errors, label, producer, db, upload_dir, referenced, *extra) -> None:
    """执行一个引用来源收集，失败则记录到 ``errors``（阻止后续删除）。"""
    try:
        for value in producer(db, *extra):
            resolved = resolve_reference(value, upload_dir)
            if resolved:
                referenced.add(resolved)
    except Exception as e:  # noqa: BLE001 - 引用来源失败必须记录并阻止删除
        errors.append(f"{label}: {e}")


def _iter_blob_paths(db):
    """产出 FileBlob.path 的所有取值。"""
    from app.models.file_blob import FileBlob

    yield from _iter_column_values(db, FileBlob.path)


def _iter_model_column_values(db, spec):
    """产出某业务表附件列的所有取值。"""
    import importlib

    module_path, class_name, column_name = spec
    model = getattr(importlib.import_module(module_path), class_name)
    yield from _iter_column_values(db, getattr(model, column_name))


def _iter_policy_attachment_urls(db):
    """产出 policies.attachment_urls 中 JSON 数组里的全部 URL。"""
    from app.models.policy import Policy

    for raw in _iter_column_values(db, Policy.attachment_urls):
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, list):
            for url in parsed:
                if url:
                    yield url


def collect_db_references(db, upload_dir: str) -> Tuple[Set[str], List[str]]:
    """收集「被 DB 引用」的物理文件绝对路径集合。

    Args:
        db: SQLAlchemy 会话
        upload_dir: 上传根目录

    Returns:
        ``(referenced, errors)``：引用路径集合 + 引用来源解析错误清单。
        只要 ``errors`` 非空，调用方**不得**执行删除（宁可漏报，不可误删）。
    """
    referenced: Set[str] = set()
    errors: List[str] = []
    _collect_from_sources(db, upload_dir, referenced, errors)
    return referenced, errors


def scan_orphans(upload_dir: str, referenced: Set[str]) -> List[Dict[str, object]]:
    """扫描 ``upload_dir`` 下未被引用的物理文件。

    Returns:
        孤儿文件清单 ``[{"path", "size", "mtime"}, ...]``（按大小降序）。
    """
    orphans: List[Dict[str, object]] = []
    if not upload_dir or not os.path.isdir(upload_dir):
        return orphans
    for root, _dirs, files in os.walk(upload_dir):
        for name in files:
            full = os.path.join(root, name)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            if _norm(full) in referenced:
                continue
            orphans.append(
                {
                    "path": full,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime),
                }
            )
    orphans.sort(key=lambda item: int(item["size"]), reverse=True)  # type: ignore[arg-type]
    return orphans


def delete_orphans(orphans: List[Dict[str, object]]) -> Tuple[List[str], List[str]]:
    """删除孤儿文件。

    Returns:
        ``(deleted, failed)``：成功删除路径清单 + 删除失败清单。
    """
    deleted: List[str] = []
    failed: List[str] = []
    for item in orphans:
        path = str(item["path"])
        try:
            os.remove(path)
            deleted.append(path)
        except OSError as e:  # pragma: no cover - 删除失败仅在真实 FS 权限异常时发生
            failed.append(f"{path}: {e}")
    return deleted, failed


def format_report(
    orphans: List[Dict[str, object]],
    upload_dir: str,
    referenced_count: int,
    errors: List[str],
    limit: int = 50,
) -> str:
    """生成可读扫描报告（文本）。"""
    total_bytes = sum(int(item["size"]) for item in orphans)
    lines = [
        "=" * 70,
        "孤立附件扫描报告",
        "=" * 70,
        f"上传根目录      : {upload_dir}",
        f"DB 引用文件数   : {referenced_count}",
        f"孤立文件数      : {len(orphans)}",
        f"孤立文件总大小  : {total_bytes} 字节 ({total_bytes / 1048576:.2f} MB)",
    ]
    if errors:
        lines.append(f"引用解析错误    : {len(errors)} 项（将拒绝删除）")
        for err in errors:
            lines.append(f"  - {err}")
    lines.append("-" * 70)
    for item in orphans[:limit]:
        lines.append(
            f"  {item['mtime']}  {int(item['size']):>12} B  {item['path']}"  # type: ignore[arg-type]
        )
    if len(orphans) > limit:
        lines.append(f"  ...（其余 {len(orphans) - limit} 条已省略，可用 --limit 调整）")
    lines.append("=" * 70)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """脚本入口。默认只读；``--delete`` 才删除。"""
    parser = argparse.ArgumentParser(description="孤立附件扫描/清理（默认只读）")
    parser.add_argument("--upload-dir", default=None, help="上传根目录（默认 settings.UPLOAD_DIR）")
    parser.add_argument("--delete", action="store_true", help="删除孤儿文件（默认只读）")
    parser.add_argument("--limit", type=int, default=50, help="报告中最多列出的条目数")
    args = parser.parse_args(argv)

    upload_dir = _norm(args.upload_dir or settings.UPLOAD_DIR)

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        referenced, errors = collect_db_references(db, upload_dir)
    finally:
        db.close()

    orphans = scan_orphans(upload_dir, referenced)
    print(format_report(orphans, upload_dir, len(referenced), errors, limit=args.limit))

    if not args.delete:
        print("[只读模式] 未删除任何文件。如需删除请显式追加 --delete")
        return 0

    if errors:
        print("[中止] 存在引用解析错误，拒绝删除（宁可漏报，不可误删）")
        return 2

    deleted, failed = delete_orphans(orphans)
    print(f"[删除完成] 成功 {len(deleted)} 个，失败 {len(failed)} 个")
    for path in deleted:
        print(f"  已删除: {path}")
    for msg in failed:
        print(f"  删除失败: {msg}")
    return 0 if not failed else 1


if __name__ == "__main__":  # pragma: no cover - 脚本入口守卫
    sys.exit(main())
