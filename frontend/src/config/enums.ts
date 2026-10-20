// Fund type/status, project status, policy level/status, village tier, etc.
export const FUND_TYPES = {
  project: '项目经费',
  operation: '运营经费',
  education: '教育经费',
  infrastructure: '基建经费',
  emergency: '应急经费',
} as const
export const FUND_STATUS = {
  pending: '待审批',
  planned: '已计划',
  approved: '已审批',
  allocated: '已拨付',
  in_use: '使用中',
  completed: '已完成',
  audited: '已审计',
  rejected: '已驳回',
  cancelled: '已取消',
} as const
// 项目状态：后端 ProjectStatus（draft/pending/approved/in_progress/completed/cancelled）
// 与历史视图并存态（planning/suspended）合并为 8 态单一来源。
export const PROJECT_STATUS = {
  draft: '草稿',
  pending: '待审批',
  approved: '已审批',
  planning: '规划中',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
  suspended: '已暂停',
} as const
export const PROJECT_TYPES = {
  infrastructure: '基础设施',
  industry: '产业发展',
  education: '教育帮扶',
  medical: '医疗帮扶',
  ecology: '生态建设',
  party_building: '党建引领',
} as const
export const POLICY_LEVELS = {
  national: '国家级',
  provincial: '省级',
  municipal: '市级',
  county: '县级',
  department: '部门级',
} as const
export const POLICY_STATUS = {
  draft: '草稿',
  published: '已发布',
  expired: '已过期',
  revoked: '已撤销',
} as const
// 审批任务状态：与后端 models/approval.py ApprovalStatus 四态一致。
export const APPROVAL_STATUS = {
  pending: '待审批',
  approved: '已通过',
  rejected: '已驳回',
  withdrawn: '已撤回',
} as const
// 审批操作：与后端 models/approval.py ApprovalAction 一致（含转交）。
export const APPROVAL_ACTIONS = {
  approve: '通过',
  reject: '拒绝',
  transfer: '转交',
} as const
// 审批实体类型（后端下发 entity_type 全量；village 为历史视图沿用的别名）。
export const ENTITY_TYPES = {
  supported_village: '帮扶村',
  village: '帮扶村',
  project: '项目',
  fund: '经费',
  school: '学校',
  rural_work: '乡村工作',
  assessment: '考核复核',
  policy: '政策',
  other: '其他',
} as const
// 任务优先级（项目任务 / 乡村工作任务 / 待办共用）。
export const TASK_PRIORITY = {
  low: '低',
  normal: '普通',
  medium: '中',
  high: '高',
  urgent: '紧急',
} as const
// 任务状态（W10-029：乡村工作任务列表/导出/进度弹窗共用，消除视图私有 switch/map）。
export const TASK_STATUS = {
  pending: '待分配',
  in_progress: '进行中',
  completed: '已完成',
  delayed: '已延期',
  cancelled: '已取消',
} as const

// Helper functions
export function getFundTypeLabel(type: string) {
  return FUND_TYPES[type as keyof typeof FUND_TYPES] || type
}
export function getFundStatusLabel(status: string) {
  return FUND_STATUS[status as keyof typeof FUND_STATUS] || status
}
export function getProjectStatusLabel(status: string) {
  return PROJECT_STATUS[status as keyof typeof PROJECT_STATUS] || status
}
export function getProjectTypeLabel(type: string) {
  return PROJECT_TYPES[type as keyof typeof PROJECT_TYPES] || type
}
export function getApprovalStatusLabel(status: string) {
  return APPROVAL_STATUS[status as keyof typeof APPROVAL_STATUS] || status
}
export function getApprovalActionLabel(action: string) {
  return APPROVAL_ACTIONS[action as keyof typeof APPROVAL_ACTIONS] || action
}
export function getEntityTypeLabel(entityType: string) {
  return ENTITY_TYPES[entityType as keyof typeof ENTITY_TYPES] || entityType
}
export function getTaskPriorityLabel(priority: string) {
  return TASK_PRIORITY[priority as keyof typeof TASK_PRIORITY] || priority
}
export function getTaskStatusLabel(status: string) {
  return TASK_STATUS[status as keyof typeof TASK_STATUS] || status
}
