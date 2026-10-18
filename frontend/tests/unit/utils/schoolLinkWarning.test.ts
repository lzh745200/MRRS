/**
 * W10-030：学校删除前关联警示纯函数 + 计数拉取（列表页/详情页共用）
 * 覆盖 buildSchoolLinkWarning 全分支与 fetchSchoolLinkCounts 的三种响应形态与失败降级。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { getSchoolStatisticsMock, logWarn } = vi.hoisted(() => ({
  getSchoolStatisticsMock: vi.fn(),
  logWarn: vi.fn(),
}))

vi.mock('@/api/schools', () => ({
  schoolApi: { getSchoolStatistics: getSchoolStatisticsMock },
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: vi.fn(), warn: logWarn, info: vi.fn(), debug: vi.fn() },
}))

import { buildSchoolLinkWarning, fetchSchoolLinkCounts } from '@/utils/schoolLinkWarning'

describe('buildSchoolLinkWarning', () => {
  it('计数缺失 / 全为 0 → 空串（无关联不弹二次确认）', () => {
    expect(buildSchoolLinkWarning(undefined)).toBe('')
    expect(buildSchoolLinkWarning(null)).toBe('')
    expect(buildSchoolLinkWarning({})).toBe('')
    expect(buildSchoolLinkWarning({ scholarship_count: 0, project_count: 0 })).toBe('')
    // null 字段同样按 0 处理（?? 右侧分支）
    expect(buildSchoolLinkWarning({ scholarship_count: null, project_count: null })).toBe('')
  })

  it('仅有资助学生 → 文案只含学生部分', () => {
    const text = buildSchoolLinkWarning({ scholarship_count: 2 })
    expect(text).toContain('该校已关联2 名资助学生')
    expect(text).not.toContain('助学兴教项目')
    expect(text).toContain('删除前请确认')
  })

  it('仅有助学项目 → 文案只含项目部分', () => {
    const text = buildSchoolLinkWarning({ scholarship_count: 0, project_count: 3 })
    expect(text).toContain('该校已关联3 个助学兴教项目')
    expect(text).not.toContain('资助学生')
  })

  it('两类关联并存 → 顿号连接', () => {
    const text = buildSchoolLinkWarning({ scholarship_count: 5, project_count: 1 })
    expect(text).toBe(
      '该校已关联5 名资助学生、1 个助学兴教项目，删除前请确认无需继续维护这些关联数据。'
    )
  })

  it('字符串数字（后端 JSON 序列化兼容）→ 数值化后展示', () => {
    const text = buildSchoolLinkWarning({ scholarship_count: '4' as any, project_count: '2' as any })
    expect(text).toContain('4 名资助学生')
    expect(text).toContain('2 个助学兴教项目')
  })
})

describe('fetchSchoolLinkCounts', () => {
  beforeEach(() => vi.clearAllMocks())

  it('接口直返 payload → 原样返回并透传学校 id', async () => {
    const payload = { scholarship_count: 1, project_count: 2 }
    getSchoolStatisticsMock.mockResolvedValueOnce(payload)
    await expect(fetchSchoolLinkCounts(7)).resolves.toBe(payload)
    expect(getSchoolStatisticsMock).toHaveBeenCalledWith(7)
    expect(logWarn).not.toHaveBeenCalled()
  })

  it('响应带 data 包装 → 取内层数据', async () => {
    const inner = { scholarship_count: 3 }
    getSchoolStatisticsMock.mockResolvedValueOnce({ data: inner })
    await expect(fetchSchoolLinkCounts('9')).resolves.toBe(inner)
    expect(getSchoolStatisticsMock).toHaveBeenCalledWith('9')
  })

  it('接口返回 null/undefined → 返回 null（不抛错）', async () => {
    getSchoolStatisticsMock.mockResolvedValueOnce(null)
    await expect(fetchSchoolLinkCounts(1)).resolves.toBeNull()
  })

  it('拉取失败 → 计数降级为 null 并记录 warn（不阻断删除）', async () => {
    getSchoolStatisticsMock.mockRejectedValueOnce(new Error('net'))
    await expect(fetchSchoolLinkCounts(1)).resolves.toBeNull()
    expect(logWarn).toHaveBeenCalled()
    // 降级后警示文案为空 → 调用方走无关联确认路径
    expect(buildSchoolLinkWarning(null)).toBe('')
  })
})
