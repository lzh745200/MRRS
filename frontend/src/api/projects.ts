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
  created_at?: string
  updated_at?: string
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
  list: (params?: any) => get('/projects', params),
  get: (id: number) => get('/projects/' + id),
  create: (data: any) => post('/projects', data),
  update: (id: number | string, data: any) => put('/projects/' + id, data),
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
  listFiles: (id: number | string) => get('/projects/' + id + '/files'),
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
export const previewPurgeProject = (id: number) => get(`/projects/${id}/purge/preview`)
export const purgeProject = (id: number, confirmPassword?: string) =>
  post(`/projects/${id}/purge`, { confirm_password: confirmPassword || '' })
