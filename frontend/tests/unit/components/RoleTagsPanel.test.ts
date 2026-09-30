/**
 * RoleTagsPanel.vue 测试
 * 覆盖：已分配/可选角色渲染、assignRole、removeRole、错误分支、暴露方法
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import RoleTagsPanel from '@/components/permission/RoleTagsPanel.vue'

enableAutoUnmount(afterEach)

vi.mock('@element-plus/icons-vue', () => ({
  InfoFilled: { template: '<i class="icon-info" />' },
}))

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  apiRequest: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  messageBox: { confirm: vi.fn() },
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

const mockGet = mocks.get
const mockPost = mocks.post
const mockApiRequest = mocks.apiRequest
const mockMessage = mocks.message

vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mocks.get(...a),
  post: (...a: any[]) => mocks.post(...a),
  apiRequest: (...a: any[]) => mocks.apiRequest(...a),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('element-plus', () => ({ ElMessage: mocks.message, ElMessageBox: mocks.messageBox }))
vi.mock('@/utils/logger', () => ({ logger: mocks.logger }))

const allRoles = [
  { id: 'r1', name: '管理员', description: '全部权限', is_system: true },
  { id: 'r2', name: '帮扶员', description: '帮扶相关' },
  { id: 'r3', name: '访客', is_active: false },
  { id: 'r4', name: '审计员' },
]

const ElSelectStub = {
  props: ['modelValue', 'placeholder'],
  emits: ['update:modelValue', 'change'],
  methods: {
    onChange(e: Event) {
      const val = (e.target as HTMLSelectElement).value
      this.$emit('update:modelValue', val)
      this.$emit('change', val)
    },
  },
  template: '<select class="stub-select" :value="modelValue" @change="onChange"><slot /></select>',
}

const ElOptionStub = {
  props: ['label', 'value'],
  template: '<option :value="value">{{ label }}</option>',
}

const ElTagStub = {
  props: {
    closable: { type: Boolean, default: false },
    type: String,
    size: String,
  },
  emits: ['close'],
  template:
    '<span class="stub-tag"><slot /><button v-if="closable" class="tag-close" @click="$emit(\'close\')">x</button></span>',
}

function mountPanel(props: Record<string, unknown> = {}) {
  return mount(RoleTagsPanel, {
    props,
    global: {
      stubs: {
        'el-select': ElSelectStub,
        'el-option': ElOptionStub,
        'el-tag': ElTagStub,
        'el-alert': { template: '<div class="stub-alert"><slot /></div>' },
        'el-tooltip': { template: '<span class="stub-tooltip"><slot /></span>' },
        'el-divider': { template: '<hr class="stub-divider" />' },
        'el-icon': { template: '<i class="stub-icon"><slot /></i>' },
      },
    },
  })
}

describe('RoleTagsPanel.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ data: [{ id: 'r1', name: '管理员', description: 'x', is_system: true }] })
    mockPost.mockResolvedValue({})
    mockApiRequest.mockResolvedValue({})
    // 撤销角色需二次确认：默认确认通过
    mocks.messageBox.confirm.mockResolvedValue('confirm')
  })

  it('渲染已分配角色与可选角色（排除已分配与停用）', async () => {
    const wrapper = mountPanel({ userId: 1, allRoles })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()

    // 已分配 r1（系统角色）
    expect(mockGet).toHaveBeenCalledWith('/rbac/user/1/roles')
    const tags = wrapper.findAll('span.stub-tag')
    expect(tags).toHaveLength(1)
    expect(tags[0].text()).toContain('管理员')
    expect(tags[0].text()).toContain('(系统)')

    // 可选角色：r2、r4（r1 已分配、r3 停用）
    const options = wrapper.findAll('option')
    expect(options).toHaveLength(2)
    expect(options[0].text()).toContain('帮扶员')
    expect(options[0].text()).toContain('帮扶相关')
    expect(options[1].text()).toBe('审计员')
  })

  it('无 allRoles 或空数据时显示空提示', async () => {
    mockGet.mockResolvedValueOnce({ data: [] })
    const wrapper = mountPanel({ userId: 1, allRoles: [] })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()
    expect(wrapper.text()).toContain('暂未分配任何 RBAC 角色')
    expect(wrapper.text()).toContain('暂无可分配的角色')

    const wrapper2 = mountPanel({ userId: 1 })
    await flushPromises()
    expect(wrapper2.text()).toContain('暂无可分配的角色')
  })

  // 2026-09-30 深审修复：原先 catch 一律 assignedRoles=[]，403/网络/5xx 与"无角色"
  // 不可区分（管理员会误判为没有角色）。现改为保留旧值 + 显式告警 + logger.error。
  it('loadAssignedRoles 失败 → 显式告警且不清空已加载数据', async () => {
    const wrapper = mountPanel({ userId: 1, allRoles })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()
    expect(wrapper.text()).toContain('管理员')

    mockGet.mockRejectedValueOnce(new Error('boom'))
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()
    // 旧值保留 + 失败提示可见（不再伪装成"暂无角色"）
    expect(wrapper.text()).toContain('管理员')
    expect(wrapper.find('.load-failed-hint').exists()).toBe(true)
    expect(mocks.logger.error).toHaveBeenCalledWith(
      '[RoleTagsPanel] 已分配角色加载失败:',
      expect.any(Error)
    )
  })

  it('loadAssignedRoles 返回无 data 结构时安全处理', async () => {
    // 直接返回数组（无 data 包裹）→ 使用 res 本身
    mockGet.mockResolvedValueOnce([{ id: 'x', name: '直返角色' }])
    const wrapper = mountPanel({ userId: 1, allRoles })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()
    expect(wrapper.text()).toContain('直返角色')

    // res 整体为 falsy/非数组（0）→ 视为畸形载荷：走失败分支（显式告警）而非静默空
    mockGet.mockResolvedValueOnce(0)
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()
    expect(wrapper.find('.load-failed-hint').exists()).toBe(true)
  })

  it('loadAssignedRoles 载荷为非数组对象 → 不渲染、不抛错（走失败分支）', async () => {
    mockGet.mockResolvedValueOnce({ data: { roles: [] } })
    const wrapper = mountPanel({ userId: 1, allRoles })
    await expect((wrapper.vm as any).loadAssignedRoles()).resolves.toBeUndefined()
    await flushPromises()
    expect(wrapper.find('.load-failed-hint').exists()).toBe(true)
  })

  it('assignRole 成功：post + 刷新 + emit assigned + 成功提示', async () => {
    mockGet
      .mockResolvedValueOnce({ data: [{ id: 'r1', name: '管理员', description: 'x', is_system: true }] })
      .mockResolvedValue({ data: [
        { id: 'r1', name: '管理员', description: 'x', is_system: true },
        { id: 'r2', name: '帮扶员', description: '帮扶相关' },
      ] })
    const wrapper = mountPanel({ userId: 1, allRoles })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()

    await wrapper.find('select.stub-select').setValue('r2')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith('/rbac/assign/role', { user_id: 1, role_id: 'r2' })
    // 刷新后 r2 已分配，从可选列表移除 → 仅剩 r4
    const options = wrapper.findAll('option')
    expect(options).toHaveLength(1)
    expect(options[0].text()).toBe('审计员')
    expect(wrapper.emitted('assigned')).toHaveLength(1)
    expect(mockMessage.success).toHaveBeenCalledWith('角色分配成功')
  })

  it('assignRole 空 roleId 时直接返回', async () => {
    const wrapper = mountPanel({ userId: 1, allRoles: [] })
    await flushPromises()
    await wrapper.find('select.stub-select').setValue('')
    await flushPromises()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('assignRole 失败：错误提示（detail / 默认）', async () => {
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '分配失败' } } })
    const wrapper = mountPanel({ userId: 1, allRoles })
    await flushPromises()
    await wrapper.find('select.stub-select').setValue('r2')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('分配失败')

    mockPost.mockRejectedValueOnce(new Error('x'))
    await wrapper.find('select.stub-select').setValue('r4')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('角色分配失败')
  })

  it('removeRole 成功：DELETE + 刷新 + emit removed + 提示', async () => {
    const wrapper = mountPanel({ userId: 1, allRoles })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()

    await wrapper.find('button.tag-close').trigger('click')
    await flushPromises()

    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'DELETE',
      url: '/rbac/revoke/role',
      data: { user_id: 1, role_id: 'r1' },
    })
    expect(wrapper.emitted('removed')).toHaveLength(1)
    expect(mockMessage.success).toHaveBeenCalledWith('角色「管理员」已移除')
  })

  it('removeRole 失败：错误提示（detail / 默认）', async () => {
    mockApiRequest.mockRejectedValueOnce({ response: { data: { detail: '撤销失败' } } })
    const wrapper = mountPanel({ userId: 1, allRoles })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()
    await wrapper.find('button.tag-close').trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('撤销失败')

    mockApiRequest.mockRejectedValueOnce(new Error('x'))
    await wrapper.find('button.tag-close').trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('角色移除失败')
  })

  // ── 2026-09-30 深审修复：撤销角色二次确认 ──

  it('removeRole 先二次确认（系统角色提示影响面），确认后才发撤销请求', async () => {
    const wrapper = mountPanel({ userId: 1, allRoles })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()
    await wrapper.find('button.tag-close').trigger('click')
    await flushPromises()

    expect(mocks.messageBox.confirm).toHaveBeenCalledWith(
      '「管理员」是系统角色，撤销可能影响该用户既有权限。确认移除？',
      '移除角色',
      { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' }
    )
    expect(mockApiRequest).toHaveBeenCalled()
  })

  it('removeRole 用户取消确认 → 不发撤销请求、不提示成功', async () => {
    mocks.messageBox.confirm.mockRejectedValueOnce('cancel')
    const wrapper = mountPanel({ userId: 1, allRoles })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()
    await wrapper.find('button.tag-close').trigger('click')
    await flushPromises()

    expect(mockApiRequest).not.toHaveBeenCalled()
    expect(mockMessage.success).not.toHaveBeenCalled()
    expect(wrapper.emitted('removed')).toBeUndefined()
  })

  it('非系统角色的确认文案不含"系统角色"字样', async () => {
    mockGet.mockResolvedValueOnce({ data: [{ id: 'r2', name: '帮扶员' }] })
    const wrapper = mountPanel({ userId: 1, allRoles })
    await (wrapper.vm as any).loadAssignedRoles()
    await flushPromises()
    await wrapper.find('button.tag-close').trigger('click')
    await flushPromises()
    expect(mocks.messageBox.confirm).toHaveBeenCalledWith(
      '确认移除角色「帮扶员」？',
      '移除角色',
      expect.any(Object)
    )
  })

  it('暴露 loadAssignedRoles 与 assignedRoles', async () => {
    const wrapper = mountPanel({ userId: 1, allRoles })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(typeof vm.loadAssignedRoles).toBe('function')
    await vm.loadAssignedRoles()
    await flushPromises()
    expect(vm.assignedRoles).toHaveLength(1)
  })
})
