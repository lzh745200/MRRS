import request, { get, post, put, del, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

export const schoolsApi = {
  // ========== 基础 CRUD ==========
  list: (p?: any) => get('/schools', p),
  get: (id: number) => get('/schools/' + id),
  create: (d: any) => post('/schools', d),
  update: (id: number, d: any) => put('/schools/' + id, d),
  delete: (id: number) => del('/schools/' + id),

  // ========== 统计与选项 ==========
  getStatistics: () => get('/schools/statistics'),
  // 单校成效统计：详情页成效卡 + 删除前关联计数共用（服务端聚合）
  getSchoolStatistics: (id: number | string) => get(`/schools/${id}/statistics`),
  getTypeOptions: () => get('/schools/options/types'),
  getStatusOptions: () => get('/schools/options/statuses'),

  // ========== 导入导出 ==========
  importExcel: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return post('/schools/import/excel', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  exportExcel: (params?: any) =>
    downloadBlobAsFile(
      () => request.get('/schools/export/excel', { params, responseType: 'blob' }),
      { fallbackFileName: '学校数据导出.xlsx' }
    ),
  // downloadImportTemplate removed — use downloadImportTemplateAndSave from @/api/import

  // ========== 学校帮扶项目 ==========
  listProjects: (schoolId: number | string) => get(`/schools/${schoolId}/projects`),
  createProject: (schoolId: number | string, data: any) =>
    post(`/schools/${schoolId}/projects`, data),
  updateProject: (schoolId: number | string, projectId: number | string, data: any) =>
    put(`/schools/${schoolId}/projects/${projectId}`, data),
  deleteProject: (schoolId: number | string, projectId: number | string) =>
    del(`/schools/${schoolId}/projects/${projectId}`),

  // ========== 资助学生 ==========
  listScholarshipStudents: (schoolId: number | string, year?: number) =>
    get(`/schools/${schoolId}/scholarship-students`, year !== undefined ? { year } : undefined),
  createScholarshipStudent: (schoolId: number | string, data: any) =>
    post(`/schools/${schoolId}/scholarship-students`, data),
  updateScholarshipStudent: (schoolId: number | string, studentId: number | string, data: any) =>
    put(`/schools/${schoolId}/scholarship-students/${studentId}`, data),
  deleteScholarshipStudent: (schoolId: number | string, studentId: number | string) =>
    del(`/schools/${schoolId}/scholarship-students/${studentId}`),
  importScholarshipStudents: (schoolId: number | string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return post(`/schools/${schoolId}/scholarship-students/import`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // ========== 附件管理 ==========
  listAttachments: (schoolId: number | string) => get(`/schools/${schoolId}/attachments`),
  uploadAttachment: (schoolId: number | string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return post(`/schools/${schoolId}/attachments`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteAttachment: (attachmentId: number | string) => del(`/schools/attachments/${attachmentId}`),
  downloadAttachment: (attachmentId: number | string) =>
    apiRequest({
      method: 'GET',
      url: `/schools/attachments/${attachmentId}/download`,
      responseType: 'blob',
    }),
}

export const schoolApi = schoolsApi
