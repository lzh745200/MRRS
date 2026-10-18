/**
 * views/bigscreen/bigscreenConfig.ts 单元测试（四指标 100%）
 *
 * 覆盖：默认配置、刷新频率归一化、配置归一化（未知/重复/缺失卡片、非法频率、
 * 非布尔脱敏）、localStorage 读写与损坏/不可用兜底、金额精度隐藏、负责人脱敏。
 */
import { describe, it, expect, vi } from 'vitest'
import {
  BIGSCREEN_CONFIG_KEY,
  BIG_SCREEN_CARDS,
  REFRESH_LABELS,
  REFRESH_OPTIONS,
  defaultBigScreenConfig,
  formatLeaderName,
  hideAmountPrecision,
  loadBigScreenConfig,
  normalizeBigScreenConfig,
  normalizeRefreshInterval,
  saveBigScreenConfig,
  type BigScreenConfig,
} from '@/views/bigscreen/bigscreenConfig'

function createStorage(initial?: string) {
  const map = new Map<string, string>()
  if (initial !== undefined) map.set(BIGSCREEN_CONFIG_KEY, initial)
  return {
    map,
    getItem: vi.fn((key: string) => map.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      map.set(key, String(value))
    }),
    removeItem: vi.fn((key: string) => map.delete(key)),
  } as unknown as Storage & { map: Map<string, string> }
}

const brokenStorage = {
  getItem: () => {
    throw new Error('storage denied')
  },
  setItem: () => {
    throw new Error('quota exceeded')
  },
  removeItem: () => {
    throw new Error('storage denied')
  },
} as unknown as Storage

describe('常量与默认配置', () => {
  it('刷新频率选项：30s / 60s / 5min / 关闭', () => {
    expect(REFRESH_OPTIONS.map((o) => o.value)).toEqual([30, 60, 300, 0])
    expect(REFRESH_LABELS[30]).toBe('30 秒')
    expect(REFRESH_LABELS[60]).toBe('60 秒')
    expect(REFRESH_LABELS[300]).toBe('5 分钟')
    expect(REFRESH_LABELS[0]).toBe('关闭自动刷新')
  })

  it('默认配置：全部卡片可见、30s 刷新、不脱敏', () => {
    const config = defaultBigScreenConfig()
    expect(config.refreshInterval).toBe(30)
    expect(config.desensitized).toBe(false)
    expect(config.cards).toHaveLength(BIG_SCREEN_CARDS.length)
    expect(config.cards.every((card) => card.visible)).toBe(true)
    expect(config.cards[0]).toMatchObject({ key: 'fundTrend', wide: true })
    // 每次返回新数组，避免多个组件实例共享可变状态
    expect(config.cards).not.toBe(defaultBigScreenConfig().cards)
  })
})

describe('normalizeRefreshInterval', () => {
  it('合法值原样保留，非法值回落 30 秒', () => {
    expect(normalizeRefreshInterval(30)).toBe(30)
    expect(normalizeRefreshInterval(60)).toBe(60)
    expect(normalizeRefreshInterval(300)).toBe(300)
    expect(normalizeRefreshInterval(0)).toBe(0)
    expect(normalizeRefreshInterval(45)).toBe(30)
    expect(normalizeRefreshInterval('60')).toBe(30)
    expect(normalizeRefreshInterval(null)).toBe(30)
  })
})

describe('normalizeBigScreenConfig', () => {
  it('非对象 / 数组 / null → 默认配置', () => {
    expect(normalizeBigScreenConfig(null)).toEqual(defaultBigScreenConfig())
    expect(normalizeBigScreenConfig(undefined)).toEqual(defaultBigScreenConfig())
    expect(normalizeBigScreenConfig('bad')).toEqual(defaultBigScreenConfig())
    expect(normalizeBigScreenConfig([])).toEqual(defaultBigScreenConfig())
  })

  it('cards 非数组 → 默认全部卡片可见', () => {
    const config = normalizeBigScreenConfig({ cards: 'bad' })
    expect(config.cards.map((c) => c.key)).toEqual(BIG_SCREEN_CARDS.map((c) => c.key))
    expect(config.cards.every((c) => c.visible)).toBe(true)
  })

  it('按保存顺序保留已知卡片，过滤重复/未知/非对象项，缺失卡片追加且可见', () => {
    const config = normalizeBigScreenConfig({
      cards: [
        { key: 'rank', visible: false },
        { key: 'yearly' },
        null,
        'bad',
        { key: 'unknown-card' },
        { key: 'rank', visible: true }, // 重复 key → 忽略
        { visible: true }, // 无 key → 忽略
        { key: 'fundTrend', visible: false },
      ],
    })
    // 顺序：rank（隐藏）→ yearly（可见）→ fundTrend（隐藏）→ 其余按默认顺序追加（可见）
    expect(config.cards.map((c) => c.key)).toEqual([
      'rank',
      'yearly',
      'fundTrend',
      'projectStatus',
      'leaders',
    ])
    expect(config.cards.find((c) => c.key === 'rank')?.visible).toBe(false)
    expect(config.cards.find((c) => c.key === 'yearly')?.visible).toBe(true)
    expect(config.cards.find((c) => c.key === 'leaders')?.visible).toBe(true)
    // 卡片元信息（title/wide）来自内置定义，不被 localStorage 篡改
    expect(config.cards.find((c) => c.key === 'fundTrend')).toMatchObject({
      title: '经费执行趋势',
      wide: true,
    })
  })

  it('刷新频率与脱敏字段归一化', () => {
    expect(normalizeBigScreenConfig({ refreshInterval: 60 }).refreshInterval).toBe(60)
    expect(normalizeBigScreenConfig({ refreshInterval: 123 }).refreshInterval).toBe(30)
    expect(normalizeBigScreenConfig({ desensitized: true }).desensitized).toBe(true)
    expect(normalizeBigScreenConfig({ desensitized: false }).desensitized).toBe(false)
    expect(normalizeBigScreenConfig({ desensitized: 'yes' }).desensitized).toBe(false)
  })
})

describe('loadBigScreenConfig / saveBigScreenConfig', () => {
  it('无记录 → 默认配置', () => {
    const storage = createStorage()
    expect(loadBigScreenConfig(storage)).toEqual(defaultBigScreenConfig())
    expect(storage.getItem).toHaveBeenCalledWith(BIGSCREEN_CONFIG_KEY)
  })

  it('合法记录 → 归一化后返回', () => {
    const storage = createStorage(
      JSON.stringify({
        cards: [{ key: 'leaders', visible: false }],
        refreshInterval: 300,
        desensitized: true,
      })
    )
    const config = loadBigScreenConfig(storage)
    expect(config.refreshInterval).toBe(300)
    expect(config.desensitized).toBe(true)
    expect(config.cards[0].key).toBe('leaders')
    expect(config.cards[0].visible).toBe(false)
  })

  it('损坏 JSON / getItem 抛错 → 默认配置（不抛错）', () => {
    expect(loadBigScreenConfig(createStorage('{broken'))).toEqual(defaultBigScreenConfig())
    expect(loadBigScreenConfig(brokenStorage)).toEqual(defaultBigScreenConfig())
  })

  it('save 写入 localStorage；setItem 抛错 → 静默降级', () => {
    const storage = createStorage()
    const config: BigScreenConfig = {
      ...defaultBigScreenConfig(),
      refreshInterval: 0,
      desensitized: true,
    }
    saveBigScreenConfig(config, storage)
    expect(JSON.parse(storage.map.get(BIGSCREEN_CONFIG_KEY) as string)).toMatchObject({
      refreshInterval: 0,
      desensitized: true,
    })
    expect(() => saveBigScreenConfig(config, brokenStorage)).not.toThrow()
  })

  it('默认使用全局 localStorage（不注入 storage 的默认分支）', () => {
    saveBigScreenConfig(defaultBigScreenConfig())
    expect(localStorage.getItem(BIGSCREEN_CONFIG_KEY)).toContain('fundTrend')
    expect(loadBigScreenConfig().cards).toHaveLength(BIG_SCREEN_CARDS.length)
  })
})

describe('hideAmountPrecision / formatLeaderName', () => {
  it('隐藏金额精度：四舍五入到整数，非法值回落 0', () => {
    expect(hideAmountPrecision(1234000.567)).toBe(1234001)
    expect(hideAmountPrecision('88.4')).toBe(88)
    expect(hideAmountPrecision(0)).toBe(0)
    expect(hideAmountPrecision(null)).toBe(0)
    expect(hideAmountPrecision(undefined)).toBe(0)
    expect(hideAmountPrecision('abc')).toBe(0)
  })

  it('负责人姓名：非脱敏原样、脱敏打码、空值占位', () => {
    expect(formatLeaderName('张三', false)).toBe('张三')
    expect(formatLeaderName('张三', true)).toBe('张*')
    expect(formatLeaderName('欧阳修文', true)).toBe('欧**文')
    expect(formatLeaderName(null, true)).toBe('—')
    expect(formatLeaderName(undefined, false)).toBe('—')
    expect(formatLeaderName('', true)).toBe('—')
  })
})
