import { describe, expect, it } from 'vitest'
import { deriveActiveStep, type FundFlowNode } from '@/utils/fundStep'

// 7 态参数化：pending→planned→approved→allocated→in_use→completed→audited
const STEP_ORDER = ['pending', 'planned', 'approved', 'allocated', 'in_use', 'completed', 'audited']

function makeNodes(currentIdx: number, reachedCount?: number): FundFlowNode[] {
  return STEP_ORDER.map((status, i) => ({
    status,
    current: i === currentIdx,
    reached: reachedCount !== undefined ? i < reachedCount : i <= currentIdx,
  }))
}

describe('deriveActiveStep (T035)', () => {
  it('空节点返回 0', () => {
    expect(deriveActiveStep([])).toBe(0)
  })

  it('参数化覆盖 7 态：current 节点索引+1', () => {
    for (let i = 0; i < STEP_ORDER.length; i++) {
      const nodes = makeNodes(i)
      // active = 已完成步骤数 = current 索引 + 1
      expect(deriveActiveStep(nodes), `state=${STEP_ORDER[i]}`).toBe(i + 1)
    }
  })

  it('无 current 时回退到已到达节点数', () => {
    const nodes = STEP_ORDER.map((status, i) => ({
      status,
      current: false,
      reached: i < 3,
    }))
    expect(deriveActiveStep(nodes)).toBe(3)
  })

  it('pending 为首步 active=1', () => {
    expect(deriveActiveStep(makeNodes(0))).toBe(1)
  })

  it('audited 为末步 active=7', () => {
    expect(deriveActiveStep(makeNodes(6))).toBe(7)
  })
})
