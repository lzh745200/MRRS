import request, { get, post } from '@/api/request'

// ── 学校回收站（Phase C 推广）──
export const restoreSchool = (id: number) => post(`/schools/${id}/restore`, {})
export const previewPurgeSchool = (id: number) => get(`/schools/${id}/purge/preview`)
export const purgeSchool = (id: number, confirmPassword?: string) =>
  post(`/schools/${id}/purge`, { confirm_password: confirmPassword || '' })

// 保留 request 引用避免 tree-shaking 警告（部分调用点仍走原始实例）
export { request }
