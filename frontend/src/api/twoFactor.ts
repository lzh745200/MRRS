/**
 * 双因素认证 API
 * 提供 TOTP 双因素认证的启用、验证、禁用和状态查询
 */

import { get, post } from '@/api/request'

// ==================== 类型定义 ====================

/** 启用双因素认证响应 */
export interface EnableTwoFactorResponse {
  secret: string
  qr_code: string
  backup_codes: string[]
}

/** 双因素认证状态 */
export interface TwoFactorStatus {
  enabled: boolean
}

/** 2FA登录验证响应（与 LoginPayload 结构一致） */
export interface TwoFactorLoginVerifyResponse {
  code: number
  data: {
    access_token: string
    token_type: string
    user: any
  } | null
  message: string
  must_change_password?: boolean
  refresh_token?: string
  two_factor_required?: boolean
  temp_token?: string
  is_first_login?: boolean
}

// ==================== API 函数 ====================

/** 启用双因素认证（返回密钥、二维码和备用码） */
export async function enableTwoFactor(): Promise<EnableTwoFactorResponse> {
  return post<EnableTwoFactorResponse>('/two-factor/enable')
}

/** 验证 TOTP 令牌并正式启用双因素认证 */
export async function verifyAndEnableTwoFactor(token: string): Promise<{ message: string }> {
  return post<{ message: string }>('/two-factor/verify', { token })
}

/** 禁用双因素认证 */
export async function disableTwoFactor(): Promise<{ message: string }> {
  return post<{ message: string }>('/two-factor/disable')
}

/** 获取双因素认证状态 */
export async function getTwoFactorStatus(): Promise<TwoFactorStatus> {
  return get<TwoFactorStatus>('/two-factor/status')
}

/** 2FA登录验证：使用 temp_token + TOTP 验证码完成登录 */
export async function verifyLoginTwoFactor(
  tempToken: string,
  code: string
): Promise<TwoFactorLoginVerifyResponse> {
  return post<TwoFactorLoginVerifyResponse>('/auth/two-factor/verify-login', {
    temp_token: tempToken,
    code,
  })
}

// ==================== 分组导出 ====================

export const twoFactorApi = {
  enable: enableTwoFactor,
  verifyAndEnable: verifyAndEnableTwoFactor,
  disable: disableTwoFactor,
  getStatus: getTwoFactorStatus,
  verifyLogin: verifyLoginTwoFactor,
}
