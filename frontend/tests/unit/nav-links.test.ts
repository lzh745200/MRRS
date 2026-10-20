/**
 * 导航死链检查（src/utils/navLinks.ts）
 *
 * 为什么需要它：`SettingsOverview.vue` 的快捷导航曾指向 `/system/i18n` 与
 * `/system/email`，两条都没有路由 → 点击 404。该页面没有被任何单测执行，
 * 所以这类死链在现有门禁里完全不可见。
 *
 * 本文件既验证解析函数本身，也对**真实仓库**做一次断言（最后一条用例）——
 * 以后任何人往导航里加一个不存在的路径，这条会直接红。
 */
import { describe, it, expect } from 'vitest'

import { checkRepo, extractPathLiterals, findDeadLinks, staticRoutes } from '@/utils/navLinks'

describe('navLinks 解析', () => {
  it('抽取单双引号的 path 字面量', () => {
    const src = `
      { path: '/system/users', label: 'A' },
      { path: "/system/audit", label: 'B' },
      { label: 'C' },
    `
    expect(extractPathLiterals(src)).toEqual(['/system/users', '/system/audit'])
  })

  it('静态路由排除带参与非绝对路径', () => {
    const routes = staticRoutes(['/system/users', '/system/:id', 'relative', '/'])
    expect(routes.has('/system/users')).toBe(true)
    expect(routes.has('/')).toBe(true)
    expect(routes.has('/system/:id')).toBe(false)
    expect(routes.has('relative')).toBe(false)
  })

  it('死链判定：导航有、路由没有（入参为 Set）', () => {
    const dead = findDeadLinks(['/system/i18n', '/system/users'], new Set(['/system/users']))
    expect(dead).toEqual(['/system/i18n'])
  })

  it('死链判定：入参为数组时同样生效', () => {
    expect(findDeadLinks(['/system/i18n'], ['/system/users'])).toEqual(['/system/i18n'])
  })

  it('死链判定：忽略非绝对路径（外部链接/锚点）', () => {
    expect(findDeadLinks(['https://example.com', '#top'], [])).toEqual([])
  })

  it('死链判定：结果去重并排序', () => {
    expect(findDeadLinks(['/b', '/a', '/b'], [])).toEqual(['/a', '/b'])
  })
})

describe('navLinks 真实仓库门禁', () => {
  it('导航配置里不存在死链', () => {
    const { dead, navCount, routeCount } = checkRepo()
    // 解析不到内容说明路径写错了，比"无死链"更该报错
    expect(navCount).toBeGreaterThan(0)
    expect(routeCount).toBeGreaterThan(50)
    expect(dead).toEqual([])
  })
})
