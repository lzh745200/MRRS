/**
 * W3-T2：路由 meta.menuKey 与菜单配置对齐校验
 * 每个菜单叶子项（含 path）必须存在对应路由，且路由 meta.menuKey 与菜单 key 一致；
 * 路由声明的 menuKey 必须都存在于菜单键集合。
 */
import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { MENU_CONFIG, getAllMenuKeys, type MenuItem } from '@/config/menu-config'
import router, { routes } from '@/router/index'

function flatten(list: any[]): any[] {
  const out: any[] = []
  for (const r of list) {
    out.push(r)
    if (r.children) out.push(...flatten(r.children))
  }
  return out
}

const allRoutes = flatten(routes)
const routeByPath = new Map<string, any>()
for (const r of allRoutes) {
  if (r.path && r.path.startsWith('/')) {
    routeByPath.set(r.path, r)
    // 可选参数路由（如 /data-package/version/:id?）在不带参数时同样可达，
    // 菜单 path 按基础路径对齐（14d2b243 版本页加 :id? 后 W3-T2 需感知可选段）
    const basePath = r.path.replace(/\/:[^/]+\?/g, '')
    if (basePath !== r.path && !routeByPath.has(basePath)) routeByPath.set(basePath, r)
  }
}

function leafMenuItems(items: MenuItem[]): MenuItem[] {
  const out: MenuItem[] = []
  for (const it of items) {
    if (it.path) out.push(it)
    if (it.children) out.push(...leafMenuItems(it.children as MenuItem[]))
  }
  return out
}

const leaves = leafMenuItems(MENU_CONFIG)

// path → 允许声明的 menuKey 集合（菜单配置允许同一 path 对应多个 key，如 /data-package）
const allowedKeysByPath = new Map<string, Set<string>>()
for (const item of leaves) {
  if (!allowedKeysByPath.has(item.path!)) allowedKeysByPath.set(item.path!, new Set())
  allowedKeysByPath.get(item.path!)!.add(item.key)
}

describe('W3-T2 路由 menuKey 对齐', () => {
  it('每个菜单叶子项 path 对应路由都声明了匹配的 menuKey', () => {
    const missing: string[] = []
    for (const item of leaves) {
      const route = routeByPath.get(item.path!)
      if (!route) {
        missing.push(`${item.key} -> 路由缺失 ${item.path}`)
        continue
      }
      const allowed = allowedKeysByPath.get(item.path!)!
      if (!allowed.has(route.meta?.menuKey)) {
        missing.push(`${item.key} (path ${item.path}) meta.menuKey=${route.meta?.menuKey}`)
      }
    }
    expect(missing).toEqual([])
  })

  it('路由声明的 menuKey 全部存在于菜单键集合', () => {
    const validKeys = new Set(getAllMenuKeys())
    const bad: string[] = []
    for (const r of allRoutes) {
      const mk = r.meta?.menuKey
      if (mk && !validKeys.has(mk)) bad.push(`${r.path}: ${mk}`)
    }
    expect(bad).toEqual([])
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// 2026-09-14 补：导航字面量可解析性守卫
//
// 背景（真实 404 事故）：管理员面板 AdminDashboard.vue 硬编码了
// pushSafe('/system/users-orgs') 与 { path: '/data-management/overview' }，
// 二者都不是已注册路由，点击后落入 404 通配路由。此前的 menuKeyAlignment
// 只校验「菜单配置 → 路由」，覆盖不到**视图里硬编码的跳转**，故补此守卫。
// ─────────────────────────────────────────────────────────────────────────────
const SRC_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../src')

function collectSourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules') continue
      collectSourceFiles(full, out)
    } else if (/\.(vue|ts)$/.test(entry.name) && !entry.name.endsWith('.d.ts')) {
      out.push(full)
    }
  }
  return out
}

/** 把路由 path 编译为匹配正则：:id → 一段，:id? → 可选段 */
function routeToRegex(route: string): RegExp {
  const body = route
    .split('/')
    .filter(Boolean)
    .map((seg) => {
      if (seg.startsWith(':')) return seg.endsWith('?') ? '(?:/[^/]+)?' : '/[^/]+'
      return '/' + seg.replace(/[.*+?^$(){}|[\]\\]/g, '\\$&')
    })
    .join('')
  return new RegExp('^' + (body || '/') + '/?$')
}

/** 已注册路由 + alias 的匹配器（排除 404 通配路由） */
const routeMatchers: RegExp[] = []
for (const r of allRoutes) {
  const candidates = [r.path, ...(Array.isArray(r.alias) ? r.alias : r.alias ? [r.alias] : [])]
  for (const p of candidates) {
    if (typeof p !== 'string' || !p.startsWith('/')) continue
    if (p.includes('*') || p.includes('(') || p.includes(':')) {
      // 含动态段仍需编译（可选参数路由要能匹配基础路径）
      if (p.includes('*')) continue
    }
    routeMatchers.push(routeToRegex(p))
  }
}

const NAV_PATTERNS: Array<[string, RegExp]> = [
  ['pushSafe', /pushSafe\(\s*['"`]([^'"`]+)['"`]/g],
  ['router.push', /router\.push\(\s*['"`]([^'"`]+)['"`]/g],
  ['router.replace', /router\.replace\(\s*['"`]([^'"`]+)['"`]/g],
  ['to', /\bto=["'](\/[^"']*)["']/g],
  ['to.path', /\bto:\s*\{\s*path:\s*['"`]([^'"`]+)['"`]/g],
  ['index', /\bindex=["'](\/[^"']*)["']/g],
  ['obj.path', /\bpath:\s*['"`](\/[^'"`]*)['"`]/g],
]

describe('W3-T2 导航字面量可解析性（防 404 回归）', () => {
  it('src 下所有硬编码跳转路径都能解析到已注册路由', () => {
    const files = collectSourceFiles(SRC_DIR)
    expect(files.length).toBeGreaterThan(100) // 目录解析失败时快速暴露

    const unresolved: string[] = []
    for (const file of files) {
      const text = fs.readFileSync(file, 'utf-8')
      for (const [kind, pattern] of NAV_PATTERNS) {
        pattern.lastIndex = 0
        let m: RegExpExecArray | null
        while ((m = pattern.exec(text)) !== null) {
          const raw = m[1]
          // 只看具体跳转路径：跳过模板插值、以及路由模式定义
          // （404 通配 /:pathMatch(.*)* 这类含 : * ( ) 的模式不是可跳转目标）
          if (!raw.startsWith('/') || /[{*():]/.test(raw)) continue
          const target = raw.split('?')[0].split('#')[0]
          if (routeMatchers.some((re) => re.test(target))) continue
          const line = text.slice(0, m.index).split('\n').length
          unresolved.push(
            `${path.relative(SRC_DIR, file).replace(/\\/g, '/')}:${line} [${kind}] ${target}`
          )
        }
      }
    }

    expect(unresolved).toEqual([])
  })
})

describe('W3-T2 管理面板跳转目标可解析（404 回归锁定）', () => {
  // 缺陷复现：AdminDashboard 的横幅按钮与快捷入口曾硬编码 /system/users-orgs、
  // /data-management/overview，二者均非注册路由 → 点击落入 404 通配路由。
  const ADMIN_TARGETS = [
    '/system/users',
    '/system/roles',
    '/system/backup',
    '/system/audit',
    '/system/config',
    '/data-management',
  ]

  it('横幅按钮与快捷入口全部命中真实路由（非 404 通配）', () => {
    const bad: string[] = []
    for (const p of ADMIN_TARGETS) {
      const resolved = router.resolve(p)
      const hitCatchAll = resolved.matched.some((m) => String(m.path).includes('pathMatch'))
      if (resolved.matched.length === 0 || hitCatchAll) bad.push(p)
    }
    expect(bad).toEqual([])
  })

  it('/system/users 命中用户管理页面（非 404）', () => {
    const resolved = router.resolve('/system/users')
    expect(resolved.name).toBe('SystemUsers')
    expect(resolved.matched.some((m) => String(m.path).includes('pathMatch'))).toBe(false)
    const last = resolved.matched[resolved.matched.length - 1] as any
    expect(typeof last.components?.default).toBe('function') // 懒加载组件装载器存在
  })
})


