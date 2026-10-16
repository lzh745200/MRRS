"""版本号同步 —— **薄封装**，实际实现收口到 scripts/sync-version.js。

M53（2026-10-14）：本脚本与 scripts/sync-version.js 曾是**两套工具、两套目标集**
（.js 供 CI 门禁 / Makefile / preflight；.py 供出包流水线按 tag 同步），覆盖面不同
导致实测漂移：根 package-lock.json 停在 1.10.0、frontend/.env.example 停在 1.12.5，
长期无人发现。现在：

* 目标集只在 scripts/sync-version.js 维护（含上述两项）；
* 本文件只做参数翻译并转发，**不再自带任何版本改写逻辑**；
* 出包工作流（build-windows.yml / build-arm64.yml）直接调用 .js，不经过本文件。

用法（保持历史签名不变）::

    python scripts/sync_version.py            # 从 version.txt 读版本并写入所有目标
    python scripts/sync_version.py 1.12.17    # 显式指定版本（v 前缀可有可无）

退出码与 node 工具一致：0 = 一致/已同步；1 = 不一致或源版本非法。
"""

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NODE_TOOL = PROJECT_ROOT / "scripts" / "sync-version.js"


def main() -> int:
    if not NODE_TOOL.exists():
        print(f"ERROR: 找不到单一版本同步工具: {NODE_TOOL}")
        return 1

    node = shutil.which("node")
    if node is None:
        print("ERROR: 未找到 node —— 版本同步已收口到 scripts/sync-version.js（M53）")
        return 1

    args = ["--write"]
    if len(sys.argv) > 1:
        args.append(sys.argv[1].lstrip("v"))
    else:
        version_file = PROJECT_ROOT / "version.txt"
        if not version_file.exists():
            print("ERROR: 无 version.txt 且未提供参数")
            return 1
        args.append(version_file.read_text(encoding="utf-8").strip().lstrip("v"))

    # 输出全 ASCII：Windows CI 的管道默认编码是 cp1252/cp936，中文 print 会
    # UnicodeEncodeError（v1.12.3 出包事故同源），这里不再重复踩。
    print("[sync_version.py] forwarding to node scripts/sync-version.js " + " ".join(args))
    return subprocess.run([node, str(NODE_TOOL), *args], cwd=str(PROJECT_ROOT)).returncode


if __name__ == "__main__":
    sys.exit(main())
