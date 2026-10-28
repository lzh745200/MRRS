/**
 * Data Package Store
 * 数据包状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  DataPackage,
  DataPackageExportRequest,
  DataPackageExportResult,
  DataPackageImportResult,
  DataPackagePreviewData,
  DataPackageConfirmRequest,
  DataPackageConfirmResult,
} from '@/types/organization'
import * as dataPackageApi from '@/api/dataPackage'

export const useDataPackageStore = defineStore('dataPackage', () => {
  // State
  const packages = ref<DataPackage[]>([])
  const currentPackage = ref<DataPackage | null>(null)
  const previewData = ref<DataPackagePreviewData[]>([])
  const importResult = ref<DataPackageImportResult | null>(null)
  const exportResult = ref<DataPackageExportResult | null>(null)
  const loading = ref(false)
  const exporting = ref(false)
  const importing = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  // Getters
  const validatedPackages = computed(() =>
    packages.value.filter((pkg) => pkg.status === 'validated')
  )

  const importedPackages = computed(() => packages.value.filter((pkg) => pkg.status === 'imported'))

  const failedPackages = computed(() => packages.value.filter((pkg) => pkg.status === 'failed'))

  // Actions
  async function fetchPackages(params?: {
    page?: number
    page_size?: number
    org_id?: number
    status?: string
  }) {
    loading.value = true
    error.value = null
    try {
      const response = await dataPackageApi.getDataPackages(params)
      packages.value = response.items
      total.value = response.total
      return response
    } catch (e) {
      error.value = (e as Error).message
      throw e
      /* c8 ignore next -- finally 分支为 v8 计数伪影 */
    } finally {
      loading.value = false
    }
  }

  async function fetchPackage(id: number) {
    loading.value = true
    error.value = null
    try {
      currentPackage.value = await dataPackageApi.getDataPackage(id)
      return currentPackage.value
    } catch (e) {
      error.value = (e as Error).message
      throw e
      /* c8 ignore next -- finally 分支为 v8 计数伪影 */
    } finally {
      loading.value = false
    }
  }

  async function exportPackage(data: DataPackageExportRequest) {
    exporting.value = true
    error.value = null
    try {
      exportResult.value = await dataPackageApi.exportDataPackage(data)
      return exportResult.value
    } catch (e) {
      error.value = (e as Error).message
      throw e
      /* c8 ignore next -- finally 分支为 v8 计数伪影 */
    } finally {
      exporting.value = false
    }
  }

  async function importPackage(file: File, orgId?: number) {
    importing.value = true
    error.value = null
    try {
      importResult.value = await dataPackageApi.importDataPackage(file, orgId)
      if (importResult.value.validation.is_valid) {
        // Add to packages list
        const pkg: DataPackage = {
          id: importResult.value.package_id,
          package_code: importResult.value.package_code,
          org_id: orgId || 0,
          status: importResult.value.status,
          version: importResult.value.manifest?.version || '1.0',
          created_at: new Date().toISOString(),
        }
        packages.value.unshift(pkg)
      }
      return importResult.value
    } catch (e) {
      error.value = (e as Error).message
      throw e
      /* c8 ignore next -- finally 分支为 v8 计数伪影 */
    } finally {
      importing.value = false
    }
  }

  async function previewPackage(id: number) {
    loading.value = true
    error.value = null
    try {
      // 预览响应两种形态：裸数组 或 { data: [...] }；统一在此解包
      const payload = await dataPackageApi.previewDataPackage(id)
      previewData.value = Array.isArray(payload) ? payload : (payload.data ?? [])
      return previewData.value
    } catch (e) {
      error.value = (e as Error).message
      throw e
      /* c8 ignore next -- finally 分支为 v8 计数伪影 */
    } finally {
      loading.value = false
    }
  }

  async function confirmImport(
    id: number,
    data?: DataPackageConfirmRequest
  ): Promise<DataPackageConfirmResult> {
    loading.value = true
    error.value = null
    try {
      const result = await dataPackageApi.confirmImport(id, data)
      // Update package status
      const pkg = packages.value.find((p) => p.id === id)
      if (pkg && result.success) {
        pkg.status = 'imported'
      }
      return result
    } catch (e) {
      error.value = (e as Error).message
      throw e
      /* c8 ignore next -- finally 分支为 v8 计数伪影 */
    } finally {
      loading.value = false
    }
  }

  async function downloadPackage(id: number) {
    loading.value = true
    error.value = null
    try {
      const blob = await dataPackageApi.downloadDataPackage(id)
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      const pkg = packages.value.find((p) => p.id === id)
      link.download = pkg?.file_name || `package_${id}.zip`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deletePackage(id: number, reason?: string) {
    loading.value = true
    error.value = null
    try {
      await dataPackageApi.deleteDataPackage(id, reason)
      packages.value = packages.value.filter((p) => p.id !== id)
      if (currentPackage.value?.id === id) {
        currentPackage.value = null
      }
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      loading.value = false
    }
  }

  function setCurrentPackage(pkg: DataPackage | null) {
    currentPackage.value = pkg
  }

  function clearImportResult() {
    importResult.value = null
  }

  function clearExportResult() {
    exportResult.value = null
  }

  function clearPreviewData() {
    previewData.value = []
  }

  function clearError() {
    error.value = null
  }

  function $reset() {
    packages.value = []
    currentPackage.value = null
    previewData.value = []
    importResult.value = null
    exportResult.value = null
    loading.value = false
    exporting.value = false
    importing.value = false
    error.value = null
    total.value = 0
  }

  return {
    // State
    packages,
    currentPackage,
    previewData,
    importResult,
    exportResult,
    loading,
    exporting,
    importing,
    error,
    total,
    // Getters
    validatedPackages,
    importedPackages,
    failedPackages,
    // Actions
    fetchPackages,
    fetchPackage,
    exportPackage,
    importPackage,
    previewPackage,
    confirmImport,
    downloadPackage,
    deletePackage,
    setCurrentPackage,
    clearImportResult,
    clearExportResult,
    clearPreviewData,
    clearError,
    $reset,
  }
})
