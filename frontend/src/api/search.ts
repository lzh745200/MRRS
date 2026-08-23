/**
 * 全局搜索 API
 *
 * 后端端点: GET /search?q=关键词&limit=20
 * 响应格式: Bare（{ total, items }，非 envelope）
 * 对应后端: backend/app/api/v1/search.py → SearchResponse
 */
import { get } from '@/api/request'

/** 搜索结果项（与后端 SearchItem 模型 1:1 对齐） */
export interface SearchItem {
  id: number
  type: 'village' | 'project' | 'policy' | 'school' | 'fund' | 'user'
  title: string
  subtitle?: string | null
  link: string
}

/** 搜索响应（与后端 SearchResponse 模型 1:1 对齐） */
export interface SearchResponse {
  total: number
  items: SearchItem[]
}

/**
 * 全局关键词搜索
 *
 * @param q 搜索关键词（1~100 字符）
 * @param limit 最大返回条数（默认 20，最大 50）
 */
export async function globalSearch(q: string, limit = 20): Promise<SearchResponse> {
  return get<SearchResponse>('/search', { q, limit })
}

/** 类型 → 中文标签映射（与后端 _get_entity_type 映射对齐） */
export const SEARCH_TYPE_LABELS: Record<SearchItem['type'], string> = {
  village: '帮扶村',
  project: '项目',
  policy: '政策法规',
  school: '学校',
  fund: '经费',
  user: '用户',
}

/** 类型 → Element Plus 图标名映射（供组件渲染） */
export const SEARCH_TYPE_ICONS: Record<SearchItem['type'], string> = {
  village: 'House',
  project: 'Document',
  policy: 'Tickets',
  school: 'School',
  fund: 'Money',
  user: 'UserFilled',
}
