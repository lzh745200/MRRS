/**
 * 项目里程碑 API（T020 断链接线）
 * 后端：backend/app/api/v1/project_milestones.py（prefix=/projects）
 */
import { get, post, put, del } from '@/api/request'

export interface ProjectMilestone {
  id: number
  project_id: number
  name: string
  description?: string | null
  planned_date: string
  actual_date?: string | null
  responsible_person?: string | null
  status: 'pending' | 'in_progress' | 'completed' | 'overdue'
  sort_order?: number
  created_at?: string
  updated_at?: string
}

export interface MilestoneProgress {
  total: number
  completed: number
  progress_percent: number
}

const base = (projectId: number | string) => `/projects/${projectId}/milestones`

/** 里程碑列表：后端可能直接返回数组，也可能包一层 { data } / { items } */
export interface MilestoneListPayload {
  data?: ProjectMilestone[]
  items?: ProjectMilestone[]
}

export const listMilestones = (projectId: number | string) =>
  get<ProjectMilestone[] | MilestoneListPayload>(base(projectId))

/** 新增里程碑 */
export const createMilestone = (projectId: number | string, data: Partial<ProjectMilestone>) =>
  post(base(projectId), data)

/** 更新里程碑（含标记完成：status/actual_date） */
export const updateMilestone = (
  projectId: number | string,
  milestoneId: number,
  data: Partial<ProjectMilestone>
) => put(`${base(projectId)}/${milestoneId}`, data)

/** 删除里程碑 */
export const deleteMilestone = (projectId: number | string, milestoneId: number) =>
  del(`${base(projectId)}/${milestoneId}`)

/** 里程碑进度汇总（completed 比例）——后端在增删改后自动回写项目进度 */
export const milestoneProgress = async (projectId: number | string): Promise<MilestoneProgress> => {
  const items = await listMilestones(projectId)
  // 后端可能直接返回数组，也可能返回 {items:[...]} 信封；用显式形状兜底。
  // ⚠️ 信封分支必须先容忍 items 自身为 null/undefined（接口 204/空体/降级返回）：
  // 直接 .items 会抛 TypeError（v1.18.21 收口实测 2 个用例红），故用可选链。
  const envelope = items as { items?: ProjectMilestone[] } | null | undefined
  const arr: ProjectMilestone[] = Array.isArray(items) ? items : (envelope?.items ?? [])
  const total = arr.length
  const completed = arr.filter((m: ProjectMilestone) => m.status === 'completed').length
  return { total, completed, progress_percent: total ? Math.round((completed / total) * 100) : 0 }
}