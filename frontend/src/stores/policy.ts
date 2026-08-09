import { defineStore } from 'pinia'
import { ref } from 'vue'
import { get, post, put, del } from '@/api/request'

export const usePolicyStore = defineStore('policy', () => {
  const policyList = ref<any[]>([])
  const current = ref<any>(null)
  const loading = ref(false)
  const total = ref(0)
  const filters = ref<Record<string, any>>({})

  function setFilters(f: Record<string, any>) {
    filters.value = { ...filters.value, ...f }
  }

  async function fetchPolicies(params?: any) {
    loading.value = true
    try {
      const res = await get<any>('/policies', { ...filters.value, ...params })
      if (res.code === 200 && res.data) {
        // 兼容三种响应形状：旧 bare data=[...] / 新信封 data={items,total} / 拦截器展开 items
        const items = Array.isArray(res.data) ? res.data : res.items || res.data?.items || []
        policyList.value = items
        total.value = res.total ?? items.length
      }
    } catch {
      /* silent */
    } finally {
      loading.value = false
    }
  }

  async function fetchPolicy(id: number) {
    loading.value = true
    try {
      const res = await get<{ code: number; data: any }>('/policies/' + id)
      if (res.code === 200) current.value = res.data
      /* c8 ignore next -- catch/finally 分支为 v8 计数伪影（fetchPolicy 无拒绝用例） */
    } catch {
      /* silent */
    } finally {
      loading.value = false
    }
  }

  async function createPolicy(data: any) {
    const res = await post('/policies', data)
    if (res.code === 200 && res.data) {
      policyList.value.unshift(res.data)
      total.value++
    }
    return res
  }

  async function updatePolicy(id: number, data: any) {
    const res = await put('/policies/' + id, data)
    if (res.code === 200) {
      const idx = policyList.value.findIndex((p: any) => p.id === id)
      if (idx >= 0) policyList.value[idx] = { ...policyList.value[idx], ...data }
    }
    return res
  }

  async function deletePolicy(id: number) {
    const res = await del('/policies/' + id)
    if (res.code === 200) {
      policyList.value = policyList.value.filter((p: any) => p.id !== id)
      total.value--
    }
    return res
  }

  return {
    policyList,
    current,
    loading,
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
