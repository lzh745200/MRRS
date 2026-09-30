import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { post, put, del, apiRequest } from '@/api/request'
import { unwrapList } from '@/utils/unwrapList'

export const useFundsStore = defineStore('funds', () => {
  const fundList = ref<any[]>([])
  const current = ref<any>(null)
  const loading = ref(false)
  const total = ref(0)

  /** 经费总额（万元） */
  const totalFunds = computed(() =>
    fundList.value.reduce((sum, f) => sum + (Number(f.amount) || 0), 0)
  )

  /** 已使用经费（万元） */
  const usedFunds = computed(() =>
    fundList.value.reduce((sum, f) => sum + (Number(f.used_amount) || 0), 0)
  )

  /** 剩余经费（万元） */
  const remainFunds = computed(() => totalFunds.value - usedFunds.value)

  async function fetchFunds(params?: any) {
    loading.value = true
    try {
      const res = await apiRequest<any>({
        method: 'GET',
        url: '/funds',
        params,
        timeout: 15000,
      })
      const { items, total: t } = unwrapList(res)
      fundList.value = items
      total.value = t
    } catch {
      fundList.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  async function createFund(data: any) {
    await post<any>('/funds', data)
    await fetchFunds()
  }

  async function updateFund(id: number, data: any) {
    await put<any>('/funds/' + id, data)
    const idx = fundList.value.findIndex((f: any) => f.id === id)
    if (idx >= 0) fundList.value[idx] = { ...fundList.value[idx], ...data }
  }

  async function deleteFund(id: number) {
    await del<any>('/funds/' + id)
    // total 是**服务端分页总数**（fetchFunds 中 unwrapList 的 total），不是标志位：
    // 原实现无条件 total.value-- ，当被删记录不在当前页时会与真实总数偏离，
    // 反复删除还会把计数减成负数。只有确实从当前页移除了记录才递减，且下限为 0。
    const before = fundList.value.length
    fundList.value = fundList.value.filter((f: any) => f.id !== id)
    if (fundList.value.length < before) {
      total.value = Math.max(0, total.value - 1)
    }
  }

  async function getSummary() {
    try {
      const res = await apiRequest<any>({
        method: 'GET',
        url: '/funds/statistics/overview',
        timeout: 10000,
      })
      return res?.data ?? res ?? {}
    } catch {
      return {
        total_amount: 0,
        total_allocated: 0,
        total_count: 0,
        by_status: {},
      }
    }
  }

  async function approveFund(id: number) {
    await post<any>('/funds/' + id + '/approve', {})
    const idx = fundList.value.findIndex((f: any) => f.id === id)
    if (idx >= 0) fundList.value[idx].status = 'approved'
  }

  return {
    fundList,
    current,
    loading,
    total,
    totalFunds,
    usedFunds,
    remainFunds,
    fetchFunds,
    createFund,
    updateFund,
    deleteFund,
    getSummary,
    approveFund,
  }
})
