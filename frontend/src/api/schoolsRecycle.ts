import { get, post } from '@/api/request'

// ── 学校回收站（Phase C 推广）──
export const restoreSchool = (id: number) => post(`/schools/${id}/restore`, {})
export const previewPurgeSchool = (id: number) => get(`/schools/${id}/purge/preview`)
export const purgeSchool = (id: number, confirmPassword?: string) =>
  post(`/schools/${id}/purge`, { confirm_password: confirmPassword || '' })
