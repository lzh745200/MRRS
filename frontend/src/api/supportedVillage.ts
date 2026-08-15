import request, { get, post, put, del, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

// ── List / detail ──
export const getSupportedVillages = (params?: any) => get('/supported-villages', params)
export const getSupportedVillage = (id: number) => get('/supported-villages/' + id)

// ── CRUD ──
export const createSupportedVillage = (data: any) => post('/supported-villages', data)
export const updateSupportedVillage = (id: number, data: any) =>
  put('/supported-villages/' + id, data)
export const deleteSupportedVillage = (id: number) => del('/supported-villages/' + id)
export const batchDeleteSupportedVillages = (ids: number[], confirmPassword?: string) =>
  post('/supported-villages/batch-delete', { ids, confirm_password: confirmPassword || '' })

// ── Import / export ──
export const importSupportedVillages = (file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return apiRequest({
    method: 'POST',
    url: '/supported-villages/import',
    data: fd,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
// blob 响应：触发浏览器下载
export const exportSupportedVillages = (params?: any) =>
  downloadBlobAsFile(
    () => request.get('/supported-villages/export', { params, responseType: 'blob' }),
    { fallbackFileName: '帮扶村数据导出.xlsx' }
  )
export const downloadImportTemplate = () =>
  downloadBlobAsFile(
    () =>
      request.get('/import/template', {
        params: { entity_type: 'supported_village' },
        responseType: 'blob',
      }),
    { fallbackFileName: '帮扶村导入模板.xlsx' }
  )
export const downloadTemplate = downloadImportTemplate

// ── Filter options ──
export const getFilterOptions = () => get('/supported-villages/filter-options')
export const getChangeHistory = (villageId: number) =>
  get(`/supported-villages/${villageId}/change-history`)

// ── Yearly data ──
export const getYearlyData = (villageId: number, year: number) =>
  get(`/supported-villages/${villageId}/yearly/${year}`)
export const copyYearData = (villageId: number, fromYear: number, toYear: number) =>
  post(`/supported-villages/${villageId}/yearly/copy`, { fromYear, toYear })
export const validateYearlyData = (villageId: number, year: number) =>
  post(`/supported-villages/${villageId}/yearly/${year}/validate`)

export const saveYearlySectionData = (
  villageId: number,
  year: number,
  section: string,
  data: any
) => post(`/supported-villages/${villageId}/yearly/${year}/${section}`, data)

// Backward compat aliases
export const saveIncomeData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'income', d)
export const saveIndustryData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'industry', d)
export const saveInfrastructureData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'infrastructure', d)
export const saveEducationData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'education', d)
export const saveForceInvestmentData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'force-investment', d)
export const savePartyBuildingData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'party-building', d)
export const saveMedicalData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'medical', d)
export const saveConsumptionData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'consumption', d)
export const saveEmploymentData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'employment', d)
export const savePopulationData = (v: number, y: number, d: any) =>
  saveYearlySectionData(v, y, 'population', d)

// ── Sections ──
export const getSectionAttachments = async (villageId: number, section: string) => {
  const res: any = await get(`/supported-villages/${villageId}/sections/${section}/attachments`)
  return res.items || res.data || []
}
export const saveSectionData = (villageId: number, year: number, section: string, data: any) =>
  post(`/supported-villages/${villageId}/yearly/${year}/${section}`, data)
export const saveCommitteeData = (villageId: number, data: any) =>
  post(`/supported-villages/${villageId}/committee`, data)
export const uploadSectionAttachment = (villageId: number, section: string, file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return apiRequest({
    method: 'POST',
    url: `/supported-villages/${villageId}/sections/${section}/attachments`,
    data: fd,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export const deleteSectionAttachment = (villageId: number, section: string, attachmentId: number) =>
  del(`/supported-villages/${villageId}/sections/${section}/attachments/${attachmentId}`)

// ── Transition funding ──
export const getTransitionFunding = (villageId: number) =>
  get(`/supported-villages/${villageId}/transition-funding`)
export const saveTransitionFunding = (villageId: number, data: any) =>
  post(`/supported-villages/${villageId}/transition-funding`, data)

// ── Import (yearly overview) ──
export const importSectionData = (
  villageId: number,
  year: number,
  sectionKey: string,
  file: File
) => {
  const fd = new FormData()
  fd.append('file', file)
  return apiRequest({
    method: 'POST',
    url: `/supported-villages/${villageId}/sections/import`,
    params: { year, section_key: sectionKey },
    data: fd,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export const downloadAllTemplates = (year?: number) =>
  downloadBlobAsFile(
    () =>
      request.get('/supported-villages/templates/all', { params: { year }, responseType: 'blob' }),
    { fallbackFileName: '全部板块模板.xlsx' }
  )
export const importAllSectionsData = (villageId: number, year: number, file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return apiRequest({
    method: 'POST',
    url: `/supported-villages/${villageId}/sections/import-all`,
    params: { year },
    data: fd,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ── Export modules / formats / preview ──
export const getExportModules = () => get('/supported-villages/export/modules')
export const getExportFormats = () => get('/supported-villages/export/formats')
export const previewExport = (params?: any) => get('/supported-villages/export/preview', params)
