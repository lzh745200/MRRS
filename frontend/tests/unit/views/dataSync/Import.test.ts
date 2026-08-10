/**
 * views/dataSync/Import.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：isEncryptedFile 三侧、handleFileChange、handleImport 全分支（未选/加密无密码/
 * 加密成功/旧版成功/异常 message 与兜底）、stats 数组四条件 if、
 * showConflicts（无冲突/有冲突跳转）、loadImportHistory（成功/失败）、formatDate、
 * 模板：上传、密码输入 v-if、策略 radio v-model、结果卡（失败记录三元/冲突区/错误区）、历史行。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  mockImportData,
  mockImportEncryptedData,
  mockGetSyncLogs,
  pushSafeMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockImportData: vi.fn(),
  mockImportEncryptedData: vi.fn(),
  mockGetSyncLogs: vi.fn(),
  pushSafeMock: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/api/dataSync', () => ({
  importData: mockImportData,
  importEncryptedData: mockImportEncryptedData,
  getSyncLogs: mockGetSyncLogs,
}))

import ImportView from '@/views/dataSync/Import.vue'

const rowA = {
  package_name: 'pkg_a.rrs',
  total_records: 10,
  success_records: 8,
  failed_records: 2,
  conflicts_count: 1,
  created_at: '2024-06-01 10:00:00',
  user_name: '张三',
}
const rowB = {
  package_name: 'pkg_b.zip',
  total_records: 5,
  success_records: 5,
  failed_records: 0,
  conflicts_count: 0,
  created_at: '2024-06-02 11:00:00',
  user_name: '李四',
}

const resultOK = {
  package_name: 'pkg_x.rrs',
  imported_at: '2024-06-03 12:00:00',
  total_records: 10,
  success_records: 7,
  inserted_count: 3,
  updated_count: 2,
  skipped_count: 1,
  failed_records: 1,
  conflicts: [{ id: 1 }],
  errors: ['行 2 失败', '行 3 失败'],
  sync_log_id: 42,
}

function mountComp() {
  return mount(ImportView, {
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
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return { rowA, rowB }
          },
        },
        'el-radio-group': {
          name: 'ElRadioGroup',
          template: '<div class="el-radio-group-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-upload': {
          name: 'ElUpload',
          template: '<div class="el-upload-stub"><slot /></div>',
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
        'el-descriptions': {
          name: 'ElDescriptions',
          template: '<div class="el-descriptions-stub"><slot /></div>',
        },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          template: '<div class="el-descriptions-item-stub"><slot /></div>',
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-alert': {
          name: 'ElAlert',
          props: ['title'],
          template: '<div class="el-alert-stub">{{ title }}<slot /></div>',
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
  mockGetSyncLogs.mockResolvedValue({ success: true, items: [rowA, rowB] })
  mockImportData.mockResolvedValue({ success: true, ...resultOK })
  mockImportEncryptedData.mockResolvedValue({ success: true, ...resultOK })
})

describe('挂载与历史', () => {
  it('onMounted：加载导入历史（成功/失败）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetSyncLogs).toHaveBeenCalledWith({ action: 'import', page: 1, page_size: 20 })
    expect(vm.importHistory).toEqual([rowA, rowB])
    // 模板插槽渲染：成功/失败/冲突数字标签（slot 内容）
    const text = wrapper.text()
    expect(text).toContain('8') // rowA success_records
    expect(text).toContain('2') // rowA failed_records>0 → tag
    expect(text).toContain('1') // rowA conflicts_count>0 → tag
    expect(text).toContain('0') // rowB 失败 0 / 冲突 0 → span
    expect(text).toContain('2024/6/1 10:00:00')

    mockGetSyncLogs.mockRejectedValue(new Error('net'))
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).importHistory).toEqual([])
  })
})

describe('isEncryptedFile 与文件选择', () => {
  it('isEncryptedFile：无文件 false / .rrs true / 其他 false', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isEncryptedFile).toBe(false)
    vm.selectedFile = { name: 'a.rrs' } as any
    expect(vm.isEncryptedFile).toBe(true)
    vm.selectedFile = { name: 'a.zip' } as any
    expect(vm.isEncryptedFile).toBe(false)
  })

  it('handleFileChange：raw 存在/缺失', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleFileChange({ raw: { name: 'x.rrs' } } as any)
    expect(vm.selectedFile).toEqual({ name: 'x.rrs' })
    vm.handleFileChange({ raw: null } as any)
    expect(vm.selectedFile).toEqual({ name: 'x.rrs' })
  })
})

describe('handleImport', () => {
  it('未选文件 → 警告早退；加密无密码 → 警告早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择要导入的数据包')

    vm.selectedFile = { name: 'a.rrs' } as any
    await vm.handleImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入解密密码')
    expect(mockImportEncryptedData).not.toHaveBeenCalled()
  })

  it('加密文件导入成功：stats 全条件 + 提示 + 刷新历史 + 清空密码', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = { name: 'a.rrs' } as any
    vm.importForm.password = '12345678'
    await vm.handleImport()
    expect(mockImportEncryptedData).toHaveBeenCalledWith({ name: 'a.rrs' }, '12345678')
    expect(vm.importResult).toEqual(expect.objectContaining(resultOK))
    expect(ElMessage.success).toHaveBeenCalledWith(
      '导入成功! 成功 7 条, 失败 1 条, 新增 3 条, 更新 2 条, 跳过 1 条'
    )
    expect(mockGetSyncLogs).toHaveBeenCalled()
    expect(vm.importForm.password).toBe('')
    expect(vm.importing).toBe(false)
  })

  it('stats 条件全缺（inserted/updated/skipped undefined）；旧版导入', async () => {
    mockImportData.mockResolvedValue({
      success: true,
      success_records: 1,
      failed_records: 0,
      conflicts: [],
      errors: [],
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = { name: 'b.zip' } as any
    await vm.handleImport()
    expect(mockImportData).toHaveBeenCalledWith({ name: 'b.zip' }, 'merge')
    expect(ElMessage.success).toHaveBeenCalledWith('导入成功! 成功 1 条, 失败 0 条')
  })

  it('模板「开始导入」按钮 + 策略 radio v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    wrapper.findAllComponents({ name: 'ElRadioGroup' })[0].vm.$emit('update:modelValue', 'overwrite')
    expect(vm.importForm.strategy).toBe('overwrite')
    vm.selectedFile = { name: 'c.rrs' } as any
    vm.importForm.password = '12345678'
    await nextTick()
    await findBtn(wrapper, '开始导入').trigger('click')
    await flushPromises()
    expect(mockImportEncryptedData).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'c.rrs' }),
      '12345678'
    )
  })

  it('异常 → error(message 或兜底)', async () => {
    mockImportData.mockRejectedValue(new Error('文件损坏'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = { name: 'd.zip' } as any
    await vm.handleImport()
    expect(ElMessage.error).toHaveBeenCalledWith('文件损坏')

    mockImportData.mockRejectedValue(new Error(''))
    await vm.handleImport()
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')
  })

  it('结果卡渲染：失败记录三元、冲突区按钮、错误列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = { name: 'e.rrs' } as any
    vm.importForm.password = '12345678'
    await vm.handleImport()
    await nextTick()
    const text = wrapper.text()
    expect(text).toContain('pkg_x.rrs')
    expect(text).toContain('冲突记录')
    expect(text).toContain('错误信息')
    expect(text).toContain('行 2 失败') // el-alert title 渲染
    expect(text).toContain('行 3 失败')
    expect(text).toContain('查看并解决冲突')
  })
})

describe('showConflicts 与工具函数', () => {
  it('showConflicts：有冲突跳转；无冲突 info；importResult 为空 info', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importResult = resultOK
    vm.showConflicts()
    expect(pushSafeMock).toHaveBeenCalledWith({
      name: 'DataSyncConflicts',
      query: { syncLogId: '42' },
    })

    vm.importResult = { ...resultOK, conflicts: [], sync_log_id: 9 }
    vm.showConflicts()
    expect(ElMessage.info).toHaveBeenCalledWith('没有需要解决的冲突')

    vm.importResult = null
    vm.showConflicts()
    expect(ElMessage.info).toHaveBeenCalledTimes(2)
  })

  it('「查看并解决冲突」按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importResult = resultOK
    await nextTick()
    await findBtn(wrapper, '查看并解决冲突').trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'DataSyncConflicts' })
    )
  })

  it('formatDate', () => {
    const wrapper = mountComp()
    expect((wrapper.vm as any).formatDate('2024-06-01')).not.toBe('')
  })
})

describe('表单 v-model', () => {
  it('密码输入框同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = { name: 'f.rrs' } as any
    await nextTick()
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', 'pw123456')
    expect(vm.importForm.password).toBe('pw123456')
  })
})

describe('响应形态收尾2', () => {
  it('加密导入（带密码）/ stats 缺省 / message-only / detail / 数组响应', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = { name: 'e.rrs' } as any
    vm.importForm.password = 'secret1'
    mockImportEncryptedData.mockResolvedValue({ success: true, total_records: 3 })
    await vm.handleImport()
    expect(mockImportEncryptedData).toHaveBeenCalledWith({ name: 'e.rrs' }, 'secret1')

    // 空密码加密文件 → 预检查拦截
    vm.importForm.password = ''
    await vm.handleImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入解密密码')

    mockImportData.mockResolvedValue({ success: true, message: '仅提示' })
    vm.selectedFile = { name: 'f.zip' } as any
    vm.importForm.password = ''
    await vm.handleImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('仅提示')
    mockImportData.mockRejectedValue({ response: { data: { detail: '权限不足' } } })
    await vm.handleImport().catch(() => {})
    expect(ElMessage.error).toHaveBeenCalledWith('权限不足')
    mockGetSyncLogs.mockResolvedValue({ data: { items: [{ ...rowA }] } })
    await vm.loadImportHistory()
    expect(vm.importHistory.length).toBe(1)
    wrapper.unmount()
  })
})
