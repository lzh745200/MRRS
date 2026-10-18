/**
 * views/dashboard/components/HeaderActions.vue 专项覆盖（W11-T45）
 *
 * 背景：原 views/dashboard/PageHeader.vue 与共享 components/common/PageHeader.vue
 * 重名重复，已去重——页头骨架（标题/副标题/#extra）由共享标准件承担，其自身覆盖见
 * tests/unit/components/common/PageHeader.test.ts；本文件只覆盖工作台专属操作区。
 *
 * 覆盖：GlobalSearch 渲染、新建项目/数据分析 pushSafe、管理员备份按钮显隐与
 * backup 事件、backingUp 两种文案、更多菜单 layout/bigscreen/其他命令三态。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const { mockPushSafe } = vi.hoisted(() => ({ mockPushSafe: vi.fn() }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

import HeaderActions from '@/views/dashboard/components/HeaderActions.vue'

function mountActions(props: { isAdmin: boolean; backingUp: boolean } = {
  isAdmin: true,
  backingUp: false,
}) {
  return mount(HeaderActions, {
    props,
    global: {
      stubs: {
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
        'el-icon': { template: '<span><slot /></span>' },
        'el-dropdown': { template: '<div><slot /><slot name="dropdown" /></div>' },
        'el-dropdown-menu': { template: '<div><slot /></div>' },
        'el-dropdown-item': { template: '<div class="el-dropdown-item-stub"><slot /></div>' },
        GlobalSearch: {
          name: 'GlobalSearch',
          template: '<div class="gs-stub" />',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('HeaderActions 工作台页头操作区', () => {
  it('渲染全局搜索与主操作按钮，点击走 pushSafe 导航', async () => {
    const wrapper = mountActions()
    expect(wrapper.findComponent({ name: 'GlobalSearch' }).exists()).toBe(true)

    await wrapper.find('[data-test="btn-new-project"]').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/projects/create')

    await wrapper.find('[data-test="btn-analysis"]').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/data-analysis')
    wrapper.unmount()
  })

  it('管理员显示备份按钮，点击 emit backup（本组件不直连备份 API）', async () => {
    const wrapper = mountActions({ isAdmin: true, backingUp: false })
    const backupBtn = wrapper.find('[data-test="btn-backup"]')
    expect(backupBtn.exists()).toBe(true)
    expect(backupBtn.text()).toContain('一键备份')

    await backupBtn.trigger('click')
    expect(wrapper.emitted('backup')).toHaveLength(1)
    wrapper.unmount()
  })

  it('非管理员隐藏备份按钮', () => {
    const wrapper = mountActions({ isAdmin: false, backingUp: false })
    expect(wrapper.find('[data-test="btn-backup"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('backingUp 为真时按钮显示备份中并可再次触发 backup', async () => {
    const wrapper = mountActions({ isAdmin: true, backingUp: true })
    const backupBtn = wrapper.find('[data-test="btn-backup"]')
    expect(backupBtn.text()).toContain('备份中...')
    await backupBtn.trigger('click')
    expect(wrapper.emitted('backup')).toHaveLength(1)
    wrapper.unmount()
  })

  it('更多菜单：layout → emit toggle-layout；其他命令 → 无 emit', () => {
    const wrapper = mountActions()
    const vm = wrapper.vm as any

    vm.handleMoreCommand('layout')
    expect(wrapper.emitted('toggle-layout')).toHaveLength(1)

    vm.handleMoreCommand('other')
    expect(wrapper.emitted('toggle-layout')).toHaveLength(1)
    wrapper.unmount()
  })

  it('更多菜单：bigscreen → pushSafe(/bigscreen) 且提前返回', () => {
    const wrapper = mountActions()
    const vm = wrapper.vm as any

    vm.handleMoreCommand('bigscreen')
    expect(mockPushSafe).toHaveBeenCalledWith('/bigscreen')
    expect(mockPushSafe).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('toggle-layout')).toBeFalsy()
    wrapper.unmount()
  })
})
