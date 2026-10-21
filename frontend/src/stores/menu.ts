import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { get } from '@/api/request'
import { AuthStorage } from '@/utils/authStorage'
// 与 stores/auth.ts 存在模块级互相引用（auth.ts 亦引入本文件的 useMenuStore）；
// 双方都只在函数体内延迟调用对方 store，ESM 循环依赖可安全解析。
import { useAuthStore } from '@/stores/auth'

/** 菜单节点类型：page 普通页面 / group 可折叠分组 / console 聚合页（页内 Tab 切换） */
export type MenuKind = 'page' | 'group' | 'console'

/** 聚合页内的 Tab —— path 为旧页面路由（聚合页内嵌组件的同时保留直达） */
export interface MenuTab {
  key: string
  label: string
  path: string
  icon?: string
  order?: number
  roles?: string[] | null
}

/**
 * 菜单入口（后端菜单 schema v2 的 section item）
 * - kind=page：普通页面，path 必填
 * - kind=group：可折叠分组，children 必填（children 均为 page）
 * - kind=console：系统管理聚合页，path（聚合页路由）+ tabs（旧页面路由）必填
 */
export interface MenuEntry {
  key: string
  label: string
  path?: string
  icon?: string
  order?: number
  kind: MenuKind
  roles?: string[] | null
  children?: MenuEntry[]
  tabs?: MenuTab[]
}

/** 板块（后端按 7 个板块下发；工作台固定渲染，不在 sections 内） */
export interface MenuSection {
  key: string
  label: string
  order?: number
  items: MenuEntry[]
}

/**
 * 扁平可导航条目：由 sections 展开而来，供「菜单搜索 / 最近访问 / 收藏 / 移动端导航」使用。
 * group 本身无 path，其 children 以 parentKey/parentLabel 标注父分组。
 */
export interface FlatMenuEntry {
  key: string
  label: string
  path: string
  icon?: string
  kind: MenuKind
  sectionKey: string
  sectionLabel: string
  parentKey?: string
  parentLabel?: string
  /**
   * console 子项（tab）专用：点击后跳转 `path?tab=<tabKey>`。
   * 普通 page / group children / console 自身均无此字段。
   */
  tabKey?: string
}

/**
 * 旧数组结构节点（后端 v1 菜单树）。
 * @deprecated 生产只走 v2；此类型仅为「旧数组结构降级」分支保留，便于旧数据包/缓存兼容。
 */
export interface MenuItem {
  key: string
  label: string
  path?: string
  icon?: string
  roles?: string[]
  children?: MenuItem[]
  order?: number
}

/** 后端 v2 菜单响应体（`/menus/accessible` 与 `/menus/all` 同构） */
export interface MenuPayloadV2 {
  version?: number
  sections?: unknown
  flat_keys?: unknown
}

export interface ModulePolicy {
  module_key: string
  visibility: 'visible' | 'hidden'
  edit_mode: 'full_edit' | 'read_only' | 'disabled'
}

/** 工作台：前端固定渲染的第一入口，不依赖后端 sections */
export const DASHBOARD_MENU_KEY = 'dashboard'

/** 工作台的扁平条目（用于搜索/最近/收藏/移动端导航） */
export const DASHBOARD_FLAT_ENTRY: FlatMenuEntry = {
  key: DASHBOARD_MENU_KEY,
  label: '工作台',
  path: '/dashboard',
  icon: 'HomeFilled',
  kind: 'page',
  sectionKey: 'dashboard',
  sectionLabel: '工作台',
}

/** 判断是否为普通对象（排除 null / 数组 / 基本类型） */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** 读取可选的字符串字段（非字符串一律视为缺失） */
function readText(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined
}

/** 读取可选的数值字段（非数字一律视为缺失） */
function readOrder(value: unknown): number | undefined {
  return typeof value === 'number' ? value : undefined
}

/** 解析 v2 tab；非法条目返回 null（防御旧缓存脏数据） */
function toTab(raw: unknown): MenuTab | null {
  if (!isRecord(raw) || typeof raw.key !== 'string' || typeof raw.path !== 'string') return null
  return {
    key: raw.key,
    label: readText(raw.label) ?? raw.key,
    path: raw.path,
    icon: readText(raw.icon),
    order: readOrder(raw.order),
    roles: raw.roles as string[] | null | undefined,
  }
}

/** 解析 v2 菜单入口；非法条目返回 null（防御后端/旧缓存脏数据，避免渲染死链） */
function toEntry(raw: unknown): MenuEntry | null {
  if (!isRecord(raw) || typeof raw.key !== 'string') return null
  const base = {
    key: raw.key,
    label: readText(raw.label) ?? raw.key,
    icon: readText(raw.icon),
    order: readOrder(raw.order),
    roles: raw.roles as string[] | null | undefined,
  }
  if (raw.kind === 'group') {
    const children = Array.isArray(raw.children)
      ? raw.children.map(toEntry).filter((child): child is MenuEntry => child !== null)
      : []
    if (children.length === 0) return null
    return { ...base, kind: 'group', children }
  }
  if (raw.kind === 'console') {
    const tabs = Array.isArray(raw.tabs)
      ? raw.tabs.map(toTab).filter((tab): tab is MenuTab => tab !== null)
      : []
    return { ...base, kind: 'console', path: readText(raw.path) as string, tabs }
  }
  return { ...base, kind: 'page', path: readText(raw.path) as string }
}

/** 解析 v2 板块；非法/空板块返回 null（空板块不出现，与后端过滤规则一致） */
function toSection(raw: unknown): MenuSection | null {
  if (!isRecord(raw) || typeof raw.key !== 'string' || !Array.isArray(raw.items)) return null
  const items = raw.items.map(toEntry).filter((entry): entry is MenuEntry => entry !== null)
  if (items.length === 0) return null
  return {
    key: raw.key,
    label: readText(raw.label) ?? raw.key,
    order: readOrder(raw.order),
    items,
  }
}

/** 解析 v2 sections 数组（非数组按空处理） */
function toSections(raw: unknown): MenuSection[] {
  return Array.isArray(raw)
    ? raw.map(toSection).filter((section): section is MenuSection => section !== null)
    : []
}

/** 读取 flat_keys（后端下发的可见 key 全集，含 group/console 自身与 tabs.key） */
function readFlatKeys(raw: unknown): string[] {
  return Array.isArray(raw) ? raw.filter((key): key is string => typeof key === 'string') : []
}

/** 旧数组结构节点 → v2 菜单入口（children 非空视为 group，有 path 视为 page） */
function legacyToEntry(raw: unknown): MenuEntry | null {
  if (!isRecord(raw) || typeof raw.key !== 'string') return null
  const children = Array.isArray(raw.children)
    ? raw.children.map(legacyToEntry).filter((entry): entry is MenuEntry => entry !== null)
    : []
  const base = {
    key: raw.key,
    label: readText(raw.label) ?? raw.key,
    icon: readText(raw.icon),
    order: readOrder(raw.order),
  }
  if (children.length > 0) return { ...base, kind: 'group', children }
  // 旧树里「无 children 的节点」一律按 page 收下（path 可能缺失，扁平导航会跳过），
  // 保证 allKeys 与旧版一致——否则旧权限配置里 path 缺失的 key 会被误判为不可访问。
  return { ...base, kind: 'page', path: readText(raw.path) }
}

/** 旧数组结构 → 单个合成板块（降级分支：生产不会走到，保证旧数据包不白屏） */
function legacyToSections(items: MenuItem[]): MenuSection[] {
  const entries = items.map(legacyToEntry).filter((entry): entry is MenuEntry => entry !== null)
  return entries.length > 0 ? [{ key: 'legacy', label: '全部菜单', order: 0, items: entries }] : []
}

/** 展开 sections 为扁平条目（工作台固定第一） */
function buildFlatEntries(sections: MenuSection[]): FlatMenuEntry[] {
  const flat: FlatMenuEntry[] = [{ ...DASHBOARD_FLAT_ENTRY }]
  for (const section of sections) {
    for (const item of section.items) {
      if (item.kind === 'page') {
        if (item.path) {
          flat.push({
            key: item.key,
            label: item.label,
            path: item.path,
            icon: item.icon,
            kind: 'page',
            sectionKey: section.key,
            sectionLabel: section.label,
          })
        }
      } else if (item.kind === 'console') {
        if (item.path) {
          flat.push({
            key: item.key,
            label: item.label,
            path: item.path,
            icon: item.icon,
            kind: 'console',
            sectionKey: section.key,
            sectionLabel: section.label,
          })
          // console 的 tabs 也进入扁平列表（R35）：Ctrl+K 菜单搜索 / 移动端「更多」
          // 能直达系统管理下的每个子功能（如「权限包管理」「备份恢复」），
          // 而不是只能搜到 6 个聚合页本身。跳转时由消费方拼 `?tab=` 保留聚合页上下文。
          for (const tab of item.tabs ?? []) {
            flat.push({
              key: tab.key,
              label: tab.label,
              path: item.path,
              icon: tab.icon ?? item.icon,
              kind: 'console',
              sectionKey: section.key,
              sectionLabel: section.label,
              parentKey: item.key,
              parentLabel: item.label,
              tabKey: tab.key,
            })
          }
        }
      } else {
        // group 的 children 已由 toEntry 保证为非空数组（无需再防御）
        for (const child of item.children as MenuEntry[]) {
          if (child.path) {
            flat.push({
              key: child.key,
              label: child.label,
              path: child.path,
              icon: child.icon,
              kind: 'page',
              sectionKey: section.key,
              sectionLabel: section.label,
              parentKey: item.key,
              parentLabel: item.label,
            })
          }
        }
      }
    }
  }
  return flat
}

/** 汇总可访问 key（含 group/console 自身、children、tabs.key 与后端 flat_keys） */
function collectKeys(sections: MenuSection[], extraKeys: string[]): Set<string> {
  const keys = new Set<string>(extraKeys)
  keys.add(DASHBOARD_MENU_KEY)
  for (const section of sections) {
    for (const item of section.items) {
      keys.add(item.key)
      if (item.children) {
        for (const child of item.children) keys.add(child.key)
      }
      if (item.tabs) {
        for (const tab of item.tabs) keys.add(tab.key)
      }
    }
  }
  return keys
}

export const useMenuStore = defineStore('menu', () => {
  /** 旧数组结构原始数据（仅降级分支写入；v2 下恒为空，保留以兼容历史调用方） */
  const menus = ref<MenuItem[]>([])
  /** 当前用户可见的 v2 板块列表（侧栏/移动端/聚合页数据源） */
  const sections = ref<MenuSection[]>([])
  /** 扁平可导航条目（搜索/最近/收藏/移动端导航数据源，工作台固定第一） */
  const flatEntries = ref<FlatMenuEntry[]>([{ ...DASHBOARD_FLAT_ENTRY }])
  /** 管理员全量菜单板块（`/menus/all`，供权限面板/权限包菜单树） */
  const allSections = ref<MenuSection[]>([])
  const activeMenu = ref('')
  const loaded = ref(false)
  const loading = ref(false)
  const loadFailed = ref(false)
  const allSectionsLoaded = ref(false)
  const allMenusLoadFailed = ref(false)
  /** 可访问的菜单 key 集合（含 children 与 tabs.key） */
  const allKeys = ref<Set<string>>(new Set())
  const orgPolicies = ref<Record<string, ModulePolicy>>({})

  /** 可访问的菜单 key 集合（历史命名，等价于 allKeys） */
  const accessibleKeys = computed(() => allKeys.value)

  function applySections(nextSections: MenuSection[], extraKeys: string[]) {
    sections.value = nextSections
    allKeys.value = collectKeys(nextSections, extraKeys)
    flatEntries.value = buildFlatEntries(nextSections)
  }

  /**
   * 写入菜单数据。
   * 入参兼容三种形态：v2 payload（对象）、旧数组结构（降级）、空值（空菜单）。
   */
  function setMenus(input: MenuItem[] | MenuPayloadV2 | null | undefined) {
    if (Array.isArray(input)) {
      // 旧数组结构降级：合成单板块，保证旧数据包/旧缓存仍可导航
      menus.value = input
      applySections(legacyToSections(input), [])
    } else {
      menus.value = []
      const payload = (input ?? {}) as MenuPayloadV2
      applySections(toSections(payload.sections), readFlatKeys(payload.flat_keys))
    }
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
    // 超管旁路：与后端 /menus/accessible 的超管豁免（app/api/v1/menus.py
    // _get_user_accessible_menu_keys 中 is_superuser 直接返回全量 key）配套，
    // 防止后端下发 key 与本地 allKeys 漂移导致超管菜单缺失。
    // 注意：仅 superuser（is_superuser===true 或 role==='super_admin'），
    // 不含普通 admin 角色——后端对普通 admin 仍按 allowed_menus/权限包/角色默认
    // 裁剪，本地放宽会造成"本地可见、后端拒绝"的不一致。
    const auth = useAuthStore()
    if (auth.user?.is_superuser === true || auth.user?.role === 'super_admin') {
      return true
    }
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

  /** 从后端加载当前用户可见菜单（v2；旧数组自动降级），更新 store */
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
        const res: any = await get('/menus/accessible')
        // 保持历史语义：res.data 优先；响应为 null/undefined 时取值抛错进入失败分支
        const data = res.data || res || []
        setMenus(data)
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

  /** 管理员全量菜单（`/menus/all` 同样返回 v2 结构，不做用户级过滤） */
  let _allInflight: Promise<MenuSection[]> | null = null

  /** 拉取全量菜单并写入 allSections（成功路径） */
  async function requestAllMenus(): Promise<MenuSection[]> {
    const res: any = await get('/menus/all')
    const data = res.data || res || []
    const nextSections = Array.isArray(data) ? legacyToSections(data) : toSections(data.sections)
    allSections.value = nextSections
    allSectionsLoaded.value = true
    allMenusLoadFailed.value = false
    return nextSections
  }

  async function fetchAllMenus(): Promise<MenuSection[]> {
    if (_allInflight) return _allInflight
    const token = AuthStorage.getToken()
    if (!token) return []
    // 用 promise 链而非 async try/finally：失败回退空数组，finally 统一释放 inflight
    _allInflight = requestAllMenus()
      .catch(() => {
        // 权限面板加载失败不阻塞页面；由 UI 展示空态
        allMenusLoadFailed.value = true
        return [] as MenuSection[]
      })
      .finally(() => {
        _allInflight = null
      })
    return _allInflight
  }

  /** 加载当前用户所属组织的模块策略 */
  async function fetchOrgPolicies(): Promise<void> {
    try {
      const res: any = await get('/org-policies/current')
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
    sections,
    flatEntries,
    allSections,
    activeMenu,
    loaded,
    loading,
    loadFailed,
    allSectionsLoaded,
    allMenusLoadFailed,
    accessibleKeys,
    allKeys,
    orgPolicies,
    setMenus,
    setActive,
    setOrgPolicies,
    canAccessMenu,
    canEditModule,
    isModuleDisabled,
    fetchMenus,
    fetchAllMenus,
    fetchOrgPolicies,
  }
})
