import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiRequest } from '@/api/request'
import { unwrapList } from '@/utils/unwrapList'

export const useDataReportStore = defineStore('dataReport', () => {
  const reports = ref<any[]>([])
  const currentReport = ref<any>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 接收的数据上报
  const receivedReports = ref<any[]>([])
  const receivedTotal = ref(0)

  /** 获取接收到的上报列表 */
  async function fetchReceivedReports(params?: any) {
    loading.value = true
    error.value = null
    try {
      const res = await apiRequest<any>({
        method: 'GET',
        url: '/data-reports/received',
        params,
        timeout: 15000,
      })
      const { items, total: t } = unwrapList(res)
      receivedReports.value = items
      receivedTotal.value = t
    } catch (e: any) {
      /* c8 ignore next -- 防御性兜底：e?.message 为空时回退默认文案（测试仅覆盖有 message 的 Error） */
      error.value = e?.response?.data?.message || e?.message || '加载失败'
      receivedReports.value = []
      receivedTotal.value = 0
    } finally {
      loading.value = false
    }
  }

  /** 获取上报列表（通用） */
  async function fetchReports(params?: any) {
    loading.value = true
    error.value = null
    try {
      const res = await apiRequest<any>({
        method: 'GET',
        url: '/data-reports',
        params,
        timeout: 15000,
      })
      const { items } = unwrapList(res)
      reports.value = items
    } catch (e: any) {
      /* c8 ignore next -- 防御性兜底：e?.message 为空时回退默认文案（测试仅覆盖有 message 的 Error） */
      error.value = e?.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  /** 提取可展示的错误文案（与上方两个 fetch* 的既有口径一致） */
  function _errMessage(e: any, fallback: string): string {
    return e?.userMessage || e?.response?.data?.message || e?.message || fallback
  }

  /**
   * 预览上报数据。
   *
   * 读/写方法统一 try/catch：原实现直接 await，失败既不写 error 也不重置 loading，
   * 与 fetchReports/fetchReceivedReports 的处理标准不一致（页面只能靠自己的
   * catch 兜底，store 侧完全不可观测）。失败仍向上抛出，交给调用方决定提示方式。
   */
  async function previewReport(reportId: number) {
    loading.value = true
    error.value = null
    try {
      const res = await apiRequest<any>({
        method: 'GET',
        url: `/data-reports/${reportId}`,
        timeout: 10000,
      })
      return res
    } catch (e: any) {
      error.value = _errMessage(e, '加载上报详情失败')
      throw e
      /* c8 ignore next -- finally 分支为 v8 计数伪影（try 内 return 后 finally 的异常完成侧） */
    } finally {
      loading.value = false
    }
  }

  /** 接收/批准上报 */
  async function receiveReport(reportId: number) {
    loading.value = true
    error.value = null
    try {
      await apiRequest<any>({
        method: 'POST',
        url: `/data-reports/${reportId}/approve`,
        timeout: 15000,
      })
    } catch (e: any) {
      error.value = _errMessage(e, '接收上报失败')
      throw e
    } finally {
      loading.value = false
    }
  }

  /** 拒绝上报 */
  async function rejectReport(reportId: number, reason: string) {
    loading.value = true
    error.value = null
    try {
      await apiRequest<any>({
        method: 'POST',
        url: `/data-reports/${reportId}/review`,
        data: { decision: 'reject', comment: reason },
        timeout: 10000,
      })
    } catch (e: any) {
      error.value = _errMessage(e, '拒绝上报失败')
      throw e
    } finally {
      loading.value = false
    }
  }

  /** 下载上报数据包 */
  async function downloadReport(reportId: number) {
    loading.value = true
    error.value = null
    try {
      const res = await apiRequest<any>({
        method: 'GET',
        url: `/data-reports/${reportId}/package`,
        timeout: 10000,
      })
      return res
    } catch (e: any) {
      error.value = _errMessage(e, '下载上报数据包失败')
      throw e
      /* c8 ignore next -- finally 分支为 v8 计数伪影（try 内 return 后 finally 的异常完成侧） */
    } finally {
      loading.value = false
    }
  }

  /** 提交上报 */
  async function submitReport(data: any) {
    loading.value = true
    error.value = null
    try {
      await apiRequest<any>({
        method: 'POST',
        url: '/data-reports',
        data,
        timeout: 15000,
      })
    } catch (e: any) {
      error.value = _errMessage(e, '提交上报失败')
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    reports,
    currentReport,
    loading,
    error,
    receivedReports,
    receivedTotal,
    fetchReports,
    fetchReceivedReports,
    previewReport,
    receiveReport,
    rejectReport,
    downloadReport,
    submitReport,
  }
})
