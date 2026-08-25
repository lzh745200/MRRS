import request, { get, post } from '@/api/request'

// ── 经费回收站（Phase C 推广）──
export const restoreFund = (id: number) => post(`/funds/${id}/restore`, {})
export const previewPurgeFund = (id: number) => get(`/funds/${id}/purge/preview`)
export const purgeFund = (id: number, confirmPassword?: string) =>
  post(`/funds/${id}/purge`, { confirm_password: confirmPassword || '' })

// request 原始实例供个别调用点复用
export { request }
