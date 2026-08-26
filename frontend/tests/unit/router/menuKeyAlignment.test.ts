/**
 * W3-T2：路由 meta.menuKey 与菜单配置对齐校验
 * 每个菜单叶子项（含 path）必须存在对应路由，且路由 meta.menuKey 与菜单 key 一致；
 * 路由声明的 menuKey 必须都存在于菜单键集合。
 */
import { describe, it, expect } from 'vitest'
import { MENU_CONFIG, getAllMenuKeys, type MenuItem } from '@/config/menu-config'
import { routes } from '@/router/index'

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
  if (r.path && r.path.startsWith('/')) routeByPath.set(r.path, r)
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
