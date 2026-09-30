import { defineStore } from 'pinia'
import { ref } from 'vue'
import { get, post, put, del } from '@/api/request'
import { logger } from '@/utils/logger'

export const usePolicyStore = defineStore('policy', () => {
  const policyList = ref<any[]>([])
  const current = ref<any>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)
  const filters = ref<Record<string, any>>({})

  /** 提取可展示的错误文案（优先请求层已净化的 userMessage） */
  function _errMessage(e: any, fallback: string): string {
    return e?.userMessage || e?.response?.data?.message || e?.message || fallback
  }

  function setFilters(f: Record<string, any>) {
    filters.value = { ...filters.value, ...f }
  }

  async function fetchPolicies(params?: any) {
    loading.value = true
    error.value = null
    try {
      const res = await get<any>('/policies', { ...filters.value, ...params })
      if (res.code === 200 && res.data) {
        // 兼容三种响应形状：旧 bare data=[...] / 新信封 data={items,total} / 拦截器展开 items
        const items = Array.isArray(res.data) ? res.data : res.items || res.data?.items || []
        policyList.value = items
        total.value = res.total ?? items.length
      }
    } catch (e: any) {
      // 原实现 catch { /* silent */ }：失败既不留痕也不写 error，页面只能显示空列表
      // 且无任何解释（请求层已不弹全局提示，等于全线静默）。此处记录并可观测。
      error.value = _errMessage(e, '加载政策列表失败')
      logger.error('[policy] 加载政策列表失败', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchPolicy(id: number) {
    loading.value = true
    error.value = null
    try {
      const res = await get<{ code: number; data: any }>('/policies/' + id)
      if (res.code === 200) current.value = res.data
    } catch (e: any) {
      error.value = _errMessage(e, '加载政策详情失败')
      logger.error('[policy] 加载政策详情失败', e)
    } finally {
      loading.value = false
    }
  }

  async function createPolicy(data: any) {
    error.value = null
    try {
      const res = await post<any>('/policies', data)
      if (res.code === 200 && res.data) {
        policyList.value.unshift(res.data)
        total.value++
      }
      return res
    } catch (e: any) {
      // 写操作同样对齐读操作：记录错误并向上抛出，由调用方决定提示方式
      error.value = _errMessage(e, '创建政策失败')
      logger.error('[policy] 创建政策失败', e)
      throw e
    }
  }

  async function updatePolicy(id: number, data: any) {
    error.value = null
    try {
      const res = await put<any>('/policies/' + id, data)
      if (res.code === 200) {
        const idx = policyList.value.findIndex((p: any) => p.id === id)
        if (idx >= 0) policyList.value[idx] = { ...policyList.value[idx], ...data }
      }
      return res
    } catch (e: any) {
      error.value = _errMessage(e, '更新政策失败')
      logger.error('[policy] 更新政策失败', e)
      throw e
    }
  }

  async function deletePolicy(id: number) {
    error.value = null
    try {
      const res = await del<any>('/policies/' + id)
      if (res.code === 200) {
        // 与 funds store 同理：total 是服务端总数，只有确实移除当前页记录才递减
        const before = policyList.value.length
        policyList.value = policyList.value.filter((p: any) => p.id !== id)
        if (policyList.value.length < before) {
          total.value = Math.max(0, total.value - 1)
        }
      }
      return res
    } catch (e: any) {
      error.value = _errMessage(e, '删除政策失败')
      logger.error('[policy] 删除政策失败', e)
      throw e
    }
  }

  return {
    policyList,
    current,
    loading,
    error,
    total,
    filters,
    fetchPolicies,
    fetchPolicy,
    createPolicy,
    updatePolicy,
    deletePolicy,
    setFilters,
  }
})
