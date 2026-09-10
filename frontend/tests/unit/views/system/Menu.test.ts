/**
 * views/system/Menu.vue 覆盖率攻坚
 * 覆盖：菜单树构建全分支（路由过滤、meta 字段、空路由）
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

let routeChildren: any[] | undefined = undefined

vi.mock('vue-router', () => ({
  useRouter: () => ({
    options: {
      routes: [{ path: '/', children: routeChildren }],
    },
  }),
  useRoute: () => ({ params: {}, query: {} }),
}))

import Menu from '@/views/system/Menu.vue'

function makeChildren() {
  return [
    {
      path: 'dashboard',
      name: 'Dashboard',
      meta: { title: '首页', icon: 'HomeFilled', requiresAdmin: true },
    },
    {
      path: 'funds',
      name: 'Funds',
      meta: { title: '资金管理', hidden: true },
    },
    {
      path: 'hidden-no-title',
      name: 'NoTitle',
      meta: {},
    },
    {
      path: 'plain',
      name: 'Plain',
    },
    {
      path: 'no-name',
      meta: { title: '无名路由' },
    },
  ]
}

beforeEach(() => {
  routeChildren = makeChildren()
})

describe('Menu.vue', () => {
  it('渲染菜单树（含图标/隐藏/管理员标记）', async () => {
    const w = mount(Menu, {
      global: {
        renderStubDefaultSlot: true,
        stubs: {
          'el-tag': { template: '<span><slot /></span>' },
          'el-table-column': {
            name: 'ElTableColumn',
            template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
            data() {
              return {
                rowA: { title: '首页', path: '/dashboard', name: 'Dashboard', icon: 'HomeFilled', hidden: false, requiresAdmin: true },
                rowB: { title: '无名路由', path: '/no-name', name: '', icon: '', hidden: true, requiresAdmin: false },
              }
            },
          },
        },
      },
    })
    const vm = w.vm as any
    expect(vm.menuCount).toBe(3)
    expect(vm.menuTree[0]).toEqual({
      path: '/dashboard',
      name: 'Dashboard',
      title: '首页',
      icon: 'HomeFilled',
      hidden: false,
      // E1：dashboard 路由 meta 无 roles → 非"仅管理员"
      requiresAdmin: false,
      children: undefined,
      hasChildren: false,
    })
    expect(vm.menuTree[1].hidden).toBe(true)
    // 无 name 的路由 → 空字符串
    expect(vm.menuTree[2].name).toBe('')
    expect(w.text()).toContain('管理员')
    expect(w.text()).toContain('隐藏')
    expect(w.text()).toContain('显示')
    expect(w.text()).toContain('所有人')
  })

  it('无主路由 → 空菜单', async () => {
    routeChildren = undefined
    const w = mount(Menu)
    expect((w.vm as any).menuCount).toBe(0)
    expect((w.vm as any).menuTree).toEqual([])
  })

  it('子路由无 meta.title → 被过滤', async () => {
    const w = mount(Menu)
    expect((w.vm as any).menuCount).toBe(3)
  })

  it('meta 缺失字段 → 默认值', async () => {
    const w = mount(Menu)
    const vm = w.vm as any
    // 无 meta / meta 无 title 的路由 → 过滤；有 title 无 name → name 空串
    expect(vm.menuTree.length).toBe(3)
    await nextTick()
    expect(w.exists()).toBe(true)
  })

  it('meta.roles 全为管理员级 → requiresAdmin 为 true（isAdminOnly 真分支）', async () => {
    routeChildren = [
      { path: 'admin-only', name: 'AdminOnly', meta: { title: '仅管理员', roles: ['admin', 'super_admin'] } },
      { path: 'mixed', name: 'Mixed', meta: { title: '混合角色', roles: ['admin', 'user'] } },
    ]
    const w = mount(Menu)
    const vm = w.vm as any
    expect(vm.menuTree[0].requiresAdmin).toBe(true) // every → true
    expect(vm.menuTree[1].requiresAdmin).toBe(false) // 含非管理员角色 → false
  })
})
