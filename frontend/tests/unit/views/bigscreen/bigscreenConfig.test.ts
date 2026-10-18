/**
 * views/bigscreen/bigscreenConfig.ts 单元测试（四指标 100%）
 *
 * 覆盖：默认配置、刷新频率归一化、配置归一化（未知/重复/缺失卡片、非法频率、
 * 非布尔脱敏）、筛选范围（scope）归一化、localStorage 读写与损坏/不可用兜底、
 * 金额精度隐藏、负责人脱敏。
 */
import { describe, it, expect, vi } from 'vitest'
import {
  BIGSCREEN_CONFIG_KEY,
  BIG_SCREEN_CARDS,
  BIG_SCREEN_SCOPE_OPTIONS,
  REFRESH_LABELS,
  REFRESH_OPTIONS,
  SCOPED_ONLY_CARD_KEYS,
  defaultBigScreenConfig,
  defaultBigScreenScope,
  formatLeaderName,
  hideAmountPrecision,
  loadBigScreenConfig,
  normalizeBigScreenConfig,
  normalizeBigScreenScope,
  normalizeBigScreenScopeType,
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
    removeItem: vi.fn((key: string) => {
      map.delete(key)
    }),
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

  it('筛选对象类型选项：全部 / 帮扶村 / 帮扶学校 / 帮扶单位', () => {
    expect(BIG_SCREEN_SCOPE_OPTIONS.map((o) => o.value)).toEqual([
      'all',
      'village',
      'school',
      'unit',
    ])
    expect(BIG_SCREEN_SCOPE_OPTIONS.map((o) => o.label)).toEqual([
      '全部',
      '帮扶村',
      '帮扶学校',
      '帮扶单位',
    ])
  })

  it('卡片定义：新增对象档案/帮扶明细，排名卡改为经费投入排名', () => {
    expect(BIG_SCREEN_CARDS.map((card) => card.key)).toContain('profile')
    expect(BIG_SCREEN_CARDS.map((card) => card.key)).toContain('details')
    expect(BIG_SCREEN_CARDS.find((card) => card.key === 'rank')?.title).toBe('经费投入排名')
    expect(BIG_SCREEN_CARDS.find((card) => card.key === 'profile')).toMatchObject({
      title: '对象档案',
      wide: false,
    })
    expect(BIG_SCREEN_CARDS.find((card) => card.key === 'details')).toMatchObject({
      title: '帮扶明细',
      wide: true,
    })
    // 仅选中具体对象时才有内容的卡片：由 BigScreen.vue 用于过滤渲染
    expect([...SCOPED_ONLY_CARD_KEYS]).toEqual(['profile', 'details'])
  })

  it('默认配置：全部卡片可见、30s 刷新、不脱敏、全部对象', () => {
    const config = defaultBigScreenConfig()
    expect(config.refreshInterval).toBe(30)
    expect(config.desensitized).toBe(false)
    expect(config.scope).toEqual({ type: 'all', id: null, name: null })
    expect(config.cards).toHaveLength(BIG_SCREEN_CARDS.length)
    expect(config.cards.every((card) => card.visible)).toBe(true)
    expect(config.cards[0]).toMatchObject({ key: 'fundTrend', wide: true })
    // 每次返回新对象/新数组，避免多个组件实例共享可变状态
    expect(config.cards).not.toBe(defaultBigScreenConfig().cards)
    expect(config.scope).not.toBe(defaultBigScreenConfig().scope)
  })

  it('默认筛选范围：全部对象', () => {
    expect(defaultBigScreenScope()).toEqual({ type: 'all', id: null, name: null })
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

describe('normalizeBigScreenScopeType / normalizeBigScreenScope', () => {
  it('对象类型：合法值原样保留，非法值回落 all', () => {
    expect(normalizeBigScreenScopeType('all')).toBe('all')
    expect(normalizeBigScreenScopeType('village')).toBe('village')
    expect(normalizeBigScreenScopeType('school')).toBe('school')
    expect(normalizeBigScreenScopeType('unit')).toBe('unit')
    expect(normalizeBigScreenScopeType('bad')).toBe('all')
    expect(normalizeBigScreenScopeType(null)).toBe('all')
    expect(normalizeBigScreenScopeType(42)).toBe('all')
  })

  it('非对象 / 数组 → 全部对象', () => {
    const fallback = defaultBigScreenScope()
    expect(normalizeBigScreenScope(null)).toEqual(fallback)
    expect(normalizeBigScreenScope(undefined)).toEqual(fallback)
    expect(normalizeBigScreenScope('bad')).toEqual(fallback)
    expect(normalizeBigScreenScope([])).toEqual(fallback)
  })

  it('帮扶村/学校：按整数 id 恢复，name 可空', () => {
    expect(normalizeBigScreenScope({ type: 'village', id: 3, name: '甲村' })).toEqual({
      type: 'village',
      id: 3,
      name: '甲村',
    })
    expect(normalizeBigScreenScope({ type: 'school', id: 5, name: '甲校' })).toEqual({
      type: 'school',
      id: 5,
      name: '甲校',
    })
    // name 非法（非字符串/空串）→ null，不影响村/校定位
    expect(normalizeBigScreenScope({ type: 'village', id: 3, name: 42 })).toEqual({
      type: 'village',
      id: 3,
      name: null,
    })
    expect(normalizeBigScreenScope({ type: 'village', id: 3, name: '' }).name).toBeNull()
    // id 缺失/非数字/非有限数 → 回落全部
    expect(normalizeBigScreenScope({ type: 'village', name: '甲村' })).toEqual(
      defaultBigScreenScope()
    )
    expect(normalizeBigScreenScope({ type: 'village', id: '3', name: '甲村' })).toEqual(
      defaultBigScreenScope()
    )
    expect(normalizeBigScreenScope({ type: 'school', id: Number.NaN, name: '甲校' })).toEqual(
      defaultBigScreenScope()
    )
  })

  it('帮扶单位：按非空 name 恢复，id 可空', () => {
    expect(normalizeBigScreenScope({ type: 'unit', name: '帮扶单位甲' })).toEqual({
      type: 'unit',
      id: null,
      name: '帮扶单位甲',
    })
    expect(normalizeBigScreenScope({ type: 'unit', name: '帮扶单位甲', id: 9 })).toEqual({
      type: 'unit',
      id: 9,
      name: '帮扶单位甲',
    })
    // name 缺失/空串/非字符串 → 回落全部
    expect(normalizeBigScreenScope({ type: 'unit' })).toEqual(defaultBigScreenScope())
    expect(normalizeBigScreenScope({ type: 'unit', name: '' })).toEqual(defaultBigScreenScope())
    expect(normalizeBigScreenScope({ type: 'unit', name: 123 })).toEqual(defaultBigScreenScope())
  })

  it('全部对象：忽略保存的 id/name', () => {
    expect(normalizeBigScreenScope({ type: 'all', id: 3, name: '甲村' })).toEqual(
      defaultBigScreenScope()
    )
    // 非法 type 也回落到全部
    expect(normalizeBigScreenScope({ type: 'bad', id: 3 })).toEqual(defaultBigScreenScope())
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
      'profile',
      'details',
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

  it('刷新频率、脱敏与筛选范围归一化', () => {
    expect(normalizeBigScreenConfig({ refreshInterval: 60 }).refreshInterval).toBe(60)
    expect(normalizeBigScreenConfig({ refreshInterval: 123 }).refreshInterval).toBe(30)
    expect(normalizeBigScreenConfig({ desensitized: true }).desensitized).toBe(true)
    expect(normalizeBigScreenConfig({ desensitized: false }).desensitized).toBe(false)
    expect(normalizeBigScreenConfig({ desensitized: 'yes' }).desensitized).toBe(false)
    expect(
      normalizeBigScreenConfig({ scope: { type: 'unit', name: '帮扶单位甲', id: null } }).scope
    ).toEqual({ type: 'unit', id: null, name: '帮扶单位甲' })
    expect(normalizeBigScreenConfig({ scope: 'bad' }).scope).toEqual(defaultBigScreenScope())
    expect(normalizeBigScreenConfig({}).scope).toEqual(defaultBigScreenScope())
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
        scope: { type: 'village', id: 7, name: '甲村' },
      })
    )
    const config = loadBigScreenConfig(storage)
    expect(config.refreshInterval).toBe(300)
    expect(config.desensitized).toBe(true)
    expect(config.cards[0].key).toBe('leaders')
    expect(config.cards[0].visible).toBe(false)
    expect(config.scope).toEqual({ type: 'village', id: 7, name: '甲村' })
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
      scope: { type: 'unit', id: null, name: '帮扶单位甲' },
    }
    saveBigScreenConfig(config, storage)
    expect(JSON.parse(storage.map.get(BIGSCREEN_CONFIG_KEY) as string)).toMatchObject({
      refreshInterval: 0,
      desensitized: true,
      scope: { type: 'unit', id: null, name: '帮扶单位甲' },
    })
    expect(() => saveBigScreenConfig(config, brokenStorage)).not.toThrow()
  })

  it('默认使用全局 localStorage（不注入 storage 的默认分支）', () => {
    saveBigScreenConfig(defaultBigScreenConfig())
    expect(localStorage.getItem(BIGSCREEN_CONFIG_KEY)).toContain('fundTrend')
    expect(loadBigScreenConfig().cards).toHaveLength(BIG_SCREEN_CARDS.length)
    expect(loadBigScreenConfig().scope).toEqual(defaultBigScreenScope())
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
