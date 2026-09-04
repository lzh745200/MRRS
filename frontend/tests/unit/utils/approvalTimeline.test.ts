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

/**
 * 单侧/双侧数据源缺失时的 `|| []` 兜底分支。
 * 后端详情接口在无审批历史或未开启状态日志时，对应字段会直接缺席（undefined）
 * 或为 null；调用方（如 approval/Detail.vue）不预先归一化就透传。
 */
describe('buildApprovalTimeline 数据源缺失兜底', () => {
  it('双源均为 null/undefined → 返回空数组，不抛 TypeError', () => {
    expect(buildApprovalTimeline(null as any, null as any)).toEqual([])
    expect(buildApprovalTimeline(undefined as any, undefined as any)).toEqual([])
  })

  it('仅 history 缺失 → 只保留状态日志节点（type 回退 status）', () => {
    const nodes = buildApprovalTimeline(null as any, [
      { actor: '系统', action: '状态变更为审批中', time: '2024-01-01 09:01' },
    ])
    expect(nodes).toHaveLength(1)
    expect(nodes[0]).toEqual({
      operator: '系统',
      action: '状态变更为审批中',
      time: '2024-01-01 09:01',
      type: 'status',
    })
  })

  it('仅 statusLogs 缺失 → 只保留审批历史节点（type 回退 history）', () => {
    const nodes = buildApprovalTimeline(
      [{ operator: '张三', action: '提交申请', time: '2024-01-01 09:00' }],
      undefined as any
    )
    expect(nodes).toHaveLength(1)
    expect(nodes[0].type).toBe('history')
    expect(nodes[0].operator).toBe('张三')
  })

  it('time 缺失时排序不抛（String(undefined) 参与 localeCompare）', () => {
    const nodes = buildApprovalTimeline(
      [{ operator: 'a', action: 'x' }, { operator: 'b', action: 'y', time: '2024-01-01' }],
      null as any
    )
    expect(nodes).toHaveLength(2)
    // 有时间的排前（倒序时空串最小）
    expect(nodes[0].time).toBe('2024-01-01')
    expect(nodes[1].time).toBe('')
  })
})
