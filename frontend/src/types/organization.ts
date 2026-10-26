/**
 * Organization Types
 * 组织单位相关类型定义
 */

// ============================================================================
// Organization Types
// ============================================================================

export interface Organization {
  id: number
  code: string
  name: string
  parent_id: number | null
  level: number
  path: string
  is_active: boolean
  description?: string
  contact_person?: string
  contact_phone?: string
  address?: string
  created_at: string
  created_by?: number
  updated_at?: string
}

export interface OrganizationTreeNode extends Organization {
  children: OrganizationTreeNode[]
}

export interface OrganizationCreate {
  name: string
  /**
   * 组织编码 = 6 位行政区划代码（GB/T 2260）—— **后端必填**。
   *
   * 2026-10-26 修复：此前这里写成 `code?: string`（可选），与后端
   * `OrganizationCreate.code`（`Field(...)`，min_length=max_length=6）不一致，
   * 导致「新增组织」对话框漏了该输入框也不会被类型检查发现，提交后只能吃 422
   * 「组织编码（行政区划代码）不能为空」。必填性必须与后端逐字段一致
   * （门禁 `scripts/check_stack_alignment.py` 轴 D 已对此做自动比对）。
   */
  code: string
  code_prefix?: string
  parent_id?: number | null
  description?: string
  contact_person?: string
  contact_phone?: string
  address?: string
  org_type?: string
  is_active?: boolean
}

export interface OrganizationUpdate {
  name?: string
  description?: string
  contact_person?: string
  contact_phone?: string
  address?: string
  is_active?: boolean
}

export interface OrganizationListResponse {
  total: number
  page: number
  page_size: number
  items: Organization[]
}

// ============================================================================
// Data Package Types
// ============================================================================

export type PackageStatus = 'pending' | 'validated' | 'imported' | 'failed' | 'cancelled'

export interface DataPackageManifest {
  version: string
  org_code: string
  org_name: string
  export_time: string
  data_types: string[]
  record_counts: Record<string, number>
  checksum?: string
  exported_by?: string
  description?: string
}

export interface DataPackage {
  id: number
  package_code: string
  org_id: number
  file_path?: string
  file_name?: string
  file_size?: number
  manifest_json?: string
  status: PackageStatus
  version: string
  checksum?: string
  data_types?: string
  record_count?: number
  error_message?: string
  created_at: string
  created_by?: number
  imported_at?: string
  imported_by?: number
}

export interface DataPackageExportRequest {
  org_id?: number
  data_types: string[]
  description?: string
}

export interface DataPackageExportResult {
  package_id: number
  package_code: string
  file_path: string
  file_name: string
  file_size: number
  manifest: DataPackageManifest
  download_url: string
}

export interface DataPackageValidationError {
  field: string
  message: string
  row?: number
  data_type?: string
}

export interface DataPackageValidationResult {
  is_valid: boolean
  errors: DataPackageValidationError[]
  warnings: string[]
  manifest?: DataPackageManifest
}

export interface DataPackagePreviewData {
  data_type: string
  total: number
  sample: Record<string, unknown>[]
  columns: string[]
}

export interface DataPackageImportResult {
  package_id: number
  package_code: string
  status: PackageStatus
  manifest?: DataPackageManifest
  preview: DataPackagePreviewData[]
  validation: DataPackageValidationResult
  records_imported?: number
  errors?: string[]
}

export interface DataPackageConfirmRequest {
  overwrite_existing?: boolean
  selected_types?: string[]
}

export interface DataPackageConfirmResult {
  success: boolean
  package_id: number
  imported_counts: Record<string, number>
  skipped_counts: Record<string, number>
  error_counts: Record<string, number>
  errors: DataPackageValidationError[]
  records_imported?: number
  message?: string
}

export interface DataPackageListResponse {
  total: number
  page: number
  page_size: number
  items: DataPackage[]
}

// ============================================================================
// Data Report Types
// ============================================================================

export type ReportStatus = 'draft' | 'submitted' | 'approved' | 'rejected' | 'cancelled'

export interface DataReport {
  id: number
  report_code: string
  package_id: number
  source_org_id: number
  target_org_id: number
  status: ReportStatus
  title?: string
  description?: string
  comment?: string
  rejection_reason?: string
  deadline?: string
  submitted_at?: string
  submitted_by?: number
  reviewed_at?: string
  reviewed_by?: number
  created_at: string
  created_by?: number
  // 关联字段（后端 JOIN 查询返回）
  source_org_name?: string
  target_org_name?: string
  package_code?: string
  data_types?: string | string[]
  record_count?: number
}

/**
 * 创建数据上报的请求体。
 *
 * 2026-10-26 修复（与 `OrganizationCreate.code` 同一类缺陷）：
 * 后端 `schemas/data_report.py:DataReportCreate` 的必填字段是
 * `title` / `report_type` / `package_id`，而这里此前
 * **漏了 `report_type`**、把后端必填的 `title` 写成了可选，
 * 反而是后端可选的 `target_org_id` 被写成了必填 —— 三者都与后端不一致。
 * 已按后端逐字段对齐（门禁 `scripts/check_stack_alignment.py` 轴 D 现在会自动比对）。
 */
export interface DataReportCreate {
  package_id: number
  title: string
  report_type: string
  target_org_id?: number
  description?: string
  deadline?: string
}

export type ReviewAction = 'approve' | 'reject'

export interface DataReportReview {
  action: ReviewAction
  comment?: string
  rejection_reason?: string
}

export interface DataReportStatistics {
  total: number
  draft: number
  submitted: number
  approved: number
  rejected: number
  pending: number
  cancelled: number
  overdue: number
  pending_review: number
  approval_rate: number
  by_source_org: Record<string, number>
  by_month: Record<string, number>
}

export interface SubordinateReportSummary {
  org_id: number
  org_name: string
  org_code: string
  total_reports: number
  pending_reports: number
  approved_reports: number
  rejected_reports: number
  latest_report_date?: string
  has_overdue: boolean
}

export interface SubordinateReportDashboard {
  total_subordinates: number
  reported_count: number
  not_reported_count: number
  pending_review_count: number
  overdue_count: number
  report_rate: number
  subordinates: SubordinateReportSummary[]
}

export interface DataReportListResponse {
  total: number
  page: number
  page_size: number
  items: DataReport[]
}

// ============================================================================
// Import/Export History Types
// ============================================================================

export type OperationType =
  | 'export'
  | 'import'
  | 'preview'
  | 'validate'
  | 'confirm'
  | 'cancel'
  | 'delete'
export type OperationResult = 'success' | 'failed' | 'partial'

export interface ImportExportHistory {
  id: number
  package_id?: number
  operation_type: OperationType
  org_id: number
  user_id: number
  operation_time: string
  result: OperationResult
  file_name?: string
  file_size?: number
  record_count?: number
  duration_ms?: number
  error_message?: string
}
