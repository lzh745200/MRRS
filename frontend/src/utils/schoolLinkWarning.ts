// W10-030：学校删除前关联检查（列表页 / 详情页共用）
// 计数来自 GET /schools/{id}/statistics（服务端聚合，非前端本地累加）；
// 计数失败时不阻断删除流程，仅降级为"无警示"确认。
import { schoolApi } from '@/api/schools'
import { logger } from '@/utils/logger'

export interface SchoolLinkCounts {
  scholarship_count?: number | null
  project_count?: number | null
}

/**
 * 构造删除前关联警示文案。
 * 资助学生 / 助学兴教项目均为 0（或计数缺失）时返回空串，
 * 调用方据此跳过二次确认，保持无关联学校的删除体验不变。
 */
export function buildSchoolLinkWarning(counts?: SchoolLinkCounts | null): string {
  const scholarship = Number(counts?.scholarship_count ?? 0)
  const projects = Number(counts?.project_count ?? 0)
  const parts: string[] = []
  if (scholarship > 0) parts.push(`${scholarship} 名资助学生`)
  if (projects > 0) parts.push(`${projects} 个助学兴教项目`)
  if (!parts.length) return ''
  return `该校已关联${parts.join('、')}，删除前请确认无需继续维护这些关联数据。`
}

/** 拉取单校关联计数；失败返回 null（静默降级：不阻断删除） */
export async function fetchSchoolLinkCounts(
  schoolId: number | string
): Promise<SchoolLinkCounts | null> {
  try {
    const raw: any = await schoolApi.getSchoolStatistics(schoolId)
    return (raw?.data ?? raw ?? null) as SchoolLinkCounts | null
  } catch (error) {
    logger.warn('[schoolLinkWarning] 关联计数获取失败，已跳过删除警示', error)
    return null
  }
}
