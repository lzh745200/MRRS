/**
 * views/dashboard/components/QuickActions.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：全部动作按钮的 pushSafe 跳转路径、backup/restore 事件、isManager/isAdmin 条件渲染、
 * backingUp 文案分支、onMounted 菜单加载分支。
 *
 * 方案：mock '@/composables/useRouterSafe' 与 '@/stores/menu'，el-collapse 等使用轻量 stub。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const icons = vi.hoisted(() => {
  const names = [
    'House', 'Document', 'Money', 'School', 'Tickets', 'OfficeBuilding', 'Download',
    'EditPen', 'Sunny', 'Aim', 'Plus', 'Tools', 'DataAnalysis', 'TrendCharts', 'Upload',
    'Refresh', 'Calendar', 'MapLocation', 'Select', 'ChatDotRound', 'Warning', 'CreditCard',
    'Files', 'Monitor', 'UserFilled', 'Setting', 'Box', 'Key', 'Reading',
  ]
  const stubs: Record<string, any> = {}
  for (const n of names) stubs[n] = { name: n, template: '<i />' }
  return stubs
})

const menuMock = vi.hoisted(() => ({
  loaded: true,
  fetchMenus: vi.fn(),
}))

const routerMock = vi.hoisted(() => ({ pushSafe: vi.fn() }))

vi.mock('@element-plus/icons-vue', () => icons)

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: routerMock.pushSafe }),
}))

vi.mock('@/stores/menu', () => ({
  useMenuStore: () => menuMock,
}))

import QuickActions from '@/views/dashboard/components/QuickActions.vue'

const stubs = {
  'el-collapse': {
    name: 'ElCollapse',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div class="qa-collapse-stub"><slot /></div>',
  },
  'el-collapse-item': {
    name: 'ElCollapseItem',
    props: ['name'],
    template: '<div class="qa-item"><slot name="title" /><slot /></div>',
  },
  'el-tag': { name: 'ElTag', template: '<span><slot /></span>' },
}

const CORE_PATHS = [
  '/supported-villages',
  '/projects',
  '/funds',
  '/schools',
  '/policies',
  '/organization',
  '/projects/import',
  '/funds/user',
  '/rural-works',
  '/effectiveness',
  '/projects/create',
  '/schools/create',
]

const DATA_PATHS = [
  '/data-analysis',
  '/funds/analysis',
  '/schools/analysis',
  '/import/data',
  '/export/report',
  '/data-sync',
  '/data-entry',
  '/work-calendar',
  '/data-analysis/map',
  '/data-analysis/assessment',
  '/supported-villages/yearly',
]

const WORKFLOW_PATHS = [
  '/approval',
  '/rural-works/list',
  '/message',
  '/funds', // 资金周期（需从经费列表选项目进入）
  '/funds/contract',
  '/funds/anomaly',
  '/funds/budget',
  '/report/templates',
  '/todos',
  '/funds/report',
  '/funds', // 经费结算（需从经费列表选项目进入）
]

const SYSTEM_PATHS = [
  '/system/monitoring',
  '/system/users',
  '/system/config',
  '/system/audit',
  '/system/backup',
  '/admin/machine-code',
  '/data-management/logs',
  '/help',
]

function mountQA(props: Record<string, boolean>) {
  return mount(QuickActions, {
    props,
    global: { stubs },
  })
}

describe('dashboard/components/QuickActions.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    menuMock.loaded = true
  })

  it('管理员模式下渲染全部动作组并点击每个按钮跳转对应路由', async () => {
    const w = mountQA({ isManager: true, isAdmin: true, backingUp: false })
    const btns = w.findAll('button.action-btn')
    expect(btns.length).toBe(44)

    for (const b of btns) {
      await b.trigger('click')
    }
    const calls = routerMock.pushSafe.mock.calls.map((c: any) => c[0])
    expect(calls).toEqual([...CORE_PATHS, ...DATA_PATHS, ...WORKFLOW_PATHS, ...SYSTEM_PATHS])
  })

  it('普通用户模式只显示核心与审批两组，且备份/恢复按钮隐藏', async () => {
    const w = mountQA({ isManager: false, isAdmin: false, backingUp: true })
    const btns = w.findAll('button.action-btn')
    expect(btns.length).toBe(22)

    expect(w.text()).not.toContain('一键备份')
    expect(w.text()).not.toContain('恢复数据')
    expect(w.text()).not.toContain('项目导入')

    for (const b of btns) {
      await b.trigger('click')
    }
    const calls = routerMock.pushSafe.mock.calls.map((c: any) => c[0])
    expect(calls).toEqual([...CORE_PATHS.filter((p) => p !== '/projects/import'), ...WORKFLOW_PATHS])
  })

  it('仅管理员：显示恢复数据/用户与角色/系统配置/备份管理/机器码；无审计/操作日志/备份按钮', () => {
    const w = mountQA({ isManager: false, isAdmin: true, backingUp: false })
    const text = w.text()
    expect(text).toContain('恢复数据')
    expect(text).toContain('用户与角色')
    expect(text).toContain('系统配置')
    expect(text).toContain('备份管理')
    expect(text).toContain('机器码管理')
    expect(text).not.toContain('一键备份')
    expect(text).not.toContain('审计日志')
    expect(text).not.toContain('操作日志')
  })

  it('仅管理员时点击恢复数据触发 restore 事件', async () => {
    const w = mountQA({ isManager: false, isAdmin: true, backingUp: false })
    await w.findAll('button.action-btn').find((b) => b.text().includes('恢复数据'))!.trigger('click')
    expect(w.emitted('restore')).toBeTruthy()
  })

  it('仅管理员时点击系统监控跳转 /system/monitoring', async () => {
    const w = mountQA({ isManager: false, isAdmin: true, backingUp: false })
    await w.findAll('button.action-btn').find((b) => b.text().includes('系统监控'))!.trigger('click')
    expect(routerMock.pushSafe).toHaveBeenCalledWith('/system/monitoring')
  })

  it('仅管理员时点击帮助文档跳转 /help', async () => {
    const w = mountQA({ isManager: false, isAdmin: true, backingUp: false })
    await w.findAll('button.action-btn').find((b) => b.text().includes('帮助文档'))!.trigger('click')
    expect(routerMock.pushSafe).toHaveBeenCalledWith('/help')
  })

  it('仅管理员时点击项目导入跳转 /projects/import', async () => {
    const w = mountQA({ isManager: false, isAdmin: true, backingUp: false })
    await w.findAll('button.action-btn').find((b) => b.text().includes('项目导入'))!.trigger('click')
    expect(routerMock.pushSafe).toHaveBeenCalledWith('/projects/import')
  })

  it('仅管理员时点击审计日志跳转 /system/audit', async () => {
    const w = mountQA({ isManager: true, isAdmin: false, backingUp: false })
    await w.findAll('button.action-btn').find((b) => b.text().includes('审计日志'))!.trigger('click')
    expect(routerMock.pushSafe).toHaveBeenCalledWith('/system/audit')
  })

  it('仅管理员时点击操作日志跳转 /data-management/logs', async () => {
    const w = mountQA({ isManager: true, isAdmin: false, backingUp: false })
    await w.findAll('button.action-btn').find((b) => b.text().includes('操作日志'))!.trigger('click')
    expect(routerMock.pushSafe).toHaveBeenCalledWith('/data-management/logs')
  })

  it('一键备份：backingUp=true 显示备份中并禁用', async () => {
    const w = mountQA({ isManager: true, isAdmin: false, backingUp: true })
    const backupBtn = w.findAll('button.action-btn').find((b) => b.text().includes('备份中'))!
    expect(backupBtn.attributes('disabled')).toBeDefined()
    await backupBtn.trigger('click')
    expect(w.emitted('backup')).toBeFalsy()
    expect(routerMock.pushSafe).not.toHaveBeenCalled()
  })

  it('backingUp=false 时显示一键备份并触发 backup 事件', async () => {
    const w = mountQA({ isManager: true, isAdmin: false, backingUp: false })
    const backupBtn = w.findAll('button.action-btn').find((b) => b.text().includes('一键备份'))!
    await backupBtn.trigger('click')
    expect(w.emitted('backup')).toBeTruthy()
  })

  it('onMounted：菜单未加载时调用 fetchMenus', async () => {
    menuMock.loaded = false
    mountQA({ isManager: true, isAdmin: true, backingUp: false })
    await flushPromises()
    expect(menuMock.fetchMenus).toHaveBeenCalledTimes(1)
  })

  it('onMounted：菜单已加载时不调用 fetchMenus', async () => {
    menuMock.loaded = true
    mountQA({ isManager: true, isAdmin: true, backingUp: false })
    await flushPromises()
    expect(menuMock.fetchMenus).not.toHaveBeenCalled()
  })

  it('action-grid 分组标题与数量标签渲染', () => {
    const w = mountQA({ isManager: true, isAdmin: true, backingUp: false })
    expect(w.text()).toContain('核心业务')
    expect(w.text()).toContain('数据与分析')
    expect(w.text()).toContain('审批与流程')
    expect(w.text()).toContain('系统管理')
  })

  it('el-collapse v-model：展开分组更新 activeGroups', async () => {
    const w = mountQA({ isManager: true, isAdmin: true, backingUp: false })
    const collapse = w.findComponent({ name: 'ElCollapse' })
    collapse.vm.$emit('update:modelValue', ['core', 'workflow'])
    await flushPromises()
    expect((w.vm as any).activeGroups).toEqual(['core', 'workflow'])
  })

  it('多次重渲染覆盖静态节点缓存分支', async () => {
    const w = mountQA({ isManager: true, isAdmin: true, backingUp: false })
    const collapse = w.findComponent({ name: 'ElCollapse' })
    for (const value of [['workflow'], ['core', 'data'], ['data', 'system'], ['core']]) {
      collapse.vm.$emit('update:modelValue', value)
      await flushPromises()
    }
    await w.findAll('button.action-btn').find((b) => b.text().includes('系统监控'))!.trigger('click')
    expect(routerMock.pushSafe).toHaveBeenCalledWith('/system/monitoring')
    expect((w.vm as any).activeGroups).toEqual(['core'])
  })

  it('非管理员挂载后重渲染系统监控 v-if 假分支', async () => {
    const w = mountQA({ isManager: false, isAdmin: false, backingUp: false })
    const collapse = w.findComponent({ name: 'ElCollapse' })
    collapse.vm.$emit('update:modelValue', [])
    await flushPromises()
    expect(w.findAll('button.action-btn').length).toBe(22)
  })
})
