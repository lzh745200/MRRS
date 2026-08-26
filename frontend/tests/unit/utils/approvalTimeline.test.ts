import { describe, expect, it } from 'vitest'
import { buildApprovalTimeline, type TimelineNode } from '@/utils/approvalTimeline'

describe('buildApprovalTimeline (T033)', () => {
  const history = [
    { operator: '张三', action: '提交申请', time: '2024-01-01 09:00', type: 'submit' },
    { operator: '李四', action: '初审通过', time: '2024-01-02 10:00' },
  ]
  const statusLogs = [
    { actor: '系统', action: '状态变更为审批中', time: '2024-01-01 09:01', type: 'status' },
    { user: '王五', action: '终审通过', time: '2024-01-03 14:00' },
  ]

  it('节点含操作人/动作/时间', () => {
    const nodes: TimelineNode[] = buildApprovalTimeline(history, statusLogs)
    expect(nodes.length).toBe(4)
    nodes.forEach((n) => {
      expect(n.operator).toBeTruthy()
      expect(n.action).toBeTruthy()
      expect(n.time).toBeTruthy()
    })
  })

  it('聚合两源并按时间倒序', () => {
    const nodes = buildApprovalTimeline(history, statusLogs)
    expect(nodes[0].time).toBe('2024-01-03 14:00')
    expect(nodes[nodes.length - 1].time).toBe('2024-01-01 09:00')
  })

  it('缺省字段回退为 - / 空串但不崩溃', () => {
    const nodes = buildApprovalTimeline([{}], [null as any])
    expect(nodes[0].operator).toBe('-')
  })

  it('空输入返回空数组', () => {
    expect(buildApprovalTimeline([], [])).toEqual([])
  })
})
