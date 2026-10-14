import { get, post, put, apiRequest } from '@/api/request'

export const getOrganizations = (params?: any) => get('/organizations', params)
export const getOrganization = (id: number) => get('/organizations/' + id)
export const getOrganizationTree = () => get('/organizations/tree')
export const createOrganization = (data: any) => post('/organizations', data)
export const updateOrganization = (id: number, data: any) => put('/organizations/' + id, data)
/**
 * 删除组织（后端逻辑删除）。
 *
 * 二次确认密码自 2026-10-14 起改为 **请求头** `X-Confirm-Password`：
 * 此前放在 URL 查询串，会原样进 uvicorn access log，明文密码随之落盘。
 * 缺少或为空时后端恒返回 400「二次确认失败」——因此这里 fail-closed：
 * 没有密码直接抛错，不再发出必然失败的请求。
 */
export const deleteOrganization = (id: number, confirmPassword?: string) => {
  if (!Number.isInteger(id) || id <= 0) {
    return Promise.reject(new Error('无效的组织 ID'))
  }
  const password = typeof confirmPassword === 'string' ? confirmPassword : ''
  if (!password) {
    return Promise.reject(new Error('删除组织需要二次确认密码'))
  }
  return apiRequest({
    method: 'DELETE',
    url: `/organizations/${id}`,
    headers: { 'X-Confirm-Password': password },
  })
}
export const batchUpdateSortOrders = (d: any[]) => post('/organizations/batch-update-sort', d)

export const getMyOrganization = () => get('/organizations/my-organization')

export const getSubordinates = () => get('/organizations/subordinates')

export const getTypeOptions = () => get('/organizations/types/options')

export const getChildren = (orgId: number) => get(`/organizations/${orgId}/children`)

export const getAncestors = (orgId: number) => get(`/organizations/${orgId}/ancestors`)

export const moveOrganization = (orgId: number, data: any) =>
  post(`/organizations/${orgId}/move`, data)

export const activateOrganization = (orgId: number) => post(`/organizations/${orgId}/activate`)

export const deactivateOrganization = (orgId: number) => post(`/organizations/${orgId}/deactivate`)

// ==================== 新增接口 ====================

/** 获取组织统计信息 */
export const getOrganizationStatistics = () => get('/organizations/statistics/summary')

/** 获取组织成员列表 */
export const getOrganizationMembers = (orgId: number, params?: any) =>
  get(`/organizations/${orgId}/members`, params)

/** 获取组织详情（含子组织和成员数） */
export const getOrganizationDetail = (orgId: number) => get(`/organizations/${orgId}/detail`)
