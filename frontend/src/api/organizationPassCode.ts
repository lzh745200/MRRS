import { get, post, del, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

export type CreateOrganizationPassCodeRequest = {
  organization_id: number
  verification_code: string
  allow_subordinate_generation?: boolean
  description?: string
}

export type OrganizationPassCodeResponse = {
  id: number
  organization_id: number
  organization_name?: string
  pass_code: string
  status: string
  created_at?: string
  expires_at?: string
  description?: string
}

/** 获取组织校验码 — 返回已解包数据，可直接访问 .verification_code */
/** 兼容两种形态：展开后的顶层字段，或包一层 data */
export type VerificationCodePayload = {
  verification_code?: string
  organization_id?: number
  organization_name?: string
  data?: { verification_code?: string }
}

export const getOrganizationVerificationCode = (orgId: number) =>
  get<VerificationCodePayload>(`/machine-code/organization/${orgId}/verification-code`)

/** 创建组织通行证码 — 返回已解包数据，可直接访问 .pass_code */
export type CreatedPassCodePayload = {
  pass_code?: string
  id?: number
  organization_id?: number
  data?: { pass_code?: string }
}

export const createOrganizationPassCode = (data: CreateOrganizationPassCodeRequest) =>
  post<CreatedPassCodePayload>('/machine-code/organization/create', data)

/** 查询组织通行证码列表 — 返回已解包数据，可直接访问 .items / .total */
export const getOrganizationPassCodeList = (params?: {
  organization_id?: number
  status?: string
  page?: number
  page_size?: number
}) =>
  get<{ total: number; items: OrganizationPassCodeResponse[] }>(
    '/machine-code/organization/list',
    params
  )

/** 导出组织通行证码 Excel — 内部处理下载，调用方只需 await */
export const exportOrganizationPassCodes = async (params?: {
  organization_id?: number
  status?: string
}) => {
  await downloadBlobAsFile(
    () =>
      apiRequest<Blob>({
        method: 'GET',
        url: '/machine-code/organization/export',
        params,
        responseType: 'blob',
      }),
    { fallbackFileName: '组织通行证码.xlsx' }
  )
}

/** 删除组织通行证码记录（管理员） */
export const deleteOrganizationPassCode = (passCodeId: number) =>
  del<{ success: boolean; message: string }>(`/machine-code/organization/${passCodeId}`)
