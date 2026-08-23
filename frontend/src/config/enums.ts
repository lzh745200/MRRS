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
export const PROJECT_STATUS = {
  planning: '规划中',
  in_progress: '进行中',
  completed: '已完成',
  suspended: '已暂停',
  cancelled: '已取消',
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
