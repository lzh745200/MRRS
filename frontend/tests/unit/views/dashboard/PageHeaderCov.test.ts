/**
 * views/dashboard/PageHeader.vue 补充覆盖（与 PageHeader.test.ts 合并达四指标 100%）
 *
 * 覆盖：handleBackup 成功/失败（post + ElMessage + emit backup-complete + loading）、
 * handleMoreCommand layout/其他命令、btn-new-project/btn-analysis pushSafe、
 * displayName 三种形态（full_name / username / 兜底）、isAdmin 两种形态（role / is_superuser）
 * 与备份按钮 v-if 假侧、格式化日期星期渲染。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const { ElMessage, mockPost, mockPushSafe, authBox } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockPost: vi.fn(),
  mockPushSafe: vi.fn(),
  authBox: { user: { full_name: '管理员', username: 'admin', role: 'admin', is_superuser: false } },
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({
  post: mockPost,
  get: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authBox,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

import PageHeader from '@/views/dashboard/PageHeader.vue'

function mountHeader() {
  return mount(PageHeader, {
    global: {
      plugins: [createPinia()],
      stubs: {
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
        'el-icon': { template: '<span><slot /></span>' },
        'el-dropdown': { template: '<div><slot /><slot name="dropdown" /></div>' },
        'el-dropdown-menu': { template: '<div><slot /></div>' },
        'el-dropdown-item': {
          template: '<div class="el-dropdown-item-stub"><slot /></div>',
        },
        GlobalSearch: { template: '<div class="gs-stub" />' },
      },
    },
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  authBox.user = { full_name: '管理员', username: 'admin', role: 'admin', is_superuser: false }
  mockPost.mockResolvedValue({ success: true })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('PageHeader 补充覆盖', () => {
  it('handleBackup 成功 → post + 成功提示 + emit backup-complete；loading 状态复位', async () => {
    const wrapper = mountHeader()
    const vm = wrapper.vm as any
    await vm.handleBackup()
    expect(mockPost).toHaveBeenCalledWith('/system/backup', {
      description: '主页手动备份',
      include_uploads: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('备份创建成功')
    expect(wrapper.emitted('backup-complete')).toBeTruthy()
    expect(vm.backingUp).toBe(false)
    wrapper.unmount()
  })

  it('handleBackup 失败 → 错误提示且不 emit', async () => {
    mockPost.mockRejectedValue(new Error('backup down'))
    const wrapper = mountHeader()
    await wrapper.vm.handleBackup()
    expect(ElMessage.error).toHaveBeenCalledWith('备份失败')
    expect(wrapper.emitted('backup-complete')).toBeFalsy()
    expect((wrapper.vm as any).backingUp).toBe(false)
    wrapper.unmount()
  })

  it('handleMoreCommand：layout → emit toggle-layout；其他命令 → 无 emit', async () => {
    const wrapper = mountHeader()
    const vm = wrapper.vm as any
    vm.handleMoreCommand('layout')
    expect(wrapper.emitted('toggle-layout')).toBeTruthy()
    vm.handleMoreCommand('other')
    expect(wrapper.emitted('toggle-layout')).toHaveLength(1)
    wrapper.unmount()
  })

  // branch@100 真侧 + stmts@101-103：bigscreen 命令走 pushSafe 并提前 return
  it('handleMoreCommand：bigscreen → pushSafe(/bigscreen) 且提前返回（不 emit toggle-layout）', async () => {
    const wrapper = mountHeader()
    const vm = wrapper.vm as any
    vm.handleMoreCommand('bigscreen')
    expect(mockPushSafe).toHaveBeenCalledWith('/bigscreen')
    expect(mockPushSafe).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('toggle-layout')).toBeFalsy()
    wrapper.unmount()
  })

  it('新建项目/数据分析按钮 → pushSafe 导航', async () => {
    const wrapper = mountHeader()
    await wrapper.find('[data-test="btn-new-project"]').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/projects/create')
    await wrapper.find('[data-test="btn-analysis"]').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/data-analysis')
    wrapper.unmount()
  })

  it('displayName：无 full_name → username；两者皆无 → 管理员', () => {
    authBox.user = { full_name: '', username: 'zhangsan', role: 'user' }
    const wrapper = mountHeader()
    expect(wrapper.text()).toContain('zhangsan')

    authBox.user = { username: '', role: 'user' }
    const wrapper2 = mountHeader()
    expect(wrapper2.text()).toContain('管理员')
    wrapper.unmount()
    wrapper2.unmount()
  })

  it('isAdmin：is_superuser 真 → 备份按钮显示；普通用户 → 隐藏', () => {
    authBox.user = { full_name: '超管', username: 's', role: 'viewer', is_superuser: true }
    const wrapper = mountHeader()
    expect(wrapper.find('[data-test="btn-backup"]').exists()).toBe(true)
    wrapper.unmount()

    authBox.user = { full_name: '访客', username: 'v', role: 'viewer', is_superuser: false }
    const wrapper2 = mountHeader()
    expect(wrapper2.find('[data-test="btn-backup"]').exists()).toBe(false)
    wrapper2.unmount()
  })

  it('格式化日期包含中文年月日与星期', () => {
    const wrapper = mountHeader()
    expect((wrapper.vm as any).formattedDate).toMatch(/\d{4}年\d{1,2}月\d{1,2}日 周[日一二三四五六]/)
    wrapper.unmount()
  })
})
