// T033：审批详情时间线 —— 聚合「审批历史 + 状态日志」为统一轨迹节点。
export interface TimelineNode {
  operator: string
  action: string
  time: string
  type: string
}

function norm(e: any, type: string): TimelineNode {
  return {
    operator: e?.operator || e?.actor || e?.user || e?.handler || e?.approver || '-',
    action: e?.action || e?.description || e?.title || e?.remark || '',
    time: e?.time || e?.created_at || e?.timestamp || e?.operated_at || '',
    type: e?.type || type,
  }
}

export function buildApprovalTimeline(history: any[], statusLogs: any[]): TimelineNode[] {
  const a = (history || []).map((e) => norm(e, 'history'))
  const b = (statusLogs || []).map((e) => norm(e, 'status'))
  // 时间倒序（最新在上）
  return [...a, ...b].sort((x, y) => String(y.time).localeCompare(String(x.time)))
}
