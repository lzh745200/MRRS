/**
 * 用户查询 API
 */
import { get } from '../request'

export async function getUsers(params?: any) {
  return get('/users', params)
}

export async function getUserById(id: string) {
  return get(`/users/${id}`)
}

/**
 * 人员列表（任务分配 / 审批转交等场景）。
 * 任何登录用户可访问，服务端按数据范围（ALL/OWN_DEPT/OWN）过滤。
 * 取代原 /user-management 列表（该接口 admin-only，普通审批人调用会 403）。
 */
export async function listStaff(params?: any) {
  return get('/users/staff-list', params)
}

export async function getCurrentUser() {
  return get('/auth/me')
}
