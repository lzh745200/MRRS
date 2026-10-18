import { get, post, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

// Types
export interface SyncLog {
  id: string
  action: string
  status: string
  message?: string
  created_at: string
  task_id?: string
}

export interface ImportDataResponse {
  success: boolean
  count: number
  message?: string
  errors?: string[]
}

export interface ExportEncryptedParams {
  password: string
  modules?: string[]
  export_type?: 'full' | 'selective'
  since?: string
}

export interface ConflictDetail {
  id: string
  entity_type: string
  local_data: Record<string, any>
  remote_data: Record<string, any>
  resolved?: boolean
}

// Named functions
export const importData = (file: File, strategy: string = 'overwrite') => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('strategy', strategy)
  return post('/data-sync/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const importEncryptedData = (file: File, password: string) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('password', password)
  return post('/data-sync/import-encrypted', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const exportData = (params: any) => post('/data-sync/export', params)

export const exportEncryptedData = (params: ExportEncryptedParams) =>
  post('/data-sync/export-encrypted', params)

export const downloadExportPackage = (packageId: string) =>
  downloadBlobAsFile(
    () =>
      apiRequest<Blob>({
        method: 'GET',
        url: `/data-sync/export/download/${packageId}`,
        responseType: 'blob',
      }),
    { fallbackFileName: packageId.includes('.') ? packageId : `${packageId}.rrs` }
  )

export const getSyncLogs = (params?: any) => get('/data-sync/logs', params)

export const getConflicts = (syncLogId: number) => get(`/data-sync/conflicts/${syncLogId}`)

export const resolveConflict = (params: {
  conflict_id: number
  resolution: string
  merged_data?: Record<string, any>
}) => post('/data-sync/resolve-conflict', params)

// Backward-compatible object form
export const dataSyncApi = {
  importData,
  importEncryptedData,
  exportData,
  exportEncryptedData,
  downloadExportPackage,
  getSyncLogs,
  getConflicts,
  resolveConflict,
}
