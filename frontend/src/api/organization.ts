import { get, post, put, del } from '@/api/request'

export const getOrganizations = (params?: any) => get('/organizations', params)
export const getOrganization = (id: number) => get('/organizations/' + id)
export const getOrganizationTree = () => get('/organizations/tree')
export const createOrganization = (data: any) => post('/organizations', data)
export const updateOrganization = (id: number, data: any) => put('/organizations/' + id, data)
/**
 * 删除组织（后端逻辑删除）。
 *
 * 二次确认密码是后端 `DELETE /organizations/{id}` 的 **Query 参数**契约
 * （organization.py: confirm_password: str = Query("")），缺少或为空时后端
 * 恒返回 400「二次确认失败」——因此这里 fail-closed：没有密码直接抛错，
 * 不再发出必然失败的请求。
 *
 * 安全备注（残留风险，需与后端接口方协同）：密码仍在查询串中传输，
 * 会出现在 uvicorn access log 的请求行里。彻底消除需要后端把该参数改为
 * 请求体（Body）字段，属于 organization API 的改动，本次未越界修改。
 */
export const deleteOrganization = (id: number, confirmPassword?: string) => {
  if (!Number.isInteger(id) || id <= 0) {
    return Promise.reject(new Error('无效的组织 ID'))
  }
  const password = typeof confirmPassword === 'string' ? confirmPassword : ''
  if (!password) {
    return Promise.reject(new Error('删除组织需要二次确认密码'))
  }
  return del(`/organizations/${id}?confirm_password=${encodeURIComponent(password)}`)
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
