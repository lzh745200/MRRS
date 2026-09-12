/**
 * 系统管理子菜单动态渲染解析器
 *
 * 背景：DefaultLayoutSafe 侧边栏「系统管理」组原为硬编码 6 个入口，而后端
 * MENU_DEFINITIONS 的 system 组有 25+ 功能项（缓存/零信任/更新日志/权限包/
 * 后台任务/数据分级/运行环境/系统总览/管理面板……），路由均已注册
 * （router/index.ts）却无任何 UI 入口，超管也"看不到"这些功能。
 *
 * 本模块把 menuStore.menus 中 key==='system' 节点的 children 解析为可直接
 * 渲染的菜单项列表，规则（防死链 + 防重复 + 不漏功能）：
 *  1. 去重跳过：backup / messages（顶级已有独立侧边栏入口）、machine-code /
 *     pass-code（保留侧边栏静态「机器码与通行码」isAdmin 合一入口，避免同屏双入口）。
 *  2. path 解析优先级：child.path 是已注册路由 → 使用之；否则查
 *     meta.menuKey === child.key 的路由 path 兜底；再否则查 PATH_OVERRIDES
 *     （后端菜单 path 与前端路由漂移的映射表）；三者皆无则跳过（不渲染死链）。
 *  3. child 无可用 path 但有 children：将 children 提升一级按同样规则渲染，
 *     保证不漏功能（当前后端 system 组无此形态，属前向兼容）。
 *  4. 顺序保持后端下发顺序；child 自带 order 字段时按 order 升序（稳定排序）。
 */
import type { MenuItem } from '@/stores/menu'

/** 与既有侧边栏入口重复、动态列表中跳过的 key（避免同屏双入口） */
const DEDUP_SKIP_KEYS: ReadonlySet<string> = new Set([
  'backup', // 顶级「备份管理」独立入口（普通用户只读可见，不依赖 system 组）
  'messages', // 顶级「消息中心」独立入口
  'machine-code', // 静态「机器码与通行码」isAdmin 合一入口（保留静态，避免重复）
  'pass-code', // 同上
])

/**
 * 后端菜单 path 与前端路由漂移的兜底映射。
 * 这些 key 的 child.path 不是已注册路由、也没有 meta.menuKey 匹配的路由，
 * 直接使用会渲染死链；映射到承载同一功能的真实路由。
 */
const PATH_OVERRIDES: Readonly<Record<string, string>> = {
  // 后端 /system/users-orgs 无对应路由，用户与组织管理页面实际在 /system/users
  'users-orgs': '/system/users',
  // 后端 /system/monitor 漂移，系统监控页面实际路由为 /system/monitoring
  monitor: '/system/monitoring',
}

/** 动态渲染的系统管理子菜单项（index 即路由 path） */
export interface SystemMenuItem {
  key: string
  label: string
  path: string
}

/** 解析所需的最小路由结构（vue-router RouteRecordNormalized 的结构子集） */
export interface SystemMenuRoute {
  path: string
  meta?: Readonly<Record<string, unknown>>
}

/**
 * 解析 system 组 children 为可渲染菜单项列表。
 *
 * @param menus 后端下发的菜单树（menuStore.menus）
 * @param routes 已注册路由表（router.getRoutes() 的结构子集即可）
 * @returns 去重、防死链、按 order 排序后的子菜单项；无 system 组时返回 []
 */
export function resolveSystemMenuItems(
  menus: readonly MenuItem[] | undefined | null,
  routes: readonly SystemMenuRoute[] | undefined | null
): SystemMenuItem[] {
  // menus/routes 非数组（store 未初始化、调用方传错）时按空集处理，不抛错
  if (!Array.isArray(menus) || !Array.isArray(routes)) return []

  // 路由查找表：全量已注册 path + menuKey → path（重复 menuKey 取首个）
  const routePaths = new Set<string>()
  const menuKeyPaths = new Map<string, string>()
  for (const r of routes) {
    if (!r.path) continue
    routePaths.add(r.path)
    const mk = r.meta?.menuKey
    if (typeof mk === 'string' && !menuKeyPaths.has(mk)) menuKeyPaths.set(mk, r.path)
  }

  const systemNode = menus.find((m) => m && m.key === 'system')
  const children = systemNode?.children
  if (!children || children.length === 0) return []

  const items: SystemMenuItem[] = []
  const seenKeys = new Set<string>()
  const seenPaths = new Set<string>()

  /** 解析 child 的渲染 path：有效路由 path → menuKey 路由兜底 → 漂移覆盖表，皆无返回 '' */
  const resolvePath = (child: MenuItem): string => {
    if (child.path && routePaths.has(child.path)) return child.path
    return menuKeyPaths.get(child.key) ?? PATH_OVERRIDES[child.key] ?? ''
  }

  /** 逐项解析并入列；无 path 但有 children 的提升一级（保证不漏功能） */
  const pushItem = (child: MenuItem): void => {
    if (!child.key || !child.label) return
    if (DEDUP_SKIP_KEYS.has(child.key) || seenKeys.has(child.key)) return
    seenKeys.add(child.key)
    const path = resolvePath(child)
    if (!path) {
      // 无可用 path：children 提升一级按同样规则解析，避免整组功能丢失
      if (child.children && child.children.length > 0) {
        for (const c of child.children) pushItem(c)
      }
      return
    }
    // 不同 key 解析到同一路径（历史漂移）时只保留首个，避免重复入口
    if (seenPaths.has(path)) return
    seenPaths.add(path)
    items.push({ key: child.key, label: child.label, path })
  }

  // order 字段存在时按 order 升序；Array#sort 稳定，缺省（0）保持后端下发顺序
  const sorted = [...children].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  for (const child of sorted) pushItem(child)
  return items
}
