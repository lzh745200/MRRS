/**
 * AI智能分析API服务
 * 提供数据分析、趋势预测、异常检测、智能推荐、自然语言查询等功能
 */

import { get, post, apiRequest } from '@/api/request'

// ==================== AI 基础服务 (/ai/*) ====================

const AI_BASE = '/ai'

/** 获取AI服务运行状态 */
export function getStatus(): Promise<any> {
  return get(`${AI_BASE}/status`)
}

/** 执行AI数据分析 */
export function analyze(data: {
  analysis_type?: string
  data?: Record<string, any>
  description?: string
}): Promise<any> {
  return post(`${AI_BASE}/analyze`, data)
}

/** 获取基于上下文的智能推荐 */
export function getRecommendations(data: {
  context?: Record<string, any>
  category?: string
}): Promise<any> {
  return post(`${AI_BASE}/recommendations`, data)
}

/** 收入趋势预测 */
export function forecastIncome(forecastYears?: number): Promise<any> {
  return apiRequest({
    method: 'GET',
    url: `${AI_BASE}/forecast/income`,
    params: { forecast_years: forecastYears ?? 2 },
  })
}

/** 年度经费完成率预测 */
export function forecastFunds(): Promise<any> {
  return get(`${AI_BASE}/forecast/funds`)
}

// ==================== AI 增强服务 (/ai-enhanced/*) ====================

const AI_ENHANCED_BASE = '/ai-enhanced'

/** 趋势预测 */
export function predictTrend(data: {
  historical_data: Array<Record<string, any>>
  periods?: number
  date_field?: string
  value_field?: string
  method?: string
}): Promise<any> {
  return post(`${AI_ENHANCED_BASE}/predict`, data)
}

/** 异常检测 */
export function detectAnomalies(data: {
  data: Array<Record<string, any>>
  value_field?: string
  method?: string
  contamination?: number
}): Promise<any> {
  return post(`${AI_ENHANCED_BASE}/anomaly-detection`, data)
}

/** 项目推荐 */
export function recommendProjects(villageId: number, limit?: number): Promise<any> {
  return apiRequest({
    method: 'GET',
    url: `${AI_ENHANCED_BASE}/recommendations/projects`,
    params: { village_id: villageId, limit: limit ?? 5 },
  })
}

/** 资金分配建议 */
export function recommendFundAllocation(data: {
  total_budget: number
  village_ids: number[]
}): Promise<any> {
  return post(`${AI_ENHANCED_BASE}/recommendations/fund-allocation`, data)
}

/** 自然语言查询 */
export function nlpQuery(query: string): Promise<any> {
  return post(`${AI_ENHANCED_BASE}/nlp-query`, null, {
    params: { query },
  })
}

// ==================== AI 可解释性（rationale / data_scope，W17-008） ====================
// AI 结论必须能"说清楚依据"：后端每个 AI 端点都在响应里带结构化 rationale
// （方法/依据字段/窗口/算式/规则/假设）与 data_scope（参与计算的数据量/范围）。
// 这里做两件事：① 从各种响应包络里稳健提取这两块；② 转成前端「为什么」面板
// 可直出的键值行。禁止在此生成自然语言结论——只展示后端给出的结构化事实。

/** 结构化依据说明（与后端 rationale 字段一一对应） */
export interface AIRationale {
  version: number
  method: string
  basis_fields: string[]
  window: Record<string, any> | null
  formula: Record<string, any> | null
  rules: Array<Record<string, any>>
  assumptions: string[]
}

/** 参与计算的数据量与范围（与后端 data_scope 字段一一对应） */
export interface AIDataScope {
  dataset: string
  scope: string
  row_count: number | null
  granularity: string
  window: Record<string, any> | null
  filters: Array<Record<string, any>>
  counts: Record<string, any>
}

export interface AIExplainability {
  rationale: AIRationale
  data_scope: AIDataScope
}

/** 「为什么」面板的一行（中文标签 + 结构化值） */
export interface RationaleRow {
  label: string
  value: string
}

function isRecord(value: any): value is Record<string, any> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

function isExplainability(value: any): value is AIExplainability {
  return isRecord(value) && isRecord(value.rationale) && isRecord(value.data_scope)
}

/**
 * 从 AI 响应中提取结构化依据。
 *
 * 兼容三种包络：裸响应（ai-enhanced）、{data: {...}}（request 解包后仍可能带
 * data 层）、{data: {data: {...}}}（后端 success_response 双层）。
 * 找不到（旧缓存/异常响应）时返回 null，由调用方隐藏面板而不是编造依据。
 */
export function extractExplainability(payload: any): AIExplainability | null {
  const data = isRecord(payload) ? payload.data : null
  const inner = isRecord(data) ? data.data : null
  const candidates = [payload, data, inner]
  for (const candidate of candidates) {
    if (isExplainability(candidate)) {
      return { rationale: candidate.rationale, data_scope: candidate.data_scope }
    }
  }
  return null
}

/** 把 rationale 渲染为「为什么」面板的行；无依据返回空数组（面板隐藏）。 */
export function describeRationale(rationale: AIRationale | null | undefined): RationaleRow[] {
  if (!rationale) return []
  const rows: RationaleRow[] = [{ label: '方法', value: rationale.method }]
  if (rationale.basis_fields.length) {
    rows.push({ label: '依据字段', value: rationale.basis_fields.join('、') })
  }
  if (rationale.window) {
    rows.push({ label: '数据窗口', value: JSON.stringify(rationale.window) })
  }
  if (rationale.formula) {
    rows.push({ label: '算式/参数', value: JSON.stringify(rationale.formula) })
  }
  if (rationale.rules.length) {
    rows.push({
      label: '判定规则',
      value: rationale.rules.map((rule) => JSON.stringify(rule)).join('；'),
    })
  }
  if (rationale.assumptions.length) {
    rows.push({ label: '计算假设', value: rationale.assumptions.join('、') })
  }
  return rows
}

/** 一行式数据范围摘要，如「village_income · year · 12 条 · 范围 user_data_scope」。 */
export function describeDataScope(scope: AIDataScope | null | undefined): string {
  if (!scope) return ''
  const rowCount = scope.row_count === null ? '未知' : String(scope.row_count)
  return `${scope.dataset} · ${scope.granularity} · ${rowCount} 条 · 范围 ${scope.scope}`
}
