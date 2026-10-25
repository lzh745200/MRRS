import { describe, expect, it } from 'vitest'

import {
  CONSUMPTION_PASTE_COLUMNS,
  buildConsumptionPayloads,
  parseAmount,
  parseQuantity,
  parseRecordDate,
  parseYear,
  resolveCategory,
} from '@/utils/consumptionPaste'

const YEAR = 2026

describe('列声明', () => {
  it('列顺序与解析索引一致（品类/品名/数量/单位/金额/购买方/销售方/年度/日期）', () => {
    expect(CONSUMPTION_PASTE_COLUMNS.map((c) => c.key)).toEqual([
      'category',
      'item_name',
      'quantity',
      'unit',
      'amount',
      'buyer',
      'seller',
      'year',
      'record_date',
    ])
  })

  it('必填列标注正确', () => {
    expect(CONSUMPTION_PASTE_COLUMNS.filter((c) => c.required).map((c) => c.key)).toEqual([
      'category',
      'item_name',
      'amount',
    ])
  })
})

describe('resolveCategory', () => {
  it('接受中文标签', () => {
    expect(resolveCategory('农产品')).toBe('agriculture')
  })

  it('接受枚举值', () => {
    expect(resolveCategory('agriculture')).toBe('agriculture')
  })

  it('空串/未知 → null', () => {
    expect(resolveCategory('')).toBeNull()
    expect(resolveCategory('   ')).toBeNull()
    expect(resolveCategory('不存在的品类')).toBeNull()
  })
})

describe('parseAmount', () => {
  it('去千分位与货币符号', () => {
    expect(parseAmount('¥1,200.50元')).toBe(1200.5)
  })

  it('非正数/空/非数字 → null', () => {
    expect(parseAmount('0')).toBeNull()
    expect(parseAmount('-5')).toBeNull()
    expect(parseAmount('')).toBeNull()
    expect(parseAmount('abc')).toBeNull()
  })
})

describe('parseQuantity', () => {
  it('正数有效，空与非法返回 null（表示未填）', () => {
    expect(parseQuantity('12')).toBe(12)
    expect(parseQuantity('')).toBeNull()
    expect(parseQuantity('0')).toBeNull()
    expect(parseQuantity('abc')).toBeNull()
  })
})

describe('parseYear', () => {
  it('合法年份原样，空/非法/越界回退默认年', () => {
    expect(parseYear('2025', YEAR)).toBe(2025)
    expect(parseYear('', YEAR)).toBe(YEAR)
    expect(parseYear('abc', YEAR)).toBe(YEAR)
    expect(parseYear('1900', YEAR)).toBe(YEAR)
    expect(parseYear('3000', YEAR)).toBe(YEAR)
    expect(parseYear('2025.5', YEAR)).toBe(YEAR)
  })
})

describe('parseRecordDate', () => {
  it('三种写法都归一成 YYYY-MM-DD', () => {
    expect(parseRecordDate('2026-03-04')).toBe('2026-03-04')
    expect(parseRecordDate('2026/3/4')).toBe('2026-03-04')
    expect(parseRecordDate('2026年3月4日')).toBe('2026-03-04')
  })

  it('空/无法解析/非法月日 → null', () => {
    expect(parseRecordDate('')).toBeNull()
    expect(parseRecordDate('无')).toBeNull()
    expect(parseRecordDate('2026-13-01')).toBeNull()
    expect(parseRecordDate('2026-01-45')).toBeNull()
  })
})

describe('buildConsumptionPayloads', () => {
  it('完整行 → 完整 payload（含空列留空）', () => {
    const { payloads, errors } = buildConsumptionPayloads(
      [['农产品', '土鸡蛋', '100', '斤', '2,000', '某局', '某合作社', '2025', '2025/6/1']],
      { year: YEAR }
    )
    expect(errors).toEqual([])
    expect(payloads).toHaveLength(1)
    expect(payloads[0]).toMatchObject({
      category: 'agriculture',
      item_name: '土鸡蛋',
      quantity: 100,
      unit: '斤',
      amount: 2000,
      buyer: '某局',
      seller: '某合作社',
      year: 2025,
      record_date: '2025-06-01',
    })
  })

  it('空的可选列 → null（不因为缺列拒绝整批）', () => {
    const { payloads, errors } = buildConsumptionPayloads([['农产品', '蜂蜜', '', '', '500', '', '', '', '']], {
      year: YEAR,
    })
    expect(errors).toEqual([])
    expect(payloads[0]).toMatchObject({
      quantity: null,
      unit: null,
      buyer: null,
      seller: null,
      year: YEAR,
      record_date: null,
    })
  })

  it('逐行报错：品类未知 / 品名为空 / 金额无效，且成功行不受影响', () => {
    const { payloads, errors } = buildConsumptionPayloads(
      [
        ['未知品类', '甲', '', '', '100', '', '', '', ''],
        ['农产品', '', '', '', '100', '', '', '', ''],
        ['农产品', '乙', '', '', '0', '', '', '', ''],
        ['农产品', '丙', '', '', '300', '', '', '', ''],
      ],
      { year: YEAR }
    )
    expect(payloads).toHaveLength(1)
    expect(payloads[0].item_name).toBe('丙')
    expect(errors.map((e) => e.index)).toEqual([1, 2, 3])
    expect(errors[0].message).toContain('品类无法识别')
    expect(errors[1].message).toContain('品名为空')
    expect(errors[2].message).toContain('金额无效')
  })

  it('行号是 1 基，与预览表格 # 一致', () => {
    const { errors } = buildConsumptionPayloads([['x', 'y', '', '', ''], ['农产品', '', '', '', '1']], {
      year: YEAR,
    })
    expect(errors[0].index).toBe(1)
    expect(errors[1].index).toBe(2)
  })

  it('短行（Excel 省略行尾空格）与空品类/空金额的错误文案带"空"', () => {
    // 只有两列：品类空、金额列根本不存在
    const first = buildConsumptionPayloads([['', '品名']], { year: YEAR })
    expect(first.payloads).toEqual([])
    expect(first.errors[0].index).toBe(1)
    expect(first.errors[0].message).toContain('空')

    // 品类有效、金额缺失（行短，走 row[n] ?? '' 兜底）
    const second = buildConsumptionPayloads([['农产品', '品名']], { year: YEAR })
    expect(second.payloads).toEqual([])
    expect(second.errors[0].message).toContain('金额无效')
    expect(second.errors[0].message).toContain('空')
  })

  it('空输入 → 空结果（不发请求）', () => {
    expect(buildConsumptionPayloads([], { year: YEAR })).toEqual({ payloads: [], errors: [] })
  })

  it('可选传 supported_village_id（页面选中的帮扶村）', () => {
    const { payloads } = buildConsumptionPayloads([['农产品', '茶叶', '', '', '100']], {
      year: YEAR,
      supportedVillageId: 42,
    })
    expect(payloads[0].supported_village_id).toBe(42)
  })
})
