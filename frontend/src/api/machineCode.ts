/**
 * 机器码管理 API
 */

import { apiRequest } from '@/api/request'

export interface MachineCodeInfo {
  machine_code: string
  verification_code: string
  machine_info: {
    system: string
    release: string
    version: string
    machine: string
    processor: string
    node: string
    cpu_name?: string
    memory_gb?: number
  }
}

export interface MachineCodeRecord {
  id: number
  machine_code: string
  pass_code: string
  status: 'pending' | 'active' | 'revoked'
  user_id?: number
  username?: string
  description?: string
  created_at: string
  activated_at?: string
}

export interface MachineCodeListResponse {
  total: number
  items: MachineCodeRecord[]
}

/**
 * 获取当前机器的机器码
 */
export function getMachineCode() {
  return apiRequest<{ data: MachineCodeInfo }>({
    url: '/machine-code/get-machine-code',
    method: 'get',
  })
}

/**
 * 管理员录入机器码并生成通行码
 * 返回已解包数据：{ code, data: {...}, message, pass_code, ... }
 */
export function createMachineCode(data: {
  machine_code: string
  description?: string
  pass_code?: string
}) {
  return apiRequest<{ code: number; pass_code: string; id: number }>({
    url: '/machine-code/admin/create',
    method: 'post',
    data,
  })
}

/**
 * 管理员查询机器码列表
 * 返回已解包数据：{ code, data: { total, items }, message, total, items }
 */
export function listMachineCodes(params?: {
  status_filter?: string
  skip?: number
  limit?: number
}) {
  return apiRequest<{ data: MachineCodeListResponse; total: number; items: MachineCodeRecord[] }>({
    url: '/machine-code/admin/list',
    method: 'get',
    params,
  })
}

/**
 * 管理员撤销机器码
 */
export function revokeMachineCode(machineCodeId: number) {
  return apiRequest({
    url: `/machine-code/admin/revoke/${machineCodeId}`,
    method: 'post',
  })
}

/**
 * 验证机器码和校验码
 */
export function verifyMachineCode(data: { machine_code: string; verification_code: string }) {
  return apiRequest<{ data: { is_valid: boolean } }>({
    url: '/machine-code/verify-machine-code',
    method: 'post',
    data,
  })
}

/**
 * 生成初始密码
 */
export function generateInitialPassword(data: { username: string; verification_code: string }) {
  return apiRequest({
    url: '/machine-code/generate-initial-password',
    method: 'post',
    data,
  })
}

/**
 * 使用机器码重置密码
 */
export function resetPasswordWithMachineCode(data: {
  username: string
  machine_code: string
  verification_code: string
}) {
  return apiRequest({
    url: '/machine-code/reset-password-with-machine-code',
    method: 'post',
    data,
  })
}

/**
 * 获取机器信息
 */
export function getMachineInfo() {
  return apiRequest({
    url: '/machine-code/machine-info',
    method: 'get',
  })
}

/**
 * 获取组织验证码
 */
export function getOrganizationVerificationCode(orgId: number) {
  return apiRequest({
    url: `/machine-code/organization/${orgId}/verification-code`,
    method: 'get',
  })
}

/**
 * 创建组织通行码
 */
export function createOrganizationPassCode(data: Record<string, any>) {
  return apiRequest({
    url: '/machine-code/organization/create',
    method: 'post',
    data,
  })
}

/**
 * 获取组织通行码列表
 */
export function listOrganizationPassCodes(params?: { page?: number; page_size?: number }) {
  return apiRequest({
    url: '/machine-code/organization/list',
    method: 'get',
    params,
  })
}

/**
 * 导出组织通行码
 * @deprecated 使用 @/api/organizationPassCode 中的 exportOrganizationPassCodes 替代
 */
export function exportOrganizationPassCodes() {
  return apiRequest({
    url: '/machine-code/organization/export',
    method: 'get',
    responseType: 'blob',
  })
}
