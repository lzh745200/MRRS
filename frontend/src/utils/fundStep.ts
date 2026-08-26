// T035：经费状态机步骤推导（纯函数，便于单测参数化覆盖 7 态）
export interface FundFlowNode {
  status: string
  label?: string
  current?: boolean
  reached?: boolean
}

// 返回 el-steps 的 active 值（已完成步骤数）：
// 优先取 current 节点索引+1；否则取已到达节点数。
export function deriveActiveStep(nodes: FundFlowNode[]): number {
  if (!nodes || !nodes.length) return 0
  const idx = nodes.findIndex((n) => n.current)
  return idx >= 0 ? idx + 1 : nodes.filter((n) => n.reached).length
}
