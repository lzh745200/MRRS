/**
 * views/dataPackage/IncrementalUpdate.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：fetchPackageList 成功（base/update 分流）与失败、handleDetectChanges 全分支
 * （无 base/无类型/成功/失败）、handleExport 全分支（成功下载/下载失败/无 download_url/
 * 请求失败）、handleImport 预览与导入、handlePackageChange、changesByType 计算、
 * onMounted、模板全部条件渲染（变更摘要/导入结果两态/预览提示）。
 *
 * 方案：mock '@/api/request'（get/post）按 URL 路由、element-plus ElMessage、
 * errorHandler.handleApiError、AuthStorage.getToken、全局 fetch。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, mockGet, mockPost, handleError, authBox } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  handleError: vi.fn(),
  authBox: { token: 'token-abc' },
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  default: {},
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/errorHandler', () => ({
  handleApiError: (...args: any[]) => handleError(...args),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: () => authBox.token },
}))

import IncrementalUpdate from '@/views/dataPackage/IncrementalUpdate.vue'

const basePkg = { id: 1, package_code: 'PKG-BASE', description: '基础包', type: 'full' }
const basePkg2 = { id: 4, package_code: 'PKG-BASE2', type: 'full' }
const updPkg = { id: 2, package_code: 'PKG-UPD', description: '增量包', type: 'update' }
const updPkg2 = { id: 3, package_code: 'PKG-UPD2', type: 'update' }

const changesSummary = {
  total_added: 10,
  total_modified: 3,
  total_deleted: 1,
  by_type: {
    villages: { added: 5, modified: 2, deleted: 0, total: 7 },
    projects: { added: 5, modified: 1, deleted: 1, total: 7 },
  },
}

const stubs = {
  'el-card': { name: 'ElCard', template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-alert': {
    name: 'ElAlert',
    props: ['title', 'description'],
    template: '<div class="el-alert-stub">{{ title }} {{ description }}</div>',
  },
  'el-tabs': {
    name: 'ElTabs',
    props: ['modelValue'],
    template: '<div class="el-tabs-stub"><slot /></div>',
    emits: ['update:modelValue'],
  },
  'el-tab-pane': {
    name: 'ElTabPane',
    props: ['label', 'name'],
    template: '<div class="el-tab-pane-stub">{{ label }}<slot /></div>',
  },
  'el-form': { name: 'ElForm', template: '<div class="el-form-stub"><slot /></div>' },
  'el-form-item': { name: 'ElFormItem', template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-select': {
    name: 'ElSelect',
    props: ['modelValue'],
    template: '<div class="el-select-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-option': { name: 'ElOption', template: '<div />' },
  'el-checkbox-group': {
    name: 'ElCheckboxGroup',
    props: ['modelValue'],
    template: '<div class="el-checkbox-group-stub"><slot /></div>',
    emits: ['update:modelValue'],
  },
  'el-checkbox': {
    name: 'ElCheckbox',
    props: ['label', 'value'],
    template: '<span class="el-checkbox-stub"><slot /></span>',
    emits: ['update:modelValue', 'change'],
  },
  'el-input': { name: 'ElInput', template: '<div class="el-input-stub"><slot /></div>' },
  'el-button': { name: 'ElButton', template: '<button class="el-button-stub"><slot /></button>' },
  'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
  'el-descriptions': { name: 'ElDescriptions', template: '<div class="el-descriptions-stub"><slot /></div>' },
  'el-descriptions-item': {
    name: 'ElDescriptionsItem',
    props: ['label'],
    template: '<div class="el-descriptions-item-stub">{{ label }}<slot /></div>',
  },
  'el-divider': { name: 'ElDivider', template: '<div class="el-divider-stub"><slot /></div>' },
  'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>', props: ['data'] },
  'el-table-column': {
    name: 'ElTableColumn',
    props: ['prop', 'label'],
    template: '<div class="el-table-column-stub">{{ label }}<slot /></div>',
  },
  'el-switch': { name: 'ElSwitch', template: '<div class="el-switch-stub" />' },
}

function mountComp() {
  return mount(IncrementalUpdate, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGet.mockResolvedValue({
    data: { items: [basePkg, basePkg2, updPkg, updPkg2] },
  })
  mockPost.mockResolvedValue({ success: true, data: {} })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(['x'])) }))
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:mock'), revokeObjectURL: vi.fn() })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('数据包列表', () => {
  it('onMounted 加载：基础包与增量包分流；无 items → 空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/data-packages')
    expect(vm.packageList.map((p: any) => p.id)).toEqual([1, 4])
    expect(vm.incrementalPackages.map((p: any) => p.id)).toEqual([2, 3])
    wrapper.unmount()

    mockGet.mockResolvedValue({ data: {} })
    const wrapper2 = mountComp()
    await flushPromises()
    expect((wrapper2.vm as any).packageList).toEqual([])
    wrapper2.unmount()
  })

  it('加载失败 → 错误提示', async () => {
    mockGet.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('获取数据包列表失败')
    wrapper.unmount()
  })
})

describe('检测变更', () => {
  it('无基础包 → 警告；无数据类型 → 警告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDetectChanges()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择基础数据包')
    vm.exportForm.base_package_id = 1
    vm.exportForm.data_types = []
    await vm.handleDetectChanges()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择数据类型')
    wrapper.unmount()
  })

  it('检测成功 → 变更摘要写入 + 成功提示；失败 → handleApiError', async () => {
    mockPost.mockResolvedValue({ success: true, data: { summary: changesSummary } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.base_package_id = 1
    await vm.handleDetectChanges()
    expect(mockPost).toHaveBeenCalledWith('/data-packages/incremental/detect-changes', null, {
      params: {
        org_id: null,
        data_types: ['villages', 'projects', 'funds', 'schools'],
        base_package_id: 1,
      },
    })
    expect(vm.changesSummary).toEqual(changesSummary)
    expect(ElMessage.success).toHaveBeenCalledWith('变更检测完成')

    mockPost.mockRejectedValue(new Error('down'))
    await vm.handleDetectChanges()
    expect(handleError).toHaveBeenCalledWith(expect.any(Error), '检测变更失败')
    wrapper.unmount()
  })

  it('changesByType 计算：有 by_type → 映射行；无 → 空数组', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.changesSummary = changesSummary
    expect(vm.changesByType).toEqual([
      { type: 'villages', added: 5, modified: 2, deleted: 0, total: 7 },
      { type: 'projects', added: 5, modified: 1, deleted: 1, total: 7 },
    ])
    vm.changesSummary = null
    expect(vm.changesByType).toEqual([])
    // 模板：变更摘要卡片渲染
    vm.changesSummary = changesSummary
    await nextTick()
    expect(wrapper.text()).toContain('变更摘要')
    expect(wrapper.text()).toContain('10')
    wrapper.unmount()
  })
})

describe('导出增量包', () => {
  it('导出成功 + download_url → fetch 下载 → 刷新列表并清空摘要', async () => {
    vi.useFakeTimers()
    mockPost.mockResolvedValue({
      success: true,
      data: { download_url: '/api/download/pkg', filename: '增量更新包.zip' },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.changesSummary = changesSummary
    await vm.handleExport()
    expect(mockPost).toHaveBeenCalledWith('/data-packages/incremental/export', {
      org_id: null,
      data_types: ['villages', 'projects', 'funds', 'schools'],
      base_package_id: null,
      description: '增量更新包',
    })
    expect(global.fetch).toHaveBeenCalledWith('/api/download/pkg', {
      headers: { Authorization: 'Bearer token-abc' },
    })
    vi.advanceTimersByTime(1100)
    expect(URL.revokeObjectURL).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('增量包导出成功')
    expect(vm.changesSummary).toBe(null)
    expect(vm.packageList.length).toBe(2)
    vi.useRealTimers()
    wrapper.unmount()
  })

  it('下载响应非 ok → 提示下载失败；fetch 抛错 → 提示下载失败', async () => {
    mockPost.mockResolvedValue({ success: true, data: { download_url: '/dl' } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vi.mocked(fetch).mockResolvedValueOnce({ ok: false } as any)
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('下载增量包失败')

    vi.mocked(fetch).mockRejectedValueOnce(new Error('net'))
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('download_url 存在但无 filename → 使用默认文件名「增量更新包.zip」', async () => {
    vi.useFakeTimers()
    mockPost.mockResolvedValue({ success: true, data: { download_url: '/dl2' } })
    const wrapper = mountComp()
    await flushPromises()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await (wrapper.vm as any).handleExport()
    vi.advanceTimersByTime(1100)
    expect(clickSpy).toHaveBeenCalled()
    expect(URL.revokeObjectURL).toHaveBeenCalled()
    vi.useRealTimers()
    wrapper.unmount()
  })

  it('导出成功但无 download_url → 跳过下载仅刷新', async () => {
    mockPost.mockResolvedValue({ success: true, package_id: 1 })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleExport()
    expect(global.fetch).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('增量包导出成功')
    wrapper.unmount()
  })

  it('导出请求失败 → handleApiError', async () => {
    mockPost.mockRejectedValue(new Error('export down'))
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleExport()
    expect(handleError).toHaveBeenCalledWith(expect.any(Error), '导出失败')
    wrapper.unmount()
  })

  it('description 有值时使用用户输入', async () => {
    mockPost.mockResolvedValue({ success: true, data: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.description = '自定义描述'
    await vm.handleExport()
    const call = mockPost.mock.calls.find((c: any) => c[0] === '/data-packages/incremental/export')
    expect(call[1].description).toBe('自定义描述')
    wrapper.unmount()
  })
})

describe('导入增量包', () => {
  it('预览模式（apply=false）→ 预览完成；导入模式（apply=true）→ 导入成功', async () => {
    mockPost.mockResolvedValue({
      success: true,
      preview_only: true,
      stats: { added: 1, modified: 2, deleted: 0 },
      summary: { total_added: 1, total_modified: 2, total_deleted: 0 },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importForm.package_id = 2
    vm.importForm.apply_changes = false
    await vm.handleImport()
    expect(mockPost).toHaveBeenCalledWith('/data-packages/incremental/import', {
      package_id: 2,
      apply_changes: false,
    })
    expect(vm.importResult.preview_only).toBe(true)
    expect(ElMessage.success).toHaveBeenCalledWith('预览完成')
    await nextTick()
    expect(wrapper.text()).toContain('预览结果')
    expect(wrapper.text()).toContain('这是预览模式，数据未实际导入')
    expect(wrapper.text()).toContain('1')

    vm.importForm.apply_changes = true
    mockPost.mockResolvedValue({ success: true, preview_only: false })
    await vm.handleImport()
    expect(ElMessage.success).toHaveBeenCalledWith('导入成功')
    await nextTick()
    expect(wrapper.text()).toContain('导入结果')
    wrapper.unmount()
  })

  it('导入失败 → handleApiError', async () => {
    mockPost.mockRejectedValue(new Error('import down'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importForm.package_id = 2
    await vm.handleImport()
    expect(handleError).toHaveBeenCalledWith(expect.any(Error), '操作失败')
    wrapper.unmount()
  })

  it('选择增量包变化 → 清空导入结果', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importResult = { preview_only: true }
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    // 第二个 el-select 是导入增量包下拉（@change=handlePackageChange）
    selects[1].vm.$emit('update:modelValue', 2)
    selects[1].vm.$emit('change', 2)
    await nextTick()
    expect(vm.importResult).toBe(null)
    wrapper.unmount()
  })

  it('模板 v-model 内联处理器：tabs/基础包下拉/类型复选/描述输入/应用开关', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // el-tabs v-model
    wrapper.findComponent({ name: 'ElTabs' }).vm.$emit('update:modelValue', 'import')
    await nextTick()
    expect(vm.activeTab).toBe('import')
    // 基础数据包下拉 v-model
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 1)
    await nextTick()
    expect(vm.exportForm.base_package_id).toBe(1)
    // 数据类型复选 v-model
    wrapper.findComponent({ name: 'ElCheckboxGroup' }).vm.$emit('update:modelValue', ['villages'])
    await nextTick()
    expect(vm.exportForm.data_types).toEqual(['villages'])
    // 描述输入 v-model
    wrapper.findComponent({ name: 'ElInput' }).vm.$emit('update:modelValue', '备注内容')
    await nextTick()
    expect(vm.exportForm.description).toBe('备注内容')
    // 应用变更开关 v-model
    wrapper.findComponent({ name: 'ElSwitch' }).vm.$emit('update:modelValue', true)
    await nextTick()
    expect(vm.importForm.apply_changes).toBe(true)
    // 按钮文案三元两侧
    vm.importForm.apply_changes = false
    await nextTick()
    expect(wrapper.text()).toContain('预览变更')
    vm.importForm.apply_changes = true
    await nextTick()
    expect(wrapper.text()).toContain('导入增量包')
    wrapper.unmount()
  })

  it('导入结果无 stats/summary → 不渲染描述块（仅标题）', async () => {
    mockPost.mockResolvedValue({ success: true, preview_only: false })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importForm.package_id = 2
    await vm.handleImport()
    await nextTick()
    wrapper.unmount()
  })
})

describe('响应形态收尾', () => {
  it('package 列表数组 / changes 摘要 / message-only / package_id / total_records', async () => {
    mockPost.mockResolvedValue({ success: true, data: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    ;(mockGet as any).mockResolvedValueOnce([{ id: 1, name: 'p1', type: 'full' }])
    await (vm as any).fetchPackageList()
    expect(vm.packageList.length).toBeGreaterThan(0)
    ;(mockPost as any).mockResolvedValueOnce({
      success: true,
      changes: [{ id: 1 }],
      by_type: { village: { added: 1, modified: 0, deleted: 0, total: 1 } },
      total_added: 1,
      total_modified: 0,
      total_deleted: 0,
    })
    vm.exportForm.base_package_id = 1
    await vm.handleDetectChanges()
    expect(vm.changesSummary).toBeTruthy()
    ;(mockPost as any).mockResolvedValueOnce({ message: '无变更' })
    await vm.handleDetectChanges()
    expect(ElMessage.info).toHaveBeenCalledWith('未检测到变更')
    ;(mockPost as any).mockResolvedValueOnce({ success: true, package_id: 2 })
    vm.importForm.package_id = 1
    await vm.handleImport()
    expect(vm.importResult.package_id).toBe(2)
    ;(mockPost as any).mockResolvedValueOnce({ success: true, total_records: 5 })
    await vm.handleImport()
    expect(vm.importResult.total_records).toBe(5)
    wrapper.unmount()
  })
})

describe('分支收尾', () => {
  it('导出 message-only / 导入 success===true', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.base_package_id = 1
    ;(mockPost as any).mockResolvedValueOnce({ message: '导出被拒' })
    await vm.handleExport()
    expect(ElMessage.warning).toHaveBeenCalledWith('导出被拒')
    vm.importForm.package_id = 1
    ;(mockPost as any).mockResolvedValueOnce({ success: true, message: '仅成功' })
    await vm.handleImport()
    expect(vm.importResult).toBeTruthy()
    ;(mockPost as any).mockResolvedValueOnce({ message: '导入被拒' })
    await vm.handleImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('导入被拒')
    wrapper.unmount()
  })
})
