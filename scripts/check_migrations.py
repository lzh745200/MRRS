"""Alembic 迁移历史健康检查（架构评估 F1-lite）。

背景：历史上发生过迁移分叉（data_report_type_001 MultipleHeads，
commit 4c1ea8a0）导致打包实例启动失败。本脚本供 CI static-analysis
门禁调用，在合并前拦截分叉回归：

  1. 恰好一个 head（无 multiple heads 分叉）；
  2. 迁移链可完整遍历（walk_revisions 对环/缺失依赖天然报错）。

用法: python scripts/check_migrations.py
退出码: 0 = 健康；1 = 存在分叉或脚本不可读
"""

import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    alembic_ini = PROJECT_ROOT / "backend" / "alembic.ini"
    if not alembic_ini.exists():
        print(f"ERROR: 未找到 {alembic_ini}")
        return 1

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(alembic_ini.parent / "alembic"))
    try:
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        revision_count = len(list(script.walk_revisions()))
    except Exception as exc:
        print(f"ERROR: 迁移脚本目录无法解析（可能存在环/缺失依赖）: {exc}")
        return 1

    if len(heads) != 1:
        print(f"ERROR: 迁移存在 {len(heads)} 个 head（分叉）: {heads}")
        print("修复方法: alembic merge -m 'merge branches' <head1> <head2>，")
        print("或删除分叉的迁移链后重新生成。")
        return 1

    print(f"OK: 单 head {heads[0]}，共 {revision_count} 个迁移版本，无分叉")
    return 0


if __name__ == "__main__":
    sys.exit(main())
