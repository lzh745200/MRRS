"""批量更新工单状态：本轮已修 → done；已审计未修 → 追加审计结论行。"""
import re
from pathlib import Path

ROOT = Path(r"C:\military-Rural Revitalization-system\.scratch")

DONE = {
    "w2-data-integrity/001-sync-table-names.md": "facca… commit：单一常量源派生+空表不误报、异常显式上报 success=False+errors",
    "w2-data-integrity/006-atomic-counters.md": "6148cbf0：policy 计数与登录锁定改 COALESCE/CASE/RETURNING 原子 UPDATE",
    "w2-data-integrity/008-backup-snapshot-wal-streaming.md":
        "07b5b017：_create_snapshots 复用一致性快照合并 WAL（流式加密部分仍开放）",
}

AUDIT_NOTES = {
    "w2-data-integrity/002-org-delete-guard.md":
        "AUDIT-20260825: MISSING——delete_organization 仅查下级组织；Project.organization_id 仍 CASCADE(organization_service.py:333-363 / project.py:87-92)",
    "w2-data-integrity/003-approval-writeback-closure.md":
        "AUDIT-20260825: PARTIAL——apply_entity_change 失败仅 warning(:46-59)；resubmit 未走 _resolve_role_approver_id(:558-561)",
    "w2-data-integrity/004-fund-state-machine.md":
        "AUDIT-20260825: PARTIAL——PUT 直改 status 绕状态机(funds.py:531-587)；FundStatus 无 REJECTED(models/fund.py:49-57)；setattr 清空已修复",
    "w2-data-integrity/005-fk-ondelete-contradictions.md":
        "AUDIT-20260825: MISSING——PolicyFavorite/ImportHistory(+ApprovalRecord/Task) 四处 SET NULL×NOT NULL 矛盾；cascade 服务物理删除审计记录(user_cascade_delete_service.py:120-127)",
    "w2-data-integrity/007-unify-import-pipeline.md":
        "AUDIT-20260825: MISSING——裸 text() 导入绕过 sync_version 事件(data_sync_service.py:459-476)；无 SAVEPOINT",
    "w11-ui-consistency/042-register-permission-directives.md":
        "AUDIT-20260825: PARTIAL——指令+测试资产在，main.ts 注册与 v-permission/v-watermark 接线为 0",
    "w12-system-compliance/048-audit-detail-completion.md":
        "AUDIT-20260825: 部分完成——rural_tasks 六端点已接入(07b5b017)；work_logs/user_permissions/files 仍缺",
    "w12-system-compliance/049-audit-capacity-governance.md":
        "AUDIT-20260825: 并行会话已加 recycle_retention_job(04:30)；audit_logs/api_access_logs/login_attempts 保留期仍缺",
}

for rel, note in DONE.items():
    p = ROOT / rel
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    m = re.search(r"labels:\s*\[([^\]]*)\]", t)
    if m and "done" not in m.group(1):
        labels = "done, " + ", ".join(
            x.strip() for x in m.group(1).split(",") if x.strip() and x.strip() != "ready-for-agent"
        )
        t = t[:m.start()] + f"labels: [{labels}]" + t[m.end():]
    if "## Resolution" not in t and "## Resolution（" not in t:
        t += f"\n## Resolution（2026-08-25）\n\n{note}\n"
    p.write_text(t, encoding="utf-8", newline="")
    print("done:", rel)

for rel, note in AUDIT_NOTES.items():
    p = ROOT / rel
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    if note.split(":")[0] not in t:
        t += f"\n## 审计结论（2026-08-25）\n\n{note}\n"
        p.write_text(t, encoding="utf-8", newline="")
        print("audited:", rel)
