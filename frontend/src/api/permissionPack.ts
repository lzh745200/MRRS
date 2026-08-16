/**
 * 权限包管理 API
 * 权限包 = 菜单套餐：管理员定义一组可见菜单 key，批量绑定给普通用户(user/viewer)，
 * 控制其可见功能板块。全部端点仅管理员可用。
 */
import { get, post, put, del } from '@/api/request'

// ==================== 类型定义 ====================

/** 权限包 */
export interface PermissionPack {
  id: number
  name: string
  description?: string
  menu_keys: string[]
  is_active: boolean
  bound_user_count: number
  created_by?: number
  created_at?: string
  updated_at?: string
}

/** 新建/更新权限包参数 */
export interface PermissionPackPayload {
  name: string
  description?: string
  menu_keys: string[]
  is_active?: boolean
}

/** 绑定/解绑用户结果 */
export interface BindUsersResult {
  bound_user_ids?: number[]
  unbound_user_ids?: number[]
}

const BASE = '/permission-packs'

// ==================== API 函数 ====================

/**
 * 获取权限包列表（含每个包绑定用户数）
 */
export async function listPermissionPacks(): Promise<PermissionPack[]> {
  const res = await get<any>(BASE)
  // 信封 data 为数组（拦截器同时展开为 items）
  const list = Array.isArray(res) ? res : (res?.data ?? res?.items ?? [])
  return Array.isArray(list) ? list : []
}

/**
 * 创建权限包
 */
export async function createPermissionPack(data: PermissionPackPayload): Promise<PermissionPack> {
  const res = await post<any>(BASE, data)
  return res?.data ?? res
}

/**
 * 更新权限包（仅更新传入字段）
 */
export async function updatePermissionPack(
  id: number,
  data: Partial<PermissionPackPayload>
): Promise<PermissionPack> {
  const res = await put<any>(`${BASE}/${id}`, data)
  return res?.data ?? res
}

/**
 * 删除权限包（仍有绑定用户时后端 400）
 */
export async function deletePermissionPack(id: number): Promise<void> {
  await del(`${BASE}/${id}`)
}

/**
 * 批量绑定用户（目标用户角色必须为 user/viewer）
 */
export async function bindPackUsers(id: number, userIds: number[]): Promise<BindUsersResult> {
  const res = await post<any>(`${BASE}/${id}/bind-users`, { user_ids: userIds })
  return res?.data ?? res
}

/**
 * 批量解绑用户（用户回落到角色默认菜单）
 */
export async function unbindPackUsers(id: number, userIds: number[]): Promise<BindUsersResult> {
  const res = await post<any>(`${BASE}/${id}/unbind-users`, { user_ids: userIds })
  return res?.data ?? res
}
