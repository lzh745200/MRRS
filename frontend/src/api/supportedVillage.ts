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

// ── 回收站：恢复 / 彻底删除 ──
export const restoreSupportedVillage = (id: number) => post(`/supported-villages/${id}/restore`, {})
export const previewPurgeSupportedVillage = (id: number) =>
  get(`/supported-villages/${id}/purge/preview`)
export const purgeSupportedVillage = (id: number, confirmPassword?: string) =>
  post(`/supported-villages/${id}/purge`, {
    confirm_password: confirmPassword || '',
  })

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

// ── Section key mapping（单一映射源）──
// 前端内部 prop key 用下划线（force_investment/party_building），
// 后端 _SECTION_MODEL 与 /yearly/{year}/{section} 路由用连字符（force-investment/party-building）。
// 映射统一在本文件的 API 函数内完成（保存/删除/导入），调用方直接传内部 key 即可，
// 不必各自记得映射 —— 历史上导入路径漏映射，导致这两个板块导入恒返回 400
// 「未知板块标识: force_investment」。resolveSectionApiKey 幂等，重复调用无害。
// 单单词 key（population、income、industry 等）两侧一致，映射原样返回。
// 附件路径（getSectionAttachments/uploadSectionAttachment/deleteSectionAttachment）
// 有意不映射：后端不按 _SECTION_MODEL 校验附件的 section，改动会使既有附件记录失配。
export const SECTION_KEY_OVERRIDE: Record<string, string> = {
  force_investment: 'force-investment',
  party_building: 'party-building',
}
/** 内部 section key → 后端 API section key（连字符）。未知 key 原样返回；幂等。 */
export function resolveSectionApiKey(sectionKey: string): string {
  return SECTION_KEY_OVERRIDE[sectionKey] ?? sectionKey
}

// ── Yearly data ──
export const getYearlyData = (villageId: number, year: number) =>
  get(`/supported-villages/${villageId}/yearly/${year}`)
export const copyYearData = (villageId: number, fromYear: number, toYear: number) =>
  post(`/supported-villages/${villageId}/yearly/copy`, { fromYear, toYear })
export const deleteYearlySection = (villageId: number, year: number, section: string) =>
  del(`/supported-villages/${villageId}/yearly/${year}/${resolveSectionApiKey(section)}`)

export const validateYearlyData = (villageId: number, year: number) =>
  post(`/supported-villages/${villageId}/yearly/${year}/validate`)

export const saveYearlySectionData = (
  villageId: number,
  year: number,
  section: string,
  data: any
) => post(`/supported-villages/${villageId}/yearly/${year}/${resolveSectionApiKey(section)}`, data)

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
  saveYearlySectionData(villageId, year, section, data)
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
    params: { year, section_key: resolveSectionApiKey(sectionKey) },
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

// ── 年度数据滚动填报（复制上年 + 批量沿用）──
// 逐字段差异元信息：status=copy（可沿用）/keep（本年度已有值保留）/blank（上年空缺需重填）
export interface YearlyPrefillField {
  field: string
  label: string
  previousValue: unknown
  currentValue: unknown
  hasPreviousValue: boolean
  hasCurrentValue: boolean
  status: 'copy' | 'keep' | 'blank'
}

export interface YearlyPrefillSection {
  key: string
  title: string
  hasPreviousData: boolean
  fields: YearlyPrefillField[]
  copyableCount: number
  keptCount: number
  blankCount: number
}

export interface YearlyPrefillResult {
  villageId: number
  year: number
  fromYear: number
  hasPreviousData: boolean
  sections: YearlyPrefillSection[]
  summary: {
    sectionCount: number
    availableSectionCount: number
    copyableFieldCount: number
    keptFieldCount: number
    blankFieldCount: number
  }
  message: string
}

export interface YearlyRollforwardSectionStats {
  created: boolean
  writtenFields: string[]
  keptFields: string[]
  memberCount: number
}

export interface YearlyRollforwardResult {
  villageId: number
  year: number
  fromYear: number
  mode: 'fill_empty' | 'overwrite'
  hasPreviousData: boolean
  appliedFields: number
  keptFields: number
  createdSections: string[]
  appliedSections: string[]
  skippedSections: Array<{ section: string; reason: string }>
  sections: Record<string, YearlyRollforwardSectionStats>
}

/** 获取「从上年复制」预填数据与逐字段差异元信息（fromYear 缺省时由后端取 year-1） */
export const getYearlyPrefill = (villageId: number, year: number, fromYear?: number) =>
  get(
    `/supported-villages/${villageId}/yearly/${year}/prefill`,
    fromYear != null ? { from_year: fromYear } : undefined
  )

/**
 * 批量沿用上年年度数据到指定年度（一次提交多个板块，后端事务原子）。
 * 默认 overwrite=false：只填空、不覆盖本年度已有非空值；true 为覆盖语义（需二次确认）。
 */
export const rollforwardYearlyData = (
  villageId: number,
  year: number,
  data: { sectionKeys: string[]; fromYear?: number; overwrite?: boolean }
) =>
  post(`/supported-villages/${villageId}/yearly/${year}/rollforward`, {
    section_keys: data.sectionKeys,
    from_year: data.fromYear,
    overwrite: data.overwrite ?? false,
  })

// ── w17-007 一村一档 PDF（档案册一键成册，blob 下载）──
/** 下载帮扶村档案册 PDF（封面 + 基本信息 + 年度数据 + 项目经费 + 附件清单） */
export const downloadVillageDossier = (villageId: number) =>
  downloadBlobAsFile(
    () => request.get(`/supported-villages/${villageId}/dossier.pdf`, { responseType: 'blob' }),
    { fallbackFileName: '帮扶村档案册.pdf' }
  )
