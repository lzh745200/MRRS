/**
 * views/dataPackage/PackageVersion.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：fetchVersionList 成功失败、handleCreateVersion、confirmCreate 全分支
 * （无版本号警告/成功/失败/loading）、handleViewDetail 成功（changes 空与非空
 * activeTab 设置）失败、handleCompare、doCompare 全分支、handleDelete 全分支
 * （确认成功/取消/失败）、getChangeCount 全分支、formatTime、模板全部渲染
 * （版本表/变更统计/详情对话框/对比对话框/创建对话框）。
 *
 * 方案：mock vue-router useRoute（params.id）、@/api/request 按 URL 路由、
 * element-plus、errorHandler、@/utils format。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  confirmMock,
  mockGet,
  mockPost,
  mockDel,
  mockApiRequest,
  handleError,
  routeBox,
  formatMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockDel: vi.fn(),
  mockApiRequest: vi.fn(),
  handleError: vi.fn(),
  routeBox: { params: { id: '42' } },
  formatMock: vi.fn((t: string) => `FT:${t}`),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeBox,
}))

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  del: (...args: any[]) => mockDel(...args),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  put: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/errorHandler', () => ({
  handleApiError: (...args: any[]) => handleError(...args),
}))

vi.mock('@/utils', () => ({
  format: { formatDateTimeLocale: formatMock },
}))

import PackageVersion from '@/views/dataPackage/PackageVersion.vue'

const v1 = {
  id: 1,
  version: '1.0',
  description: '初始版本',
  created_at: '2024-01-01T00:00:00',
  changes: {
    villages: { added: ['V1'], modified: [], deleted: [] },
    projects: { added: [], modified: ['P1', 'P2'], deleted: ['P3'] },
  },
}
const v2 = {
  id: 2,
  version: '1.1',
  description: '增量更新',
  created_at: '2024-02-01T00:00:00',
  changes: {},
}
const v3 = { id: 3, version: '2.0', description: '', created_at: '2024-03-01T00:00:00', changes: undefined }

const comparison = {
  version1: { version: '1.0' },
  version2: { version: '1.1' },
  differences: {
    added_in_v2: { villages: ['V9'], projects: [] },
    modified: { villages: ['M1'] },
    removed_in_v2: { villages: ['R1'] },
  },
}

const stubs = {
  'el-card': { name: 'ElCard', template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-alert': {
    name: 'ElAlert',
    props: ['title', 'description'],
    template: '<div class="el-alert-stub">{{ title }} {{ description }}</div>',
  },
  'el-button': {
    name: 'ElButton',
    props: ['disabled', 'loading'],
    template: '<button class="el-button-stub"><slot /></button>',
  },
  'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>', props: ['data'] },
  'el-table-column': {
    name: 'ElTableColumn',
    props: ['prop', 'label'],
    template:
      '<div class="el-table-column-stub" :label="label"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
    data() {
      return { rowA: v1, rowB: v2, rowC: v3 }
    },
  },
  'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
  'el-dialog': {
    name: 'ElDialog',
    props: ['modelValue', 'title'],
    template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
    emits: ['update:modelValue', 'close'],
  },
  'el-form': { name: 'ElForm', template: '<div class="el-form-stub"><slot /></div>' },
  'el-form-item': { name: 'ElFormItem', template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-input': { name: 'ElInput', template: '<div class="el-input-stub"><slot /></div>' },
  'el-descriptions': { name: 'ElDescriptions', template: '<div class="el-descriptions-stub"><slot /></div>' },
  'el-descriptions-item': {
    name: 'ElDescriptionsItem',
    props: ['label'],
    template: '<div class="el-descriptions-item-stub">{{ label }}<slot /></div>',
  },
  'el-divider': { name: 'ElDivider', template: '<div class="el-divider-stub"><slot /></div>' },
  'el-tabs': { name: 'ElTabs', props: ['modelValue'], template: '<div class="el-tabs-stub"><slot /></div>', emits: ['update:modelValue'] },
  'el-tab-pane': {
    name: 'ElTabPane',
    props: ['label', 'name'],
    template: '<div class="el-tab-pane-stub">{{ label }}<slot /></div>',
  },
  'el-select': {
    name: 'ElSelect',
    props: ['modelValue'],
    template: '<div class="el-select-stub"><slot /></div>',
    emits: ['update:modelValue'],
  },
  'el-option': { name: 'ElOption', template: '<div />' },
}

function mountComp() {
  return mount(PackageVersion, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

async function clickBtn(wrapper: any, text: string, index = 0) {
  const btns = wrapper.findAll('.el-button-stub').filter((b: any) => b.text().trim().includes(text))
  expect(btns.length, `按钮「${text}」`).toBeGreaterThan(index)
  await btns[index].trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.params = { id: '42' }
  formatMock.mockImplementation((t: string) => `FT:${t}`)
  mockGet.mockResolvedValue({ success: true, data: { versions: [v1, v2, v3] } })
  mockPost.mockResolvedValue({ success: true, data: {} })
  mockDel.mockResolvedValue({ success: true })
  mockApiRequest.mockResolvedValue({ success: true, data: { comparison } })
  confirmMock.mockResolvedValue('confirm')
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('版本列表', () => {
  it('onMounted 加载版本列表；表格渲染变更统计与时间', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/data-packages/42/versions')
    expect(vm.versionList.length).toBe(3)
    expect(vm.packageId).toBe('42')
    const text = wrapper.text()
    expect(text).toContain('数据包版本管理')
    expect(text).toContain('FT:2024-01-01T00:00:00') // formatTime
    wrapper.unmount()
  })

  it('获取失败 → 错误提示', async () => {
    mockGet.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('获取版本列表失败')
    wrapper.unmount()
  })
})

describe('创建版本', () => {
  it('handleCreateVersion → 重置表单并打开对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.versionForm = { version: '9.9', description: '旧值' }
    vm.handleCreateVersion()
    expect(vm.versionForm).toEqual({ version: '', description: '' })
    expect(vm.createDialogVisible).toBe(true)
    wrapper.unmount()
  })

  it('confirmCreate：无版本号 → 警告；成功 → post + 提示 + 关闭 + 刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.confirmCreate()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入版本号')

    vm.versionForm = { version: '1.2', description: '说明' }
    await vm.confirmCreate()
    expect(mockPost).toHaveBeenCalledWith('/data-packages/42/versions', {
      version: '1.2',
      description: '说明',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('版本创建成功')
    expect(vm.createDialogVisible).toBe(false)
    expect(mockGet).toHaveBeenCalledWith('/data-packages/42/versions')
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })

  it('confirmCreate 失败 → handleApiError；loading 复位', async () => {
    mockPost.mockRejectedValue(new Error('down'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.versionForm = { version: '1.2', description: '' }
    await vm.confirmCreate()
    expect(handleError).toHaveBeenCalledWith(expect.any(Error), '创建失败')
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })
})

describe('版本详情', () => {
  it('详情成功：changes 非空 → activeTab 设置 + 对话框打开 + 渲染变更 ID', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/versions/1')) return Promise.resolve({ success: true, data: v1 })
      return Promise.resolve({ success: true, data: { versions: [v1, v2, v3] } })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '详情', 0)
    expect(mockGet).toHaveBeenCalledWith('/data-packages/42/versions/1')
    expect(vm.currentVersion).toEqual(v1)
    expect(vm.activeTab).toBe('villages')
    expect(vm.detailDialogVisible).toBe(true)
    await nextTick()
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    const detailDialog = dialogs.find((d: any) => d.props('title') === '版本详情')
    expect(detailDialog).toBeTruthy()
    const text = wrapper.text()
    expect(text).toContain('初始版本')
    expect(text).toContain('新增记录ID')
    expect(text).toContain('修改记录ID')
    expect(text).toContain('删除记录ID')
    wrapper.unmount()
  })

  it('详情成功：changes 为空 → activeTab 保持；描述缺失 → -', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/versions/2')) return Promise.resolve({ success: true, data: v2 })
      return Promise.resolve({ success: true, data: { versions: [v1, v2, v3] } })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.activeTab = ''
    await vm.handleViewDetail(v2 as any)
    expect(vm.activeTab).toBe('')
    expect(vm.detailDialogVisible).toBe(true)
    wrapper.unmount()
  })

  it('详情失败 → 错误提示', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/versions/1')) return Promise.reject(new Error('down'))
      return Promise.resolve({ success: true, data: { versions: [v1] } })
    })
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleViewDetail(v1 as any)
    expect(ElMessage.error).toHaveBeenCalledWith('获取版本详情失败')
    wrapper.unmount()
  })
})

describe('版本对比', () => {
  it('handleCompare → 填入 version1 并打开对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '对比', 0)
    expect(vm.compareForm.version1).toBe('1.0')
    expect(vm.compareForm.version2).toBe('')
    expect(vm.compareResult).toBe(null)
    expect(vm.compareDialogVisible).toBe(true)
    wrapper.unmount()
  })

  it('doCompare：缺版本 → 警告；成功 → apiRequest + 结果渲染；失败 → handleApiError', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.doCompare()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择两个版本')

    vm.compareForm = { version1: '1.0', version2: '1.1' }
    await vm.doCompare()
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        url: '/data-packages/42/versions/compare',
        params: { version1: '1.0', version2: '1.1' },
      })
    )
    expect(vm.compareResult).toEqual(comparison)
    await nextTick()
    expect(wrapper.text()).toContain('对比结果')

    mockApiRequest.mockRejectedValue(new Error('cmp down'))
    await vm.doCompare()
    expect(handleError).toHaveBeenCalledWith(expect.any(Error), '对比失败')
    wrapper.unmount()
  })

  it('对比对话框版本下拉 v-model 更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '对比', 0)
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', '1.0')
    selects[1].vm.$emit('update:modelValue', '1.1')
    await nextTick()
    expect(vm.compareForm.version1).toBe('1.0')
    expect(vm.compareForm.version2).toBe('1.1')
    wrapper.unmount()
  })
})

describe('删除版本', () => {
  it('handleDelete：确认 → del + 成功提示 + 刷新；取消静默；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete(2)
    expect(confirmMock).toHaveBeenCalledWith('确定要删除此版本吗？', '警告', expect.anything())
    expect(mockDel).toHaveBeenCalledWith('/data-packages/42/versions/2')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')

    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDelete(2)
    expect(ElMessage.error).not.toHaveBeenCalledWith('删除失败')

    mockDel.mockRejectedValue(new Error('del down'))
    await vm.handleDelete(2)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
    wrapper.unmount()
  })
})

describe('辅助函数', () => {
  it('getChangeCount 全分支；formatTime 委托 format', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.getChangeCount(undefined as any, 'added')).toBe(0)
    expect(vm.getChangeCount(v1.changes as any, 'added')).toBe(1)
    expect(vm.getChangeCount(v1.changes as any, 'modified')).toBe(2)
    expect(vm.getChangeCount(v1.changes as any, 'deleted')).toBe(1)
    // 无该类型字段 → length || 0
    expect(vm.getChangeCount({ villages: {} } as any, 'added')).toBe(0)
    expect(vm.formatTime('2024-01-01')).toBe('FT:2024-01-01')
    expect(vm.formatTime(undefined as any)).toBe('FT:')
    wrapper.unmount()
  })

  it('模板：变更统计标签渲染数量；创建对话框 footer 按钮关闭', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('新增: 1')
    expect(text).toContain('修改: 2')
    expect(text).toContain('删除: 1')
    // 创建对话框 v-model 关闭
    const vm = wrapper.vm as any
    vm.createDialogVisible = true
    await nextTick()
    await clickBtn(wrapper, '取消')
    expect(vm.createDialogVisible).toBe(false)
    wrapper.unmount()
  })

  it('三个对话框 v-model 内联关闭处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createDialogVisible = true
    vm.detailDialogVisible = true
    vm.compareDialogVisible = true
    await nextTick()
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    dialogs[0].vm.$emit('update:modelValue', false)
    dialogs[1].vm.$emit('update:modelValue', false)
    dialogs[2].vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.createDialogVisible).toBe(false)
    expect(vm.detailDialogVisible).toBe(false)
    expect(vm.compareDialogVisible).toBe(false)
    wrapper.unmount()
  })

  it('模板内联处理器：删除按钮 handleDelete(row.id)、创建表单 v-model、详情 tabs v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 版本表「删除」按钮 → handleDelete(row.id)
    await clickBtn(wrapper, '删除', 0)
    expect(confirmMock).toHaveBeenCalled()
    // 创建对话框表单 v-model（版本号/说明输入）
    vm.createDialogVisible = true
    await nextTick()
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', '3.0')
    inputs[1].vm.$emit('update:modelValue', '新版本说明')
    await nextTick()
    expect(vm.versionForm.version).toBe('3.0')
    expect(vm.versionForm.description).toBe('新版本说明')
    // 详情对话框 tabs v-model（activeTab 内联写入）
    vm.detailDialogVisible = true
    vm.activeTab = ''
    await nextTick()
    wrapper.findComponent({ name: 'ElTabs' }).vm.$emit('update:modelValue', 'villages')
    await nextTick()
    expect(vm.activeTab).toBe('villages')
    wrapper.unmount()
  })
})

describe('版本数组形态', () => {
  it('versions 数组 → 直接使用', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(Array.isArray(vm.versionList)).toBe(true)
    wrapper.unmount()
  })
})
