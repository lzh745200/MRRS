/**
 * 用户管理 API
 * 提供用户完整 CRUD 操作、密码管理、角色分配等功能
 */

import { get, post, put, del } from '@/api/request'

// ==================== 类型定义 ====================

/** 用户信息 */
export interface ManagedUser {
  id: string
  username: string
  name: string
  role: string
  department: string
  phone: string
  email: string
  status: 'active' | 'inactive'
  lastLogin: string
  organization_id?: number
  organization_name?: string
}

/** 用户列表响应 */
export interface UserListResponse {
  items: ManagedUser[]
  total: number
  page: number
  page_size: number
}

/** 创建用户参数 */
export interface CreateUserParams {
  username: string
  full_name?: string
  password?: string
  email?: string
  phone?: string
  department?: string
  role?: string
  is_active?: boolean
  organization_id?: number
}

/** 更新用户参数 */
export interface UpdateUserParams {
  full_name?: string
  name?: string
  email?: string
  phone?: string
  department?: string
  role?: string
  is_active?: boolean
  status?: string
  organization_id?: number
}

/** 角色信息 */
export interface RoleInfo {
  id: string
  name: string
  code: string
  description: string
  is_system: boolean
  user_count: number
}

/** 角色列表响应 */
export interface RoleListResponse {
  items: RoleInfo[]
  total: number
}

// ==================== API 函数 ====================

/** 获取用户列表 */
export async function listUsers(params?: {
  page?: number
  page_size?: number
  username?: string
  name?: string
  role?: string
  status?: string
}): Promise<{ success: boolean; data: UserListResponse }> {
  return get('/user-management', params)
}

/** 创建用户 */
export async function createUser(data: CreateUserParams): Promise<{
  success: boolean
  message: string
  data: { id: string; username: string; password: string }
}> {
  return post('/user-management', data)
}

/** 更新用户信息 */
export async function updateUser(
  userId: number,
  data: UpdateUserParams
): Promise<{ success: boolean; message: string }> {
  return put(`/user-management/${userId}`, data)
}

/** 删除用户 */
export async function deleteUser(userId: number): Promise<{
  success: boolean
  message: string
  deleted_records?: number
  set_null_records?: number
}> {
  return del(`/user-management/${userId}`)
}

/** 重置用户密码 */
export async function resetPassword(
  userId: number,
  newPassword?: string
): Promise<{
  success: boolean
  message: string
  data: { username: string; new_password: string }
}> {
  return post(`/user-management/${userId}/reset-password`, {
    new_password: newPassword,
  })
}

/** 为用户分配角色 */
export async function assignUserRole(
  userId: number,
  roleCode: string
): Promise<{ success: boolean; message: string }> {
  return post(`/user-management/${userId}/assign-role?role_code=${encodeURIComponent(roleCode)}`)
}

/** 生成随机密码 */
export async function generatePassword(
  length?: number
): Promise<{ success: boolean; data: { password: string } }> {
  return get('/user-management/generate-password', length ? { length } : undefined)
}

/** 获取角色列表 */
export async function listRoles(): Promise<{
  success: boolean
  data: RoleListResponse
}> {
  return get('/user-management/roles')
}
