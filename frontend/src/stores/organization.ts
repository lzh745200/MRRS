import { defineStore } from 'pinia'
import { ref } from 'vue'
import { get, post, put, del, apiRequest } from '@/api/request'
import type { ApiResponse } from '@/types/api'

export const useOrganizationStore = defineStore('organization', () => {
  const orgs = ref<any[]>([])
  const current = ref<any>(null)
  const tree = ref<any[]>([])
  const loading = ref(false)
  const subordinateOrganizations = ref<any[]>([])

  async function fetchOrganizations(params?: any) {
    loading.value = true
    try {
      const res = await get<ApiResponse<any>>('/organizations', params)
      if (res.code === 200 && res.data) {
        orgs.value = Array.isArray(res.data) ? (res.data as any[]) : (res.items as any[]) || []
      }
    } catch {
      /* silent */
    } finally {
      loading.value = false
    }
  }

  async function fetchOrganization(id: number) {
    loading.value = true
    try {
      const res = await get<ApiResponse<any>>('/organizations/' + id)
      if (res.code === 200) current.value = res.data
    } catch {
      /* silent */
    } finally {
      loading.value = false
    }
  }

  async function fetchTree() {
    try {
      const res = await get<any>('/organizations/tree')
      // 后端直接返回数组——兼容数组直返与信封两种格式
      if (Array.isArray(res)) tree.value = res
      else if ((res?.code === 200 || res?.success !== false) && Array.isArray(res?.data))
        tree.value = res.data
    } catch {
      /* silent */
    }
  }

  async function createOrganization(data: any) {
    const res = await post('/organizations', data)
    if (res.code === 200 && res.data) {
      orgs.value.unshift(res.data)
      tree.value = []
    }
    return res
  }

  async function updateOrganization(id: number, data: any) {
    const res = await put('/organizations/' + id, data)
    if (res.code === 200) {
      const idx = orgs.value.findIndex((o: any) => o.id === id)
      if (idx >= 0) orgs.value[idx] = { ...orgs.value[idx], ...data }
      tree.value = []
    }
    return res
  }

  async function deleteOrganization(id: number) {
    const res = await del('/organizations/' + id)
    if (res.code === 200) {
      orgs.value = orgs.value.filter((o: any) => o.id !== id)
      tree.value = []
    }
    return res
  }

  async function fetchMyOrganization() {
    try {
      const res = await get<ApiResponse<any>>('/organizations/my')
      if (res.code === 200 && res.data) current.value = res.data
    } catch {
      /* silent — my org not configured */
    }
  }

  async function fetchSubordinateOrganizations() {
    try {
      const res = await apiRequest<any>({
        method: 'GET',
        url: '/organizations/subordinates',
        timeout: 10000,
      })
      // 后端直接返回数组——兼容数组直返与信封两种格式
      subordinateOrganizations.value = Array.isArray(res) ? res : res?.data || res?.items || []
    } catch {
      subordinateOrganizations.value = []
    }
  }

  return {
    orgs,
    current,
    tree,
    loading,
    subordinateOrganizations,
    fetchOrganizations,
    fetchOrganization,
    fetchMyOrganization,
    fetchTree,
    createOrganization,
    updateOrganization,
    deleteOrganization,
    fetchSubordinateOrganizations,
  }
})
