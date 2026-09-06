# -*- coding: utf-8 -*-
"""全链路探针总运行器：按轮次顺序执行全部 9 个探针，汇总结果。

每个探针独立子进程运行（独立临时目录 + 独立数据库，互不污染）；
任一探针失败不影响后续探针执行，最终以失败数作为退出码。

用法：
    python backend/tests/probe/run_all.py            # 全部
    python backend/tests/probe/run_all.py r1 r8      # 指定轮次
"""
import subprocess
import sys
import time
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent

PROBES = [
    ("r1", "probe_r1_passcode_register.py", "通行码注册/refresh 轮换/异步导出/权限包/数据同步"),
    ("r2", "probe_r2_approval_reports_map.py", "审批流/报表模板/地图离线瓦片/消息待办/监控健康"),
    ("r3", "probe_r3_funds_state_yearly_rbac.py", "经费状态机/村年度板块/RBAC/系统配置调度/数据包链"),
    ("r4", "probe_r4_policy_school_worklog_2fa.py", "政策/学校/项目/工作日志/通知/2FA/资料/订阅/模板上传"),
    ("r5", "probe_r5_scholarship_incremental_marker.py", "乡村工作台/奖学金导入/增量三端点/坐标/更新日志/消息联动"),
    ("r6", "probe_r6_contract_voucher_conflict.py", "合同链/转账凭证/同步冲突解决/subordinate 级联"),
    ("r7", "probe_r7_help_assessment_effectiveness.py", "帮助文档/考核评估/成效评估"),
    ("r8", "probe_r8_concurrency.py", "并发场景（同记录写/审批竞态/并发备份/注册竞态/并发导入）"),
    ("r9", "probe_r9_quality_analytics_chunked.py", "数据质量/分析/离线地图/机器码管理/分片上传/通知偏好"),
]


def main() -> int:
    wanted = set(sys.argv[1:])
    results = []
    for key, filename, desc in PROBES:
        if wanted and key not in wanted:
            continue
        print(f"\n{'=' * 64}\n>>> {key} {desc}\n{'=' * 64}", flush=True)
        t0 = time.time()
        proc = subprocess.run(
            [sys.executable, str(PROBE_DIR / filename)],
            cwd=str(PROBE_DIR),
        )
        results.append((key, proc.returncode, time.time() - t0))

    print(f"\n{'=' * 64}\n===== 探针汇总 =====")
    failed = 0
    for key, code, secs in results:
        mark = "PASS" if code == 0 else f"FAIL(exit={code})"
        if code != 0:
            failed += 1
        print(f"  [{mark:>12}] {key}  ({secs:.0f}s)")
    total = len(results)
    print(f"===== {total - failed}/{total} 探针通过 =====")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
