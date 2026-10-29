import request, { get, post, put, del, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

// Types
export interface Project {
  id: number
  name: string
  status: string
  village_id?: number
  description?: string
  budget?: number
  start_date?: string
  end_date?: string
  /** 完成进度（甘特图用） */
  progress?: number
  created_at?: string
  updated_at?: string
}

/** 创建/更新后的回包（兼容裸 {id} 与信封 {data:{id}}） */
export interface ProjectCreated {
  id?: number
  data?: { id?: number }
}

/**
 * 项目附件项：字段名以**后端实际返回**为准（filename/file_size/file_path/created_at）。
 * 起初按 name/size/url 猜了一版，tsc 立刻在模板里报错 —— 正好证明这层类型有用。
 */
export interface ProjectFileItem {
  id?: number | string
  filename?: string
  file_path?: string
  file_size?: number
  file_type?: string
  category?: string
  created_at?: string
  url?: string
  [key: string]: unknown
}

/** 附件列表回包：{grouped:{cat:[...]}} 为主，兼容裸 files 数组 */
export interface ProjectFilesPayload {
  grouped?: Record<string, ProjectFileItem[]>
  items?: ProjectFileItem[]
  files?: ProjectFileItem[]
}

/** 列表响应：裸分页 {items,total} 与信封 {data:{items,total}} 双形态 */
export interface ProjectListPayload {
  items?: Project[]
  total?: number
  data?: { items?: Project[]; total?: number }
}

/** 彻底删除前的级联引用统计 */
export interface ProjectPurgePreview {
  total_references?: number
  details?: Record<string, number>
  data?: ProjectPurgePreview
}

export interface ProjectPurgeResult {
  deleted_records?: number
  data?: { deleted_records?: number }
}

export interface CreateProjectRequest {
  name: string
  village_id: number
  status?: string
  description?: string
  budget?: number
  start_date?: string
  end_date?: string
}

// Core API
export const projectsApi = {
  // ========== 基础 CRUD ==========
  list: (params?: Record<string, unknown>) => get<ProjectListPayload>('/projects', params),
  get: (id: number) => get('/projects/' + id),
  create: (data: Record<string, unknown>) => post<ProjectCreated>('/projects', data),
  update: (id: number | string, data: Record<string, unknown>) =>
    put<ProjectCreated>('/projects/' + id, data),
  delete: (id: number) => del('/projects/' + id),
  // 回收站：恢复 / 彻底删除
  restore: (id: number) => post(`/projects/${id}/restore`, {}),
  purgePreview: (id: number) => get(`/projects/${id}/purge/preview`),
  purge: (id: number, confirmPassword?: string) =>
    post(`/projects/${id}/purge`, { confirm_password: confirmPassword || '' }),
  getById: (id: number | string) => get('/projects/' + id),
  getStats: () => get('/projects/stats'),
  exportList: (params?: any) =>
    downloadBlobAsFile(() => request.get('/projects/export', { params, responseType: 'blob' }), {
      fallbackFileName: '项目数据导出.xlsx',
    }),
  importData: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return post('/projects/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // ========== 项目文件 ==========
  uploadFiles: (id: number | string, category: string, files: File[]) => {
    const formData = new FormData()
    formData.append('category', category)
    files.forEach((f) => formData.append('files', f))
    return post('/projects/' + id + '/files', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listFiles: (id: number | string) => get<ProjectFilesPayload>('/projects/' + id + '/files'),
  getFileDownloadUrl: (projectId: number | string, fileId: number) =>
    `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/projects/${projectId}/files/${fileId}/download`,
  deleteFile: (projectId: number | string, fileId: number) =>
    del('/projects/' + projectId + '/files/' + fileId),
  previewFile: (projectId: number | string, fileId: number) =>
    apiRequest({
      method: 'GET',
      url: `/projects/${projectId}/files/${fileId}/preview`,
      responseType: 'blob',
    }) as Promise<Blob>,

  // ========== 项目变更历史 ==========
  getChangeHistory: (projectId: number) => get(`/projects/${projectId}/history/changes`),

  // ========== 项目经费关联 ==========
  getFunds: (projectId: number) => get(`/projects/${projectId}/funds`),
  addFund: (projectId: number, data: any) => post(`/projects/${projectId}/funds`, data),

  // ========== 项目任务 ==========
  getTasks: (projectId: number) => get(`/projects/${projectId}/tasks`),
  createTask: (projectId: number, data: any) => post(`/projects/${projectId}/tasks`, data),
  updateTask: (projectId: number, taskId: number, data: any) =>
    put(`/projects/${projectId}/tasks/${taskId}`, data),
  deleteTask: (projectId: number, taskId: number) => del(`/projects/${projectId}/tasks/${taskId}`),
}

// Alias for views that use the singular form
export const projectApi = projectsApi
// 回收站：恢复 / 彻底删除（具名导出，供列表页直接使用）
export const restoreProject = (id: number) => post(`/projects/${id}/restore`, {})
export const previewPurgeProject = (id: number) =>
  get<ProjectPurgePreview>(`/projects/${id}/purge/preview`)
export const purgeProject = (id: number, confirmPassword?: string) =>
  post<ProjectPurgeResult>(`/projects/${id}/purge`, { confirm_password: confirmPassword || '' })
