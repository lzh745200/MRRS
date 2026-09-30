/**
 * 批量操作API服务
 * 提供批量更新、删除、导出和验证功能
 */

import { get, post } from '@/api/request'

const BASE_URL = '/batch'

/** 批量更新 */
export function batchUpdate(data: {
  table_name: string
  ids: number[]
  updates: Record<string, any>
}): Promise<any> {
  return post(`${BASE_URL}/update`, data)
}

/** 批量删除 */
export function batchDelete(data: {
  table_name: string
  ids: number[]
  soft_delete?: boolean
}): Promise<any> {
  return post(`${BASE_URL}/delete`, data)
}

/** 批量导出 */
export function batchExport(data: {
  table_name: string
  ids: number[]
  format?: string
}): Promise<any> {
  return post(`${BASE_URL}/export`, data)
}

/** 验证批量操作 */
export function validateBatch(tableName: string, ids: number[]): Promise<any> {
  return post(`${BASE_URL}/validate`, null, {
    params: { table_name: tableName, ids },
    // 后端 FastAPI 契约：ids: List[int] = Query(...)，要求重复查询键 `ids=1&ids=2`。
    // axios 默认把数组序列化为 `ids[]=1&ids[]=2`（键名变成 "ids[]"），后端取不到
    // ids → 该端点恒 422。indexes:null 表示不加方括号、重复同名键。
    paramsSerializer: { indexes: null },
  })
}

/** 获取批量操作状态 */
export function getBatchStatus(): Promise<any> {
  return get(`${BASE_URL}/status`)
}
