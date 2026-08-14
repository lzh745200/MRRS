/**
 * views/dataSync/Export.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：selectAllModules/clearModules、handleExport 全验证分支（无模块/无密码/密码过短/不一致）、
 * 加密导出成功（full/selective + since）、未加密旧版导出、response.success=false、
 * 异常（message/兜底）、handleDownload/ByName 成功失败、loadExportHistory（成功/失败）、
 * formatSize 三分支、formatDate、
 * 模板：radio/date-picker/checkbox-group/switch/input v-model、开始导出按钮、历史行下载。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  mockExportData,
  mockExportEncryptedData,
  mockDownloadExportPackage,
  mockGetSyncLogs,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockExportData: vi.fn(),
  mockExportEncryptedData: vi.fn(),
  mockDownloadExportPackage: vi.fn(),
  mockGetSyncLogs: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/dataSync', () => ({
  exportData: mockExportData,
  exportEncryptedData: mockExportEncryptedData,
  downloadExportPackage: mockDownloadExportPackage,
  getSyncLogs: mockGetSyncLogs,
}))

import ExportView from '@/views/dataSync/Export.vue'

const rowA = { package_name: 'pkg_a.rrs', total_records: 10, size: 500, created_at: '2024-06-01 10:00:00', user_name: '张三' }
const rowB = { package_name: 'pkg_b.rrs', total_records: 20, size: 2048, created_at: '2024-06-02 11:00:00', user_name: '李四' }
const rowC = { package_name: 'pkg_c.rrs', total_records: 30, size: 5 * 1024 * 1024, created_at: '2024-06-03 12:00:00', user_name: '王五' }

function mountComp() {
  return mount(ExportView, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return { rowA, rowB, rowC }
          },
        },
        'el-radio-group': {
          name: 'ElRadioGroup',
          template: '<div class="el-radio-group-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-date-picker': {
          name: 'ElDatePicker',
          template: '<div class="el-date-picker-stub" />',
          emits: ['update:modelValue'],
        },
        'el-checkbox-group': {
          name: 'ElCheckboxGroup',
          template: '<div class="el-checkbox-group-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-switch': {
          name: 'ElSwitch',
          props: ['modelValue'],
          template:
            '<button class="el-switch-stub" @click="$emit(\'update:modelValue\', !modelValue)" />',
        },
        'el-input': {
          name: 'ElInput',
          template: '<div class="el-input-stub" />',
          emits: ['update:modelValue'],
        },
        'el-form': { name: 'ElForm', template: '<div class="el-form-stub"><slot /></div>' },
        'el-form-item': {
          name: 'ElFormItem',
          template: '<div class="el-form-item-stub"><slot /></div>',
        },
        'el-checkbox': {
          name: 'ElCheckbox',
          template: '<div class="el-checkbox-stub" />',
          emits: ['update:modelValue'],
        },
      },
    },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, text).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGetSyncLogs.mockResolvedValue({ success: true, items: [rowA, rowB, rowC] })
  mockExportEncryptedData.mockResolvedValue({
    success: true,
    total_records: 99,
    package_name: 'pkg_x.rrs',
  })
  mockExportData.mockResolvedValue({ success: true, total_records: 5, package_name: 'old.zip' })
  mockDownloadExportPackage.mockResolvedValue(undefined)
})

describe('挂载与历史', () => {
  it('onMounted：加载历史 + 默认全选模块', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetSyncLogs).toHaveBeenCalledWith({ action: 'export', page: 1, page_size: 20 })
    expect(vm.exportHistory).toEqual([rowA, rowB, rowC])
    expect(vm.exportForm.modules).toHaveLength(13)
    const text = wrapper.text()
    expect(text).toContain('500 B')
    expect(text).toContain('2.00 KB')
    expect(text).toContain('5.00 MB')
  })

  it('加载历史失败 → logger 兜底；刷新通过手动调用', async () => {
    mockGetSyncLogs.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).exportHistory).toEqual([])
  })

  it('clearModules 清空 / selectAllModules 全选（模板「全选」「清空」按钮）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.exportType = 'selective'
    await nextTick()
    const btns = wrapper.findAll('el-button-stub')
    const textBtn = (t: string) => btns.find((b: any) => b.text().trim() === t)
    await textBtn('清空').trigger('click')
    expect(vm.exportForm.modules).toEqual([])
    await textBtn('全选').trigger('click')
    expect(vm.exportForm.modules).toHaveLength(13)
  })
})

describe('handleExport 验证分支', () => {
  it('选择性导出无模块 → 警告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.exportType = 'selective'
    vm.exportForm.modules = []
    await vm.handleExport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请至少选择一个导出模块')
    expect(mockExportEncryptedData).not.toHaveBeenCalled()
  })

  it('加密无密码 / 密码过短 / 两次不一致 → 警告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.encrypted = true
    vm.exportForm.password = ''
    await vm.handleExport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入加密密码')

    vm.exportForm.password = '1234567'
    await vm.handleExport()
    expect(ElMessage.warning).toHaveBeenCalledWith('密码长度至少为 8 位')

    vm.exportForm.password = '12345678'
    vm.exportForm.confirmPassword = '87654321'
    await vm.handleExport()
    expect(ElMessage.warning).toHaveBeenCalledWith('两次输入的密码不一致')
    expect(mockExportEncryptedData).not.toHaveBeenCalled()
  })
})

describe('handleExport 成功路径', () => {
  it('加密 full + since → 载荷不含 modules；成功提示+自动下载+刷新历史+清空密码', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.exportType = 'full'
    vm.exportForm.password = '12345678'
    vm.exportForm.confirmPassword = '12345678'
    vm.exportForm.since = new Date('2024-01-01T00:00:00Z')
    await vm.handleExport()
    expect(mockExportEncryptedData).toHaveBeenCalledWith({
      export_type: 'full',
      modules: undefined,
      password: '12345678',
      since: '2024-01-01T00:00:00.000Z',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('导出成功! 共 99 条记录')
    expect(mockDownloadExportPackage).toHaveBeenCalledWith('pkg_x.rrs')
    expect(mockGetSyncLogs).toHaveBeenCalled()
    expect(vm.exportForm.password).toBe('')
    expect(vm.exportForm.confirmPassword).toBe('')
    expect(vm.exporting).toBe(false)
  })

  it('加密 selective + since 为空 → modules 携带；模板「开始导出」按钮触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.exportType = 'selective'
    vm.exportForm.password = '12345678'
    vm.exportForm.confirmPassword = '12345678'
    vm.exportForm.since = null
    await findBtn(wrapper, '开始导出').trigger('click')
    await flushPromises()
    expect(mockExportEncryptedData).toHaveBeenCalledWith({
      export_type: 'selective',
      modules: vm.exportForm.modules,
      password: '12345678',
      since: undefined,
    })
  })

  it('未加密 → 旧版 exportData（含 include_files 与 since ISO）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.encrypted = false
    vm.exportForm.includeFiles = true
    vm.exportForm.since = new Date('2024-02-01T00:00:00Z')
    await vm.handleExport()
    expect(mockExportData).toHaveBeenCalledWith({
      since: '2024-02-01T00:00:00.000Z',
      modules: vm.exportForm.modules,
      include_files: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('导出成功! 共 5 条记录')
    expect(mockDownloadExportPackage).toHaveBeenCalledWith('old.zip')
  })

  it('response.success 为 false → 无成功提示', async () => {
    mockExportEncryptedData.mockResolvedValue({ success: false })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.password = '12345678'
    vm.exportForm.confirmPassword = '12345678'
    await vm.handleExport()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.exporting).toBe(false)
  })

  it('异常 → error(message 或兜底)；加密导出失败', async () => {
    mockExportEncryptedData.mockRejectedValue(new Error('磁盘满'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportForm.password = '12345678'
    vm.exportForm.confirmPassword = '12345678'
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('磁盘满')

    mockExportEncryptedData.mockRejectedValue(new Error(''))
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
  })
})

describe('下载与工具函数', () => {
  it('handleDownload / handleDownloadByName 成功与失败（历史行下载按钮）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '下载').trigger('click') // rowA
    await flushPromises()
    expect(mockDownloadExportPackage).toHaveBeenCalledWith('pkg_a.rrs')

    mockDownloadExportPackage.mockRejectedValue(new Error('404'))
    await vm.handleDownloadByName('pkg_b.rrs')
    expect(ElMessage.error).toHaveBeenCalledWith('404')

    mockDownloadExportPackage.mockRejectedValue(new Error(''))
    await vm.handleDownloadByName('pkg_b.rrs')
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
  })

  it('formatSize 三分支 / formatDate', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.formatSize(500)).toBe('500 B')
    expect(vm.formatSize(2048)).toBe('2.00 KB')
    expect(vm.formatSize(5 * 1024 * 1024)).toBe('5.00 MB')
    expect(vm.formatDate('2024-06-01')).not.toBe('')
  })
})

describe('表单 v-model', () => {
  it('exportType/since/modules/includeFiles/encrypted/password 同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const byName = (n: string) => wrapper.findAllComponents({ name: n })
    byName('ElRadioGroup')[0].vm.$emit('update:modelValue', 'incremental')
    expect(vm.exportForm.exportType).toBe('incremental')
    await nextTick()
    byName('ElDatePicker')[0].vm.$emit('update:modelValue', new Date('2024-03-01'))
    expect(vm.exportForm.since).toEqual(new Date('2024-03-01'))
    byName('ElCheckboxGroup')[0].vm.$emit('update:modelValue', ['policies'])
    expect(vm.exportForm.modules).toEqual(['policies'])
    const switches = wrapper.findAllComponents({ name: 'ElSwitch' })
    switches[0].vm.$emit('update:modelValue', true) // includeFiles
    expect(vm.exportForm.includeFiles).toBe(true)
    switches[1].vm.$emit('update:modelValue', false) // encrypted
    expect(vm.exportForm.encrypted).toBe(false)
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', 'pw123456')
    expect(vm.exportForm.password).toBe('pw123456')
    inputs[1].vm.$emit('update:modelValue', 'pw123456')
    expect(vm.exportForm.confirmPassword).toBe('pw123456')
  })
})

describe('响应形态收尾2', () => {
  it('total_records 缺省 / message-only / detail / 数组历史', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockExportData.mockResolvedValue({ success: true })
    vm.exportForm.encrypted = false
    await vm.handleExport()
    expect(ElMessage.success).toHaveBeenCalledWith('导出成功! 共 0 条记录')
    mockExportData.mockResolvedValue({ message: '无数据可导出' })
    await vm.handleExport()
    expect(ElMessage.warning).toHaveBeenCalledWith('无数据可导出')
    mockExportData.mockRejectedValue({ response: { data: { detail: '导出失败' } } })
    await vm.handleExport().catch(() => {})
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
    mockExportData.mockResolvedValue({ success: true })
    mockGetSyncLogs.mockResolvedValue({ data: { items: [{ id: 1 }] } })
    await vm.handleExport().catch(() => {})
    expect(vm.exportHistory).toEqual([{ id: 1 }])
    wrapper.unmount()
  })
})

describe('分支收尾', () => {
  it('response.items 直接 / 历史非数组兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGetSyncLogs.mockResolvedValue({ items: [{ id: 9 }] })
    await vm.loadExportHistory()
    expect(vm.exportHistory).toEqual([{ id: 9 }])
    mockGetSyncLogs.mockResolvedValue({ items: { bad: true } })
    await vm.loadExportHistory()
    expect(vm.exportHistory).toEqual([])
    wrapper.unmount()
  })
})

describe('历史形态收尾', () => {
  it('data.items 解包 / list 非数组兜底 / 纯数组 / 空对象', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGetSyncLogs.mockResolvedValue({ data: { items: [{ id: 2 }] } })
    await vm.loadExportHistory()
    expect(vm.exportHistory).toEqual([{ id: 2 }])
    mockGetSyncLogs.mockResolvedValue({ data: { items: { oops: true } } })
    await vm.loadExportHistory()
    expect(vm.exportHistory).toEqual([])
    mockGetSyncLogs.mockResolvedValue([{ id: 3 }])
    await vm.loadExportHistory()
    expect(vm.exportHistory).toEqual([{ id: 3 }])
    mockGetSyncLogs.mockResolvedValue({})
    await vm.loadExportHistory()
    expect(vm.exportHistory).toEqual([])
    wrapper.unmount()
  })
})

describe('导出结果卡片', () => {
  it('total_records ?? 0 与 exported_at 三元两侧；「重新下载数据包」内联点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // total_records 缺省 → ?? 0；exported_at 缺省 → '-'
    vm.exportResult = { package_name: 'pkg_r.rrs', size: 2048 }
    await nextTick()
    const card = wrapper.find('.export-result')
    expect(card.exists()).toBe(true)
    expect(card.text()).toContain('0')
    expect(card.text()).toContain('-')
    expect(card.text()).toContain('2.00 KB')
    // 行内 @click="handleDownloadByName(exportResult.package_name)"
    await findBtn(wrapper, '重新下载数据包').trigger('click')
    await flushPromises()
    expect(mockDownloadExportPackage).toHaveBeenCalledWith('pkg_r.rrs')

    // total_records / exported_at 有值侧
    vm.exportResult = {
      package_name: 'pkg_s.rrs',
      total_records: 7,
      exported_at: '2024-06-01T10:00:00',
      size: 100,
    }
    await nextTick()
    const text2 = wrapper.find('.export-result').text()
    expect(text2).toContain('7')
    expect(text2).toContain('2024/') // formatDate(exported_at) 真侧
    expect(text2).toContain('100 B')
    wrapper.unmount()
  })
})
