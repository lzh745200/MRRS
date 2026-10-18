import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockApiRequest } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockApiRequest: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  apiRequest: mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import {
  getStatus,
  analyze,
  getRecommendations,
  forecastIncome,
  forecastFunds,
  predictTrend,
  detectAnomalies,
  recommendProjects,
  recommendFundAllocation,
  nlpQuery,
  extractExplainability,
  describeRationale,
  describeDataScope,
} from '@/api/ai'

describe('api/ai', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getStatus GET /ai/status', async () => {
    const body = { status: 'ok' }
    mockGet.mockResolvedValueOnce(body)
    const r = await getStatus()
    expect(mockGet).toHaveBeenCalledWith('/ai/status')
    expect(r).toBe(body)
  })

  it('analyze POST /ai/analyze', async () => {
    const body = { result: 'done' }
    mockPost.mockResolvedValueOnce(body)
    const data = { analysis_type: 'trend', data: { year: 2026 } }
    const r = await analyze(data)
    expect(mockPost).toHaveBeenCalledWith('/ai/analyze', data)
    expect(r).toBe(body)
  })

  it('getRecommendations POST /ai/recommendations', async () => {
    const body = { items: [] }
    mockPost.mockResolvedValueOnce(body)
    const data = { context: { village_id: 1 }, category: 'project' }
    const r = await getRecommendations(data)
    expect(mockPost).toHaveBeenCalledWith('/ai/recommendations', data)
    expect(r).toBe(body)
  })

  it('forecastIncome 默认 forecast_years=2', async () => {
    const body = { forecast: [] }
    mockApiRequest.mockResolvedValueOnce(body)
    const r = await forecastIncome()
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/ai/forecast/income',
      params: { forecast_years: 2 },
    })
    expect(r).toBe(body)
  })

  it('forecastIncome 自定义年数', async () => {
    mockApiRequest.mockResolvedValueOnce({ forecast: [] })
    await forecastIncome(5)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/ai/forecast/income',
      params: { forecast_years: 5 },
    })
  })

  it('forecastFunds GET /ai/forecast/funds', async () => {
    const body = { completion_rate: 0.9 }
    mockGet.mockResolvedValueOnce(body)
    const r = await forecastFunds()
    expect(mockGet).toHaveBeenCalledWith('/ai/forecast/funds')
    expect(r).toBe(body)
  })

  it('predictTrend POST /ai-enhanced/predict', async () => {
    const body = { trend: [] }
    mockPost.mockResolvedValueOnce(body)
    const data = { historical_data: [{ year: 2025, value: 100 }], periods: 3 }
    const r = await predictTrend(data)
    expect(mockPost).toHaveBeenCalledWith('/ai-enhanced/predict', data)
    expect(r).toBe(body)
  })

  it('detectAnomalies POST /ai-enhanced/anomaly-detection', async () => {
    const body = { anomalies: [] }
    mockPost.mockResolvedValueOnce(body)
    const data = { data: [{ value: 1 }], value_field: 'value' }
    const r = await detectAnomalies(data)
    expect(mockPost).toHaveBeenCalledWith('/ai-enhanced/anomaly-detection', data)
    expect(r).toBe(body)
  })

  it('recommendProjects 默认 limit=5', async () => {
    const body = { projects: [] }
    mockApiRequest.mockResolvedValueOnce(body)
    const r = await recommendProjects(3)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/ai-enhanced/recommendations/projects',
      params: { village_id: 3, limit: 5 },
    })
    expect(r).toBe(body)
  })

  it('recommendProjects 自定义 limit', async () => {
    mockApiRequest.mockResolvedValueOnce({ projects: [] })
    await recommendProjects(3, 10)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/ai-enhanced/recommendations/projects',
      params: { village_id: 3, limit: 10 },
    })
  })

  it('recommendFundAllocation POST /ai-enhanced/recommendations/fund-allocation', async () => {
    const body = { allocation: [] }
    mockPost.mockResolvedValueOnce(body)
    const data = { total_budget: 100000, village_ids: [1, 2] }
    const r = await recommendFundAllocation(data)
    expect(mockPost).toHaveBeenCalledWith('/ai-enhanced/recommendations/fund-allocation', data)
    expect(r).toBe(body)
  })

  it('nlpQuery POST /ai-enhanced/nlp-query 带 query 参数', async () => {
    const body = { answer: 'ok' }
    mockPost.mockResolvedValueOnce(body)
    const r = await nlpQuery('今年收入多少')
    expect(mockPost).toHaveBeenCalledWith('/ai-enhanced/nlp-query', null, {
      params: { query: '今年收入多少' },
    })
    expect(r).toBe(body)
  })
})

// ==================== AI 可解释性（rationale / data_scope，W17-008） ====================

const RATIONALE = {
  version: 1,
  method: 'ordinary_least_squares_regression',
  basis_fields: ['VillageIncome.year', 'VillageIncome.per_capita_income'],
  window: { start_year: 2021, end_year: 2026, year_count: 6 },
  formula: { kind: 'linear_regression' },
  rules: [{ id: 'low_risk' }, { id: 'high_risk' }],
  assumptions: ['user_data_scope_applied'],
}

const DATA_SCOPE = {
  dataset: 'village_income',
  scope: 'user_data_scope',
  row_count: 6,
  granularity: 'year',
  window: null,
  filters: [],
  counts: { forecast_years: 2 },
}

const EXPLAINABILITY = { rationale: RATIONALE, data_scope: DATA_SCOPE }

describe('api/ai 可解释性提取', () => {
  beforeEach(() => vi.clearAllMocks())

  it('裸响应（ai-enhanced）直接提取', () => {
    expect(extractExplainability({ ...EXPLAINABILITY })).toEqual({
      rationale: RATIONALE,
      data_scope: DATA_SCOPE,
    })
  })

  it('{data: {...}} 解包后提取', () => {
    expect(extractExplainability({ data: { ...EXPLAINABILITY } })).toEqual({
      rationale: RATIONALE,
      data_scope: DATA_SCOPE,
    })
  })

  it('{data: {data: {...}}} 双层信封提取', () => {
    expect(extractExplainability({ data: { data: { ...EXPLAINABILITY } } })).toEqual({
      rationale: RATIONALE,
      data_scope: DATA_SCOPE,
    })
  })

  it('非对象/空值/数组/字符串 → null（不编造依据）', () => {
    expect(extractExplainability(null)).toBeNull()
    expect(extractExplainability(undefined)).toBeNull()
    expect(extractExplainability('text')).toBeNull()
    expect(extractExplainability(42)).toBeNull()
    expect(extractExplainability([])).toBeNull()
    expect(extractExplainability({ data: [] })).toBeNull()
  })

  it('缺 rationale / 缺 data_scope 的半结构响应 → null', () => {
    expect(extractExplainability({ rationale: RATIONALE })).toBeNull()
    expect(extractExplainability({ data_scope: DATA_SCOPE })).toBeNull()
    expect(extractExplainability({ rationale: RATIONALE, data_scope: 'no' })).toBeNull()
    expect(extractExplainability({ data: { rationale: RATIONALE } })).toBeNull()
  })

  it('description: 完整 rationale 渲染 6 行结构化依据', () => {
    const rows = describeRationale(RATIONALE)
    expect(rows.map((row) => row.label)).toEqual([
      '方法',
      '依据字段',
      '数据窗口',
      '算式/参数',
      '判定规则',
      '计算假设',
    ])
    expect(rows[0].value).toBe('ordinary_least_squares_regression')
    expect(rows[1].value).toBe('VillageIncome.year、VillageIncome.per_capita_income')
    expect(rows[2].value).toContain('2021')
    expect(rows[3].value).toContain('linear_regression')
    expect(rows[4].value).toContain('low_risk')
    expect(rows[4].value).toContain('high_risk')
    expect(rows[5].value).toBe('user_data_scope_applied')
  })

  it('description: 最小 rationale 只渲染方法行', () => {
    const rows = describeRationale({
      version: 1,
      method: 'count',
      basis_fields: [],
      window: null,
      formula: null,
      rules: [],
      assumptions: [],
    })
    expect(rows).toEqual([{ label: '方法', value: 'count' }])
  })

  it('description: 无 rationale 返回空数组（面板隐藏）', () => {
    expect(describeRationale(null)).toEqual([])
    expect(describeRationale(undefined)).toEqual([])
  })

  it('description: data_scope 摘要文本', () => {
    expect(describeDataScope(null)).toBe('')
    expect(describeDataScope(undefined)).toBe('')
    expect(describeDataScope({ ...DATA_SCOPE, row_count: null })).toBe(
      'village_income · year · 未知 条 · 范围 user_data_scope'
    )
    expect(describeDataScope(DATA_SCOPE)).toBe(
      'village_income · year · 6 条 · 范围 user_data_scope'
    )
  })
})
