/**
 * 政策记录（`/policies` 返回的常用字段）。
 *
 * 这是**接口边界类型**：只声明界面真正读写的字段，后端新增字段不会让编译失败；
 * 以前这些访问都写成宽松断言，代价是字段改名/拼错都发现不了。
 */
export interface PolicyRecord {
  id?: number
  title?: string
  category?: string
  organization_level?: string
  publish_date?: string
  effective_date?: string
  issuing_authority?: string
  department?: string
  content?: string
  summary?: string
  document_number?: string
  keywords?: string
  attachment_urls?: string[]
  status?: string
  created_at?: string
  updated_at?: string
}

/** 新增/更新政策的提交载荷（后端按存在字段写入） */
export type PolicyPayload = Partial<PolicyRecord>
