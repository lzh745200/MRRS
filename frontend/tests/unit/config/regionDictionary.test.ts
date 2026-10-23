/**
 * config/regionDictionary.ts 覆盖率补齐
 *
 * ## 为什么需要
 * 该文件是「离线地区字典」的唯一入口（`detectRegionAttributes` 被综合录入、
 * 帮扶村表单等多处调用）。此前**没有任何专属测试文件** —— 只有
 * `ComprehensiveEntryCov.test.ts` 顺带调用了它，导致一个分支长期未覆盖，
 * 前端覆盖率门禁（100%）因此长期红在本文件上。
 *
 * ## 覆盖的行为
 * 1. 传入**行政区划代码**（如 "520000"）→ 解析出中文省份标签；
 * 2. 传入**中文标签**（如 "贵州省"）→ 原样返回；
 * 3. 传入无法识别的值 → 原样返回（不臆造省份）；
 * 4. 传入空/未定义 → 返回空串；
 * 5. 契约锁：市/县参数被**有意忽略**（离线字典只有省市县名称，没有权威属性源），
 *    不得返回任何未经核定的布尔标记（如 `isThreeRegions`）。
 */
import { describe, it, expect } from 'vitest'
import { detectRegionAttributes } from '@/config/regionDictionary'

describe('detectRegionAttributes', () => {
  it('行政区划代码 → 中文省份标签', () => {
    expect(detectRegionAttributes('520000').province).toBe('贵州省')
  })

  it('中文标签 → 原样返回', () => {
    expect(detectRegionAttributes('贵州省').province).toBe('贵州省')
  })

  it('无法识别的值 → 原样返回（不臆造）', () => {
    expect(detectRegionAttributes('XX-UNKNOWN').province).toBe('XX-UNKNOWN')
  })

  it('空值 / 未定义 → 空串', () => {
    expect(detectRegionAttributes(undefined).province).toBe('')
    expect(detectRegionAttributes('').province).toBe('')
  })

  it('兼容旧版三参数调用：市/县参数被忽略', () => {
    // 只从省份值反查标签；市/县无权威字典可查
    expect(detectRegionAttributes('520000', '贵阳市', '云岩区').province).toBe('贵州省')
  })

  it('契约锁：不得返回任何未经核定的布尔标记', () => {
    const attrs = detectRegionAttributes('520000', '贵阳市', '云岩区')
    // 三区三州 / 边疆 / 民族 / 革命老区 / 重点帮扶县 均无离线权威源 → 一律不返回
    for (const key of [
      'isThreeRegions',
      'isBorder',
      'isEthnic',
      'isRevolutionary',
      'isKeyCounty',
    ]) {
      expect((attrs as Record<string, unknown>)[key]).toBeUndefined()
    }
  })
})
