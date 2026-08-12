import { defineStore } from 'pinia'
import { ref } from 'vue'
import { get } from '@/api/request'
import { useAuthStore } from '@/stores/auth'

export interface Role {
  id: string
  name: string
  label: string
  permissions: string[]
}

export interface Permission {
  id: string
  name: string
  label: string
  resource: string
  action: string
}

export const useRbacStore = defineStore('rbac', () => {
  const roles = ref<Role[]>([])
  const permissions = ref<Permission[]>([])
  const loading = ref(false)

  async function fetchRoles() {
    loading.value = true
    try {
      const res = await get<{ code?: number; success?: boolean; data: Role[] }>('/rbac/roles')
      // 后端返回 {success, data}（无 code 字段）——兼容 code===200 与 success 两种格式
      if ((res.code === 200 || res.success !== false) && Array.isArray(res.data))
        roles.value = res.data
    } catch {
      /* silent */
    } finally {
      loading.value = false
    }
  }

  async function fetchPermissions() {
    loading.value = true
    try {
      const res = await get<{ code?: number; success?: boolean; data: Permission[] }>(
        '/rbac/permissions'
      )
      // 后端返回 {success, data, categories}（无 code 字段）——兼容 code===200 与 success 两种格式
      if ((res.code === 200 || res.success !== false) && Array.isArray(res.data))
        permissions.value = res.data
    } catch {
      /* silent */
    } finally {
      loading.value = false
    }
  }

  /** 权限检查：需要用户角色 + 权限标识 */
  function hasPermission(userRole: string, permission: string): boolean {
    if (!userRole || !permission) return false
    // Super admin bypasses all checks
    if (userRole === 'super_admin') return true
    // Check role-level permissions
    const role = roles.value.find((r) => r.name === userRole)
    if (role?.permissions.includes('*') || role?.permissions.includes(permission)) return true
    return false
  }

  /** 角色检查：当前用户是否拥有指定角色 */
  function hasRole(roleName: string): boolean {
    const authStore = useAuthStore()
    const currentRole = authStore.user?.role || ''
    if (!roleName) return false
    if (currentRole === 'super_admin') return true
    if (Array.isArray(currentRole)) {
      return currentRole.includes(roleName)
    }
    return currentRole === roleName
  }

  /** 别名：异步加载用户权限（供 permissionGuard 使用） */
  async function loadUserPermissions(): Promise<void> {
    await fetchPermissions()
  }

  return {
    roles,
    permissions,
    loading,
    fetchRoles,
    fetchPermissions,
    hasPermission,
    hasRole,
    loadUserPermissions,
  }
})
