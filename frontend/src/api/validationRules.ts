/**
 * 数据校验规则API服务
 * 管理员可配置字段级校验规则，前端动态读取并实时校验
 */

import { get, post, put, del } from '@/api/request'

const BASE_URL = '/validation'

/** 校验规则（后端 /validation/rules 的常用字段） */
export interface ValidationRuleOut {
  id: number
  module: string
  field: string
  rule_type: string
  is_active?: boolean
  error_message?: string
  [key: string]: unknown
}

/** 校验执行结果（结构由规则决定，用索引签名放行） */
export interface ValidationRunResult {
  [key: string]: unknown
}

/** 获取校验规则列表 */
export function listRules(params?: {
  module?: string
  is_active?: boolean
}): Promise<ValidationRuleOut[] | { data?: ValidationRuleOut[]; items?: ValidationRuleOut[] }> {
  return get(`${BASE_URL}/rules`, params)
}

/** 创建校验规则（管理员） */
export function createRule(data: {
  module: string
  field: string
  rule_type: string
  params?: string
  error_message?: string
  description?: string
  is_active?: boolean
  priority?: number
}): Promise<any> {
  return post(`${BASE_URL}/rules`, data)
}

/** 更新校验规则 */
export function updateRule(
  ruleId: number,
  data: {
    module?: string
    field?: string
    rule_type?: string
    params?: string
    error_message?: string
    description?: string
    is_active?: boolean
    priority?: number
  }
): Promise<any> {
  return put(`${BASE_URL}/rules/${ruleId}`, data)
}

/** 删除校验规则 */
export function deleteRule(ruleId: number): Promise<any> {
  return del(`${BASE_URL}/rules/${ruleId}`)
}

/** 对提交数据执行校验 */
export function runValidation(
  module: string,
  data: Record<string, unknown>
): Promise<ValidationRunResult | { data?: ValidationRunResult }> {
  return post(`${BASE_URL}/validate`, data, { params: { module } })
}
