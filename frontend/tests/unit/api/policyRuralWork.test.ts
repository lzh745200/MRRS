import { describe, it, expect, vi, beforeEach } from 'vitest'

// 被测模块（policy.ts / ruralWork.ts）从 '@/api/request' 导入命名辅助函数
// get/post/put/del（返回已自动解包的 body，不是 AxiosResponse）；policy.ts 另用
// default 导出（原始 axios 实例）做 blob 下载，并导入了 apiRequest。
// 因此 mock 必须提供全部被 import 的命名导出，否则抛
// "No "get" export is defined on the "@/api/request" mock"。
//
// 注意两套签名差异：
// - 命名 get 签名是 get(url, params)，params 直接作为第二参（不包 { params }）；
// - default.get 是 axios 实例签名 get(url, { params, ...config })。
// default.get 的返回值会被 downloadBlobAsFile 当 AxiosResponse 检查 'data' in result，
// 因此统一默认 resolve { data: {} }；导出测试里再改为 { data: Blob }。
const { mockGet, mockPost, mockPut, mockDelete, mockApiRequest, mockDownloadBlob } = vi.hoisted(
  () => ({
    mockGet: vi.fn().mockResolvedValue({ data: {} }),
    mockPost: vi.fn().mockResolvedValue({ data: {} }),
    mockPut: vi.fn().mockResolvedValue({ data: {} }),
    mockDelete: vi.fn().mockResolvedValue({ data: {} }),
    mockApiRequest: vi.fn().mockResolvedValue({ data: {} }),
    mockDownloadBlob: vi.fn(),
  })
)

vi.mock('@/api/request', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    put: (...args: any[]) => mockPut(...args),
    delete: (...args: any[]) => mockDelete(...args),
  },
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: (...args: any[]) => mockPut(...args),
  del: (...args: any[]) => mockDelete(...args),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  parseContentDisposition: (_headers: any, fallback: string) => fallback,
  downloadBlob: (...args: any[]) => mockDownloadBlob(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import {
  getLevelOptions,
  getPolicyTypes,
  searchPolicies,
  getPolicyCategories,
  getPolicyStats,
  getPolicies,
  getPolicy,
  createPolicy,
  updatePolicy,
  deletePolicy,
  importPolicies,
  exportPolicies,
  exportPoliciesPDF,
  exportPoliciesWPS,
  getCategoryLabel,
  getLevelLabel,
  getStatusLabel,
  getStatusColor,
  getStatusOptions,
  getCategoryTree,
  createCategory,
  updateCategory,
  deleteCategory,
  publishPolicy,
  archivePolicy,
  uploadPolicyFile,
  previewPolicyFile,
  downloadPolicyFile,
  addPolicyFavorite,
  removePolicyFavorite,
  getPolicyFavorites,
  getPolicyRelated,
  batchDeletePolicies,
} from '@/api/policy'

import {
  getRuralWorks,
  createRuralWork,
  updateRuralWork,
  deleteRuralWork,
  generateWorkReport,
  ruralWorkApi,
} from '@/api/ruralWork'

describe('api/policy', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getLevelOptions', () => {
    getLevelOptions()
    expect(mockGet).toHaveBeenCalledWith('/policies/options/levels')
  })
  it('getPolicyTypes', () => {
    getPolicyTypes()
    expect(mockGet).toHaveBeenCalledWith('/policies/options/levels')
  })
  it('searchPolicies GET /policies/search with q', () => {
    searchPolicies('农业')
    expect(mockGet).toHaveBeenCalledWith('/policies/search', { q: '农业' })
  })
  it('getPolicyCategories', () => {
    getPolicyCategories()
    expect(mockGet).toHaveBeenCalledWith('/policies/categories')
  })
  it('getPolicyStats', () => {
    getPolicyStats()
    expect(mockGet).toHaveBeenCalledWith('/policies/statistics')
  })
  it('getPolicies GET /policies', () => {
    getPolicies({ page: 1 })
    expect(mockGet).toHaveBeenCalledWith('/policies', { page: 1 })
  })
  it('getPolicy GET /policies/{id}', () => {
    getPolicy(1)
    expect(mockGet).toHaveBeenCalledWith('/policies/1')
  })
  it('createPolicy POST /policies', () => {
    createPolicy({ title: 'X' })
    expect(mockPost).toHaveBeenCalledWith('/policies', { title: 'X' })
  })
  it('updatePolicy PUT /policies/{id}', () => {
    updatePolicy(1, { title: 'Y' })
    expect(mockPut).toHaveBeenCalledWith('/policies/1', { title: 'Y' })
  })
  it('deletePolicy DELETE /policies/{id}', () => {
    deletePolicy(1)
    expect(mockDelete).toHaveBeenCalledWith('/policies/1')
  })

  it('importPolicies POST FormData', () => {
    const file = new File(['x'], 'a.xlsx')
    importPolicies(file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/policies/import')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
  })

  describe('export 系列触发下载', () => {
    beforeEach(() => {
      vi.clearAllMocks()
      // downloadBlobAsFile 会把 default.get 的返回值当 AxiosResponse 解包 .data；
      // downloadBlob 已被 mock，不会触发真实 DOM 下载。
      mockGet.mockResolvedValue({ data: new Blob(['x']) })
    })

    it('exportPolicies -> xlsx', async () => {
      await exportPolicies({ page: 1 })
      expect(mockGet).toHaveBeenCalledWith('/policies/export/excel', {
        params: { page: 1 },
        responseType: 'blob',
      })
    })
    it('exportPoliciesPDF -> pdf', async () => {
      await exportPoliciesPDF()
      expect(mockGet).toHaveBeenCalledWith('/policies/export/pdf', {
        params: undefined,
        responseType: 'blob',
      })
    })
    it('exportPoliciesWPS -> wps', async () => {
      await exportPoliciesWPS()
      expect(mockGet).toHaveBeenCalledWith('/policies/export/wps', {
        params: undefined,
        responseType: 'blob',
      })
    })
    // downloadImportTemplate removed — consolidated to downloadImportTemplateAndSave in @/api/import
  })

  describe('label helpers', () => {
    it('getCategoryLabel 未知 cat 回退', () => {
      expect(getCategoryLabel('xxx')).toBe('xxx')
    })
    it('getLevelLabel 未知 level 回退', () => {
      expect(getLevelLabel('xxx')).toBe('xxx')
    })
    it('getStatusLabel 未知 status 回退', () => {
      expect(getStatusLabel('xxx')).toBe('xxx')
    })
    it('getStatusColor 未知 status 默认 info', () => {
      expect(getStatusColor('xxx')).toBe('info')
    })
  })
})

describe('api/ruralWork', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getRuralWorks GET', () => {
    getRuralWorks({ status: 'pending' })
    expect(mockGet).toHaveBeenCalledWith('/rural-works', { status: 'pending' })
  })
  it('createRuralWork POST', () => {
    createRuralWork({ title: 'W' })
    expect(mockPost).toHaveBeenCalledWith('/rural-works', { title: 'W' })
  })
  it('updateRuralWork PUT', () => {
    updateRuralWork(1, { title: 'W2' })
    expect(mockPut).toHaveBeenCalledWith('/rural-works/1', { title: 'W2' })
  })
  it('deleteRuralWork DELETE', () => {
    deleteRuralWork(1)
    expect(mockDelete).toHaveBeenCalledWith('/rural-works/1')
  })
  it('generateWorkReport GET /rural-works/report/generate', () => {
    generateWorkReport({ year: 2026 })
    expect(mockGet).toHaveBeenCalledWith('/rural-works/report/generate', { year: 2026 })
  })

  it('ruralWorkApi.list / get / create / update / delete / generateWorkReport 转发', () => {
    ruralWorkApi.list({ p: 1 })
    ruralWorkApi.get(1)
    ruralWorkApi.create({ x: 1 })
    ruralWorkApi.update(1, { y: 2 })
    ruralWorkApi.delete(1)
    ruralWorkApi.generateWorkReport({ q: 9 })
    expect(mockGet).toHaveBeenCalledTimes(3)
    expect(mockPost).toHaveBeenCalledTimes(1)
    expect(mockPut).toHaveBeenCalledTimes(1)
    expect(mockDelete).toHaveBeenCalledTimes(1)
  })

  it('ruralWorkApi.getById GET /rural-works/{id}', () => {
    ruralWorkApi.getById(2)
    expect(mockGet).toHaveBeenCalledWith('/rural-works/2')
  })

  it('ruralWorkApi.getStatistics GET /rural-works/statistics/summary', () => {
    ruralWorkApi.getStatistics()
    expect(mockGet).toHaveBeenCalledWith('/rural-works/statistics/summary')
  })

  it('ruralWorkApi.getVillagesForSelect GET /rural-works/villages', () => {
    ruralWorkApi.getVillagesForSelect()
    expect(mockGet).toHaveBeenCalledWith('/rural-works/villages')
  })

  it('ruralWorkApi.getAvailableYears GET /rural-works/years', () => {
    ruralWorkApi.getAvailableYears()
    expect(mockGet).toHaveBeenCalledWith('/rural-works/years')
  })

  it('ruralWorkApi.batchDelete POST /rural-works/batch-delete', () => {
    ruralWorkApi.batchDelete([1, 2])
    expect(mockPost).toHaveBeenCalledWith('/rural-works/batch-delete', { ids: [1, 2] })
  })
})

describe('api/policy 补充（此前未覆盖函数）', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getStatusOptions GET /policies/options/statuses', () => {
    getStatusOptions()
    expect(mockGet).toHaveBeenCalledWith('/policies/options/statuses')
  })

  it('getCategoryTree GET /policies/categories/tree', () => {
    getCategoryTree()
    expect(mockGet).toHaveBeenCalledWith('/policies/categories/tree')
  })

  it('createCategory POST /policies/categories', () => {
    createCategory({ name: '农业' })
    expect(mockPost).toHaveBeenCalledWith('/policies/categories', { name: '农业' })
  })

  it('updateCategory PUT /policies/categories/{id}', () => {
    updateCategory(2, { name: '教育' })
    expect(mockPut).toHaveBeenCalledWith('/policies/categories/2', { name: '教育' })
  })

  it('deleteCategory DELETE /policies/categories/{id}', () => {
    deleteCategory(2)
    expect(mockDelete).toHaveBeenCalledWith('/policies/categories/2')
  })

  it('publishPolicy POST /policies/{id}/publish', () => {
    publishPolicy(3)
    expect(mockPost).toHaveBeenCalledWith('/policies/3/publish')
  })

  it('archivePolicy POST /policies/{id}/archive', () => {
    archivePolicy(3)
    expect(mockPost).toHaveBeenCalledWith('/policies/3/archive')
  })

  it('uploadPolicyFile POST FormData', () => {
    const file = new File(['x'], 'p.pdf')
    uploadPolicyFile(4, file)
    const [url, fd, config] = mockPost.mock.calls[0]
    expect(url).toBe('/policies/4/upload')
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('file')).toBe(file)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('previewPolicyFile apiRequest blob（v1.8.0：预览按 blob 流处理）', () => {
    previewPolicyFile(4)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/policies/4/preview',
      responseType: 'blob',
    })
  })

  it('downloadPolicyFile apiRequest blob', () => {
    downloadPolicyFile(4)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/policies/4/download',
      responseType: 'blob',
    })
  })

  it('addPolicyFavorite POST /policies/{id}/favorite', () => {
    addPolicyFavorite(5)
    expect(mockPost).toHaveBeenCalledWith('/policies/5/favorite')
  })

  it('removePolicyFavorite DELETE /policies/{id}/favorite', () => {
    removePolicyFavorite(5)
    expect(mockDelete).toHaveBeenCalledWith('/policies/5/favorite')
  })

  it('getPolicyFavorites GET /policies/user/{userId}/favorites', () => {
    getPolicyFavorites(7)
    expect(mockGet).toHaveBeenCalledWith('/policies/user/7/favorites')
  })

  it('getPolicyRelated GET /policies/{id}/related', () => {
    getPolicyRelated(5)
    expect(mockGet).toHaveBeenCalledWith('/policies/5/related')
  })

  it('batchDeletePolicies POST /policies/batch-delete', () => {
    batchDeletePolicies([1, 2, 3])
    expect(mockPost).toHaveBeenCalledWith('/policies/batch-delete', { ids: [1, 2, 3] })
  })
})
