import { defineStore } from 'pinia'
import { ref } from 'vue'
import { get, post, put, del } from '@/api/request'
import type { ApiResponse } from '@/types/api'
import { AuthStorage } from '@/utils/authStorage'

export interface User {
  id: number
  username: string
  nickname?: string
  email?: string
  phone?: string
  role?: string
  status?: string
  avatar?: string
  is_active?: boolean
  [key: string]: any
}

export const useUserStore = defineStore('user', () => {
  const userList = ref<User[]>([])
  // 初始化时从 AuthStorage 恢复 currentUser（防止页面刷新后丢失）
  const _initialUser = AuthStorage.getUser()
  const currentUser = ref<User | null>(_initialUser ? (_initialUser as unknown as User) : null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  async function fetchUsers(params?: Record<string, any>) {
    loading.value = true
    error.value = null
    try {
      const res = await get<any>('/users', params)
      // 后端 GET /users 返回裸格式 {total, page, page_size, items}（无 envelope）
      const items = Array.isArray(res?.items)
        ? res.items
        : Array.isArray(res?.data?.items)
          ? res.data.items
          : []
      const totalCount =
        typeof res?.total === 'number'
          ? res.total
          : typeof res?.data?.total === 'number'
            ? res.data.total
            : items.length
      userList.value = items
      total.value = totalCount
    } catch (e: any) {
      error.value = e?.response?.data?.message || e?.message || '获取用户列表失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchUser(id: number) {
    loading.value = true
    error.value = null
    try {
      const res = await get<any>(`/users/${id}`)
      // 后端 GET /users/{id} 返回裸用户对象（无 envelope），也兼容 envelope 格式
      const userData = res?.data ?? res
      if (userData && typeof userData === 'object') {
        currentUser.value = userData
        return userData
      }
    } catch (e: any) {
      error.value = e?.response?.data?.message || e?.message || '获取用户详情失败'
    } finally {
      loading.value = false
    }
  }

  async function createUser(data: Partial<User>) {
    const res = await post<any>('/users', data)
    // 后端 POST /users 返回裸格式 {id, username, role, ..., message}（无 envelope）
    const userData = res?.data ?? res
    if (userData && (userData.id || userData.username)) {
      userList.value.unshift(userData)
      total.value++
    }
    return res
  }

  async function updateUser(id: number, data: Partial<User>) {
    const res = await put<any>(`/users/${id}`, data)
    // 后端 PUT /users/{id} 返回 {code: 200, message: "更新成功"}（无 data 字段）
    if (res?.code === 200) {
      const idx = userList.value.findIndex((u) => u.id === id)
      if (idx !== -1) userList.value[idx] = { ...userList.value[idx], ...data } as User
      if (currentUser.value?.id === id)
        currentUser.value = { ...currentUser.value, ...data } as User
    }
    return res
  }

  async function deleteUser(id: number) {
    const res = await del<ApiResponse<null>>(`/users/${id}`)
    if (res.code === 200) {
      userList.value = userList.value.filter((u) => u.id !== id)
      total.value--
      if (currentUser.value?.id === id) currentUser.value = null
    }
    return res
  }

  async function resetUserPassword(userId: number, newPassword: string) {
    return post<ApiResponse<null>>(`/users/${userId}/admin-reset-password`, {
      new_password: newPassword,
    })
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    // 确保 currentUser 已加载（Profile 页面不可见时可能为 null）
    if (!currentUser.value?.id) {
      try {
        await getUserProfile()
      } catch {
        // /me 调用失败时仍继续，但停止改密流程（避免 userId 为空打到错误 URL）
      }
    }
    if (!currentUser.value?.id) {
      throw new Error('无法获取用户信息，请重新登录')
    }
    return put(`/users/${currentUser.value.id}/password`, {
      old_password: oldPassword,
      new_password: newPassword,
    })
  }

  async function assignRole(userId: number, roleCode: string) {
    // 后端期望 role_code 作为 query 参数（string），不是 JSON body 中的 role_id
    return post<ApiResponse<null>>(
      `/user-management/${userId}/assign-role?role_code=${encodeURIComponent(roleCode)}`
    )
  }

  // Profile / Auth 兼容方法
  async function logout() {
    AuthStorage.clear()
  }

  /** 获取当前用户 ID（从 token 解析或 currentUser） */
  function _getCurrentUserId(): number | null {
    if (currentUser.value?.id) return currentUser.value.id
    try {
      const token = AuthStorage.getToken()
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]))
        // JWT payload 中 sub 是 username（字符串），不是 user_id
        // 优先取 user_id 字段（部分 token 可能包含），没有则返回 null
        const userId = payload?.user_id
        if (typeof userId === 'number') return userId
        return null
      }
    } catch {
      /* ignore */
    }
    return null
  }

  async function getUserProfile(_userId?: number) {
    // 使用 /me 端点（无需传用户 ID，后端从 token 解析）
    const res = await get<ApiResponse<User>>('/users/me')
    if (res.code === 200 && res.data) {
      currentUser.value = res.data as User
      return res.data as User
    }
    // fallback via fetchUser for callers that pass explicit userId
    if (_userId) return fetchUser(_userId)
    throw new Error('无法获取用户信息')
  }

  async function updateUserProfile(data: Partial<User>, _userId?: number) {
    // 使用 /me/profile 端点
    const res = await put<ApiResponse<User>>('/users/me/profile', data)
    if (res.code === 200) {
      if (res.data) currentUser.value = res.data as User
      return res.data || res
    }
    throw new Error('更新失败')
  }

  async function uploadAvatar(file: File, userId?: number) {
    const id = userId || _getCurrentUserId()
    if (!id) throw new Error('无法获取用户ID，请重新登录')
    const formData = new FormData()
    formData.append('avatar', file)
    // post() 对 FormData 自动移除 Content-Type（浏览器设置 multipart boundary）
    const res = await post<ApiResponse<{ avatar_url?: string; url?: string }>>(
      `/users/${id}/avatar`,
      formData
    )
    return res.data || (res as any)
  }

  return {
    userList,
    currentUser,
    loading,
    error,
    total,
    fetchUsers,
    fetchUser,
    createUser,
    updateUser,
    deleteUser,
    resetUserPassword,
    changePassword,
    assignRole,
    logout,
    getUserProfile,
    updateUserProfile,
    uploadAvatar,
  }
})
