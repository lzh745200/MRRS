import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { get } from '@/api/request'
import { AuthStorage } from '@/utils/authStorage'

export interface MenuItem {
  key: string
  label: string
  path?: string
  icon?: string
  roles?: string[]
  children?: MenuItem[]
  order?: number
}

export interface ModulePolicy {
  module_key: string
  visibility: 'visible' | 'hidden'
  edit_mode: 'full_edit' | 'read_only' | 'disabled'
}

/** 从菜单树中提取所有 key（含子节点） */
function _extractAllKeys(items: MenuItem[]): Set<string> {
  const keys = new Set<string>()
  const walk = (list: MenuItem[]) => {
    for (const item of list) {
      keys.add(item.key)
      if (item.children?.length) walk(item.children)
    }
  }
  walk(items)
  return keys
}

export const useMenuStore = defineStore('menu', () => {
  const menus = ref<MenuItem[]>([])
  const activeMenu = ref('')
  const loaded = ref(false)
  const loading = ref(false)
  const loadFailed = ref(false)
  const allKeys = ref<Set<string>>(new Set())
  const orgPolicies = ref<Record<string, ModulePolicy>>({})

  /** 可访问的菜单 key 集合 */
  const accessibleKeys = computed(() => allKeys.value)

  function setMenus(items: MenuItem[]) {
    menus.value = items
    allKeys.value = _extractAllKeys(items)
    loaded.value = true
    loading.value = false
    // Empty menu is valid — only fetchMenus catch sets loadFailed
    loadFailed.value = false
  }

  function setActive(key: string) {
    activeMenu.value = key
  }

  function setOrgPolicies(policies: ModulePolicy[]) {
    const map: Record<string, ModulePolicy> = {}
    for (const p of policies) {
      map[p.module_key] = p
    }
    orgPolicies.value = map
  }

  function canAccessMenu(menuKey: string): boolean {
    if (!loaded.value) return false
    // 组织级策略优先：hidden 模块不可见
    const policy = orgPolicies.value[menuKey]
    if (policy && policy.visibility === 'hidden') return false
    return allKeys.value.has(menuKey)
  }

  function canEditModule(moduleKey: string): boolean {
    const policy = orgPolicies.value[moduleKey]
    if (!policy) return true
    return policy.edit_mode === 'full_edit'
  }

  function isModuleDisabled(moduleKey: string): boolean {
    const policy = orgPolicies.value[moduleKey]
    return policy?.edit_mode === 'disabled' || policy?.visibility === 'hidden'
  }

  /** 从后端加载当前用户可见菜单，更新 store */
  // 进行中的请求 Promise：登录后 fire-and-forget 预加载与路由守卫的 await 调用
  // 必须共享同一 Promise —— 否则守卫的 await 拿到"未加载"假完成，
  // canAccessMenu 在 loaded=false 时返回 false，登录后立即被弹到 /403。
  let _inflight: Promise<void> | null = null

  async function fetchMenus(): Promise<void> {
    if (_inflight) return _inflight
    const token = AuthStorage.getToken()
    if (!token) return
    loading.value = true
    _inflight = (async () => {
      try {
        const res = await get('/menus/accessible')
        const data = res.data || res || []
        setMenus(Array.isArray(data) ? data : [])
      } catch {
        // 加载失败：保持 loaded=false 允许下次重试，标记失败状态
        loading.value = false
        loadFailed.value = true
      } finally {
        _inflight = null
      }
    })()
    return _inflight
  }

  /** 加载当前用户所属组织的模块策略 */
  async function fetchOrgPolicies(): Promise<void> {
    try {
      const res = await get('/org-policies/current')
      const data = res.data || res || []
      if (Array.isArray(data)) {
        setOrgPolicies(data)
      }
    } catch {
      // 策略加载失败不阻塞正常使用
    }
  }

  return {
    menus,
    activeMenu,
    loaded,
    loading,
    loadFailed,
    accessibleKeys,
    orgPolicies,
    setMenus,
    setActive,
    setOrgPolicies,
    canAccessMenu,
    canEditModule,
    isModuleDisabled,
    fetchMenus,
    fetchOrgPolicies,
  }
})
