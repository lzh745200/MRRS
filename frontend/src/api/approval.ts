/**
 * 审批管理API服务
 * Feature: production-deployment-readiness
 * Requirements: 3.2, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.3, 4.6
 */

import { get, post, put, del } from '@/api/request'

// ==================== 类型定义 ====================

/** 审批节点 */
export interface ApprovalNode {
  id?: number
  level?: number
  name: string
  approver_type: 'user' | 'role'
  approver_id?: number
  timeout_hours: number
}

/** 审批流程 */
export interface ApprovalWorkflow {
  id: number
  name: string
  entity_type: string
  description?: string
  is_active: boolean
  level_count: number
  nodes?: ApprovalNode[]
}

/** 审批任务 */
export interface ApprovalTask {
  id: number
  title?: string
  entity_type: string
  entity_id: number
  status: string
  current_level: number
  priority: number
  submitter_id?: number
  submitter_name?: string
  current_approver_id?: number
  reviewer_name?: string
  opinion?: string
  created_at: string
  completed_at?: string
  /** 变更数据摘要（待审批板块展示经费等业务信息） */
  change_data?: Record<string, any>
}

/** 审批记录 */
export interface ApprovalRecord {
  id: number
  task_id: number
  level: number
  approver_id: number
  approver_name?: string
  action: string
  opinion?: string
  created_at: string
}

/** 变更对比数据 */
export interface TaskDiff {
  task_id: number
  entity_type: string
  entity_id: number
  original_data: Record<string, any>
  change_data: Record<string, any>
  diff_fields: string[]
}

/** 批量审批结果 */
export interface BatchApproveResult {
  success: number[]
  failed: Array<{ id: number; reason: string }>
}

// ==================== 审批流程 API ====================

/**
 * 创建审批流程
 */
export async function createWorkflow(data: {
  name: string
  entity_type: string
  description?: string
  nodes: ApprovalNode[]
}): Promise<{ id: number; name: string; level_count: number }> {
  const response = await post<any>('/approval/workflows', data)
  return response
}

/**
 * 获取审批流程列表
 */
export async function getWorkflows(params?: {
  entity_type?: string
  is_active?: boolean
  skip?: number
  limit?: number
}): Promise<ApprovalWorkflow[]> {
  const response = await get<any>('/approval/workflows', params)
  return Array.isArray(response) ? response : response?.items || response?.data || []
}

/**
 * 获取审批流程详情
 */
export async function getWorkflow(workflowId: number): Promise<ApprovalWorkflow> {
  const response = await get<any>(`/approval/workflows/${workflowId}`)
  return response
}

/**
 * 更新审批流程
 */
export async function updateWorkflow(
  workflowId: number,
  data: {
    name?: string
    description?: string
    is_active?: boolean
    nodes?: ApprovalNode[]
  }
): Promise<{ id: number }> {
  const response = await put<any>(`/approval/workflows/${workflowId}`, data)
  return response
}

/**
 * 删除审批流程
 */
export async function deleteWorkflow(workflowId: number): Promise<void> {
  await del(`/approval/workflows/${workflowId}`)
}

// ==================== 审批任务 API ====================

/**
 * 提交审批
 */
export async function submitApproval(data: {
  entity_type: string
  entity_id: number
  change_data: Record<string, any>
  original_data?: Record<string, any>
  title?: string
  description?: string
  priority?: number
}): Promise<{ task_id: number; status: string; current_level: number }> {
  const response = await post<any>('/approval/submit', data)
  return response
}

/**
 * 审批通过
 */
export async function approveTask(
  taskId: number,
  opinion?: string
): Promise<{ task_id: number; status: string; current_level: number }> {
  const response = await post<any>(`/approval/tasks/${taskId}/approve`, {
    opinion,
  })
  return response
}

/**
 * 审批拒绝
 */
export async function rejectTask(
  taskId: number,
  opinion?: string
): Promise<{ task_id: number; status: string }> {
  const response = await post<any>(`/approval/tasks/${taskId}/reject`, {
    opinion,
  })
  return response
}

/**
 * 转交审批
 */
export async function transferTask(
  taskId: number,
  transferToId: number,
  reason?: string
): Promise<{ task_id: number; current_approver_id: number }> {
  const response = await post<any>(`/approval/tasks/${taskId}/transfer`, {
    transfer_to_id: transferToId,
    reason,
  })
  return response
}

/**
 * 撤回申请
 */
export async function withdrawTask(taskId: number): Promise<{ task_id: number; status: string }> {
  const response = await post<any>(`/approval/tasks/${taskId}/withdraw`, {})
  return response
}

/**
 * 获取所有审批任务（管理员总览）
 */
export async function getAllTasks(params?: {
  status?: string
  entity_type?: string
  skip?: number
  limit?: number
}): Promise<ApprovalTask[]> {
  const response = await get<any>('/approval/tasks/all', params)
  return Array.isArray(response) ? response : response?.items || response?.data || []
}

/**
 * 获取待审批任务列表（含总数，供分页）
 */
export async function getPendingTasksWithTotal(params?: {
  skip?: number
  limit?: number
}): Promise<{ items: ApprovalTask[]; total: number }> {
  const response = await get<any>('/approval/tasks/pending', params)
  const items = Array.isArray(response)
    ? response
    : response?.items ||
      (Array.isArray(response?.data) ? response.data : response?.data?.items) ||
      []
  return { items, total: Number(response?.total ?? items.length) || items.length }
}

/**
 * 获取待审批任务列表
 */
export async function getPendingTasks(params?: {
  skip?: number
  limit?: number
}): Promise<ApprovalTask[]> {
  const response = await get<any>('/approval/tasks/pending', params)
  return Array.isArray(response) ? response : response?.items || response?.data || []
}

/**
 * 获取我的申请列表（当前用户提交的审批任务，含 total）
 */
export async function getMyTasks(params?: {
  status?: string
  date_from?: string
  date_to?: string
  skip?: number
  limit?: number
}): Promise<{ items: ApprovalTask[]; total: number }> {
  const response = await get<any>('/approval/tasks/mine', params)
  const items = Array.isArray(response) ? response : response?.items || response?.data || []
  return { items, total: Number(response?.total ?? items.length) || items.length }
}

/**
 * 获取审批任务历史列表（管理员全部/普通用户仅自己提交的，含 total）
 */
export async function getTasksHistory(params?: {
  entity_type?: string
  status?: string
  completed?: boolean
  skip?: number
  limit?: number
}): Promise<{ items: ApprovalTask[]; total: number }> {
  const response = await get<any>('/approval/tasks/history', params)
  const items = Array.isArray(response) ? response : response?.items || response?.data || []
  return { items, total: Number(response?.total ?? items.length) || items.length }
}

/**
 * 批量审批
 */
export async function batchApprove(
  taskIds: number[],
  opinion?: string
): Promise<BatchApproveResult> {
  const response = await post<any>('/approval/tasks/batch', {
    task_ids: taskIds,
    opinion,
  })
  // 注意：envelope 顶层 success:true 会遮蔽内层 data.success（响应拦截器跳过同名键复制），
  // 必须从 response.data 读取真实结果数组。
  const payload = response?.data ?? response ?? {}
  const success = Array.isArray(payload.success) ? payload.success : []
  const failed = Array.isArray(payload.failed) ? payload.failed : []
  return { success, failed }
}

/**
 * 获取变更对比
 */
export async function getTaskDiff(taskId: number): Promise<TaskDiff> {
  const response = await get<any>(`/approval/tasks/${taskId}/diff`)
  return response
}

/**
 * 获取审批历史
 */
export async function getApprovalHistory(params?: {
  entity_type?: string
  entity_id?: number
  submitter_id?: number
  status?: string
  skip?: number
  limit?: number
}): Promise<ApprovalTask[]> {
  const response = await get<any>('/approval/history', params)
  return Array.isArray(response) ? response : response?.items || response?.data || []
}

// ==================== 单机版优化 API ====================

/**
 * 获取审批概览
 */
export async function getOverview(): Promise<{
  pending_count: number
  approved_count: number
  rejected_count: number
  total_count: number
}> {
  const response = await get<any>('/approval')
  return response
}

/**
 * 发送审批提醒
 */
export async function remindTask(taskId: number): Promise<{ message: string }> {
  const response = await post<any>(`/approval/tasks/${taskId}/remind`, {})
  return response
}

/**
 * 重新提交审批
 */
export async function resubmitTask(
  taskId: number,
  data?: Record<string, any>
): Promise<{ task_id: number; status: string }> {
  const response = await post<any>(`/approval/tasks/${taskId}/resubmit`, data || {})
  return response
}

/**
 * 单机版快速审批单个任务（跳过审批人校验）
 */
export async function autoApproveSingleTask(
  taskId: number,
  opinion?: string
): Promise<{ task_id: number; status: string }> {
  const response = await post<any>(`/approval/tasks/${taskId}/auto-approve`, {
    opinion,
  })
  return response
}

/**
 * 单机版一键审批所有待处理任务
 */
export async function autoApproveAll(
  opinion?: string
): Promise<{ success: number[]; failed: number[] }> {
  const response = await post<any>('/approval/tasks/auto-approve-all', {
    opinion,
  })
  return response
}

/**
 * 单机版提交并自动审批
 */
export async function submitAndAutoApprove(data: {
  entity_type: string
  entity_id: number
  change_data: Record<string, any>
  original_data?: Record<string, any>
  title?: string
  description?: string
  opinion?: string
}): Promise<{ task_id: number; status: string }> {
  const response = await post<any>('/approval/submit-auto', data)
  return response
}

// ==================== 工具函数 ====================

/**
 * 格式化审批状态
 */
type ElTagType = 'info' | 'primary' | 'success' | 'warning' | 'danger'

export function formatApprovalStatus(status: string): {
  text: string
  type: ElTagType
} {
  const statusMap: Record<string, { text: string; type: ElTagType }> = {
    pending: { text: '待审批', type: 'warning' },
    approved: { text: '已通过', type: 'success' },
    rejected: { text: '已拒绝', type: 'danger' },
    withdrawn: { text: '已撤回', type: 'info' },
  }
  return statusMap[status] || { text: status, type: 'info' }
}

/**
 * 格式化审批操作
 */
export function formatApprovalAction(action: string): string {
  const actionMap: Record<string, string> = {
    approve: '通过',
    reject: '拒绝',
    transfer: '转交',
  }
  return actionMap[action] || action
}

/**
 * 格式化实体类型
 */
export function formatEntityType(entityType: string): string {
  const typeMap: Record<string, string> = {
    supported_village: '帮扶村',
    project: '项目',
    fund: '经费',
    school: '学校',
  }
  return typeMap[entityType] || entityType
}
