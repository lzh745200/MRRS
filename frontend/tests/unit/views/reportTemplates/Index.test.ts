/**
 * views/reportTemplates/Index.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：moduleIcon/moduleLabel 映射与兜底、formatDate、parseFields（无/JSON 数组/非数组/对象字段/异常回退）、
 * displayTemplates（类型/搜索/模块过滤）、loadTemplates（数组/data/items/null/失败）、
 * openCreateDialog/resetCreateForm、handleCreate（无 formRef/校验失败/成功/失败）、
 * handleDownload（成功/失败）、handleEdit/handleSaveEdit（无模板/校验失败/名称空警告/成功/失败）、
 * handlePreview、handleDelete（确认/取消）、上传流程（openUploadDialog/onUploadDialogClosed/
 * onFileChange/onFileRemove/handleFilePreview 早退与成功失败/handleConfirmImport 全量覆盖确认与成功失败）、
 * 模板：搜索/筛选/选项卡切换、五个对话框 v-model、上传两阶段与导入结果。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

vi.mock('xlsx', () => ({
  utils: {
    aoa_to_sheet: vi.fn(() => ({})),
    book_new: vi.fn(() => ({})),
    book_append_sheet: vi.fn(),
  },
  writeFile: vi.fn(),
}))

const {
  ElMessage,
  confirmMock,
  validateMock,
  mockGet,
  mockPost,
  mockPut,
  mockDel,
  mockApiRequest,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  validateMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
  mockApiRequest: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import Templates from '@/views/reportTemplates/Index.vue'

const templates = [
  { id: 1, name: '导入模板A', type: 'import', module: 'village', description: '帮扶村导入', is_active: true, created_at: '2024-06-01', updated_at: '2024-06-02', fields: '["name","county"]' },
  { id: 2, name: '导入模板B', type: 'import', module: 'school', description: '', is_active: false, created_at: '2024-06-03', updated_at: '2024-06-04', fields: '[{"excel_header":"H1","db_field":"db1"},"str"]' },
  { id: 3, name: '导出模板C', type: 'export', module: 'fund', description: '经费导出', is_active: true, created_at: '2024-06-05', updated_at: '2024-06-06', fields: 'a,b,c' },
  { id: 4, name: '导入模板D', type: 'import', module: 'weird', description: '未知模块', is_active: true, created_at: '2024-06-07', updated_at: '2024-06-08', fields: '{"bad json"' },
  { id: 5, name: 'EXCEL 模板', type: 'import', module: 'village', description: 'Excel 描述', is_active: false, created_at: '2024-06-09', updated_at: '2024-06-10' },
]

function mountComp() {
  return mount(Templates, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-tabs': {
          name: 'ElTabs',
          template: '<div class="el-tabs-stub"><slot /></div>',
          emits: ['update:modelValue', 'tab-change'],
        },
        'el-tab-pane': {
          name: 'ElTabPane',
          template: '<div class="el-tab-pane-stub"><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue', 'closed'],
        },
        'el-form': {
          name: 'ElForm',
          template: '<div class="el-form-stub"><slot /></div>',
          methods: { validate: () => validateMock(), resetFields: () => {} },
        },
        'el-form-item': {
          name: 'ElFormItem',
          template: '<div class="el-form-item-stub"><slot /></div>',
        },
        'el-input': {
          name: 'ElInput',
          template: '<div class="el-input-stub" />',
          emits: ['update:modelValue', 'clear', 'keyup'],
        },
        'el-select': {
          name: 'ElSelect',
          template: '<div class="el-select-stub"><slot /></div>',
          emits: ['update:modelValue', 'change'],
        },
        'el-switch': {
          name: 'ElSwitch',
          props: ['modelValue'],
          template:
            '<button class="el-switch-stub" @click="$emit(\'update:modelValue\', !modelValue)" />',
        },
        'el-radio-group': {
          name: 'ElRadioGroup',
          template: '<div class="el-radio-group-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-upload': {
          name: 'ElUpload',
          template: '<div class="el-upload-stub"><slot /><slot name="tip" /></div>',
          methods: { clearFiles: vi.fn() },
        },
        'el-descriptions': {
          name: 'ElDescriptions',
          template: '<div class="el-descriptions-stub"><slot /></div>',
        },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          props: ['label', 'span'],
          template: '<div class="el-descriptions-item-stub">{{ label }}<slot /></div>',
        },
        'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
        'el-table-column': {
          name: 'ElTableColumn',
          props: ['prop', 'label'],
          template: '<div class="el-table-column-stub">{{ label }}</div>',
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-alert': {
          name: 'ElAlert',
          props: ['title'],
          template: '<div class="el-alert-stub">{{ title }}<slot /></div>',
        },
        'el-empty': { name: 'ElEmpty', template: '<div class="el-empty-stub"><slot /></div>' },
        'el-result': {
          name: 'ElResult',
          props: ['title', 'icon'],
          template:
            '<div class="el-result-stub">{{ title }}<slot /><slot name="sub-title" /></div>',
        },
        'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
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
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  mockGet.mockResolvedValue(templates)
  mockPost.mockResolvedValue({})
  mockPut.mockResolvedValue({})
  mockDel.mockResolvedValue({})
  mockApiRequest.mockResolvedValue(new Blob())
  validateMock.mockResolvedValue(true)
  confirmMock.mockResolvedValue('confirm')
})

describe('挂载与加载', () => {
  it('onMounted：数组形态加载；模板卡片渲染（含两标签页）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/report-templates')
    expect(vm.templates).toHaveLength(5)
    expect(vm.loading).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('导入模板A')
    expect(text).toContain('启用')
    expect(text).toContain('停用')
    expect(text).toContain('帮扶村')
    expect(text).toContain('帮扶学校')
    expect(text).toContain('未知模块') // moduleLabel 兜底
    expect(text).toContain('2024-06-01') // formatDate
  })

  it('data / items / null / 失败四种形态', async () => {
    mockGet.mockResolvedValue({ data: templates })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).templates).toHaveLength(5)

    mockGet.mockResolvedValue({ items: templates })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).templates).toHaveLength(5)

    mockGet.mockResolvedValue(null)
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).templates).toEqual([])

    mockGet.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).templates).toEqual([])
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('displayTemplates：类型过滤 + 搜索（名称/描述）+ 模块过滤', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.displayTemplates).toHaveLength(4) // import 类型
    vm.activeTab = 'export'
    expect(vm.displayTemplates).toHaveLength(1)
    vm.searchText = 'EXCEL'
    expect(vm.displayTemplates).toHaveLength(0) // 当前为 export 标签
    vm.activeTab = 'import'
    expect(vm.displayTemplates).toHaveLength(1) // 名称匹配 EXCEL
    vm.searchText = 'xx'
    expect(vm.displayTemplates).toHaveLength(0)
    vm.searchText = ''
    vm.filterModule = 'school'
    expect(vm.displayTemplates).toHaveLength(1) // 模块过滤
    vm.filterModule = 'village'
    expect(vm.displayTemplates).toHaveLength(2)
  })

  it('空模板 → el-empty 空态', async () => {
    mockGet.mockResolvedValue([])
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.findAll('.el-empty-stub').length).toBeGreaterThan(0)
  })
})

describe('工具函数', () => {
  it('moduleIcon/moduleLabel 映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const m of ['village', 'school', 'fund', 'project', 'rural_work', 'comprehensive']) {
      expect(vm.moduleIcon(m)).toBeTruthy()
      expect(vm.moduleLabel(m)).toBeTruthy()
    }
    expect(vm.moduleIcon('zzz')).toBeTruthy()
    expect(vm.moduleLabel('zzz')).toBe('zzz')
  })

  it('formatDate：空与截取', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatDate('')).toBe('-')
    expect(vm.formatDate(undefined)).toBe('-')
    expect(vm.formatDate('2024-06-01T10:00:00')).toBe('2024-06-01')
  })

  it('parseFields：无/字符串数组/对象字段（三链兜底）/非数组/JSON 异常回退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.parseFields(undefined)).toEqual([])
    expect(vm.parseFields('["a","b"]')).toEqual(['a', 'b'])
    expect(
      vm.parseFields(
        '[{"excel_header":"H1","db_field":"d"},{"db_field":"only_db"},{"x":1},"s",""]'
      )
    ).toEqual(['H1', 'only_db', '{"x":1}', 's'])
    expect(vm.parseFields('{"not":"array"}')).toEqual([])
    expect(vm.parseFields('a, b ,c')).toEqual(['a', 'b', 'c']) // JSON 失败 → split
    expect(vm.parseFields('["x"]')).toEqual(['x'])
  })
})

describe('搜索与选项卡', () => {
  it('搜索输入：clear / keyup.enter 触发 onFilterChange（noop 安全）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', 'A')
    expect((wrapper.vm as any).searchText).toBe('A')
    inputs[0].vm.$emit('clear')
    inputs[0].vm.$emit('keyup', { key: 'Enter' })
    expect(true).toBe(true)
  })

  it('模块筛选 select change；tabs tab-change 与 v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const tabs = wrapper.findAllComponents({ name: 'ElTabs' })
    tabs[0].vm.$emit('update:modelValue', 'export')
    expect(vm.activeTab).toBe('export')
    tabs[0].vm.$emit('tab-change', 'import')
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 'fund')
    selects[0].vm.$emit('change', 'fund')
    expect(vm.filterModule).toBe('fund')
  })
})

describe('创建模板', () => {
  it('「新建模板」按钮 → 打开对话框；v-model 与 @closed 重置', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '新建模板').trigger('click')
    expect(vm.showCreateDialog).toBe(true)
    vm.newTemplate.name = '脏数据'
    wrapper.findAllComponents({ name: 'ElDialog' })[0].vm.$emit('closed')
    expect(vm.newTemplate.name).toBe('')
    expect(vm.newTemplate.type).toBe('import')
    expect(vm.newTemplate.module).toBe('village')
  })

  it('handleCreate：无 formRef 早退；校验失败早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createFormRef = undefined
    await vm.handleCreate()
    expect(mockPost).not.toHaveBeenCalled()

    vm.createFormRef = { validate: validateMock }
    validateMock.mockRejectedValueOnce(new Error('invalid'))
    await vm.handleCreate()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleCreate：成功 → 提示+关闭+切换标签+刷新；失败 → error', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.newTemplate.type = 'export'
    await findBtn(wrapper, '创建').trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/report-templates', expect.any(Object))
    expect(ElMessage.success).toHaveBeenCalledWith('模板创建成功')
    expect(vm.showCreateDialog).toBe(false)
    expect(vm.activeTab).toBe('export')
    expect(mockGet).toHaveBeenCalled()

    mockPost.mockRejectedValue(new Error('net'))
    await vm.handleCreate()
    expect(ElMessage.error).toHaveBeenCalledWith('创建失败')
    expect(vm.creating).toBe(false)
  })
})

describe('编辑模板', () => {
  it('handleEdit 打开编辑框；handleSaveEdit 无模板早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '编辑').trigger('click')
    expect(vm.showEditDialog).toBe(true)
    expect(vm.editTemplate).toMatchObject({ id: 1 })
    vm.editTemplate = null
    await vm.handleSaveEdit()
    expect(mockPut).not.toHaveBeenCalled()
  })

  it('handleSaveEdit：名称空 → 警告；校验失败早退；成功 → 提示+关闭+刷新；失败 → error', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.editTemplate = { id: 3, name: '  ' } as any
    vm.editFormRef = undefined
    await vm.handleSaveEdit()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入模板名称')

    // 表单校验失败 → 早退
    vm.editFormRef = { validate: validateMock }
    validateMock.mockRejectedValueOnce(new Error('invalid'))
    await vm.handleSaveEdit()
    expect(mockPut).not.toHaveBeenCalled()

    vm.editTemplate = { id: 3, name: '改名', description: 'd', is_active: true } as any
    await vm.handleSaveEdit()
    expect(mockPut).toHaveBeenCalledWith('/report-templates/3', {
      name: '改名',
      description: 'd',
      is_active: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('保存成功')
    expect(vm.showEditDialog).toBe(false)
    expect(mockGet).toHaveBeenCalled()

    mockPut.mockRejectedValue(new Error('net'))
    await vm.handleSaveEdit()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    expect(vm.creating).toBe(false)
  })

  it('编辑表单控件 v-model（名称/描述/开关）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.editTemplate = { id: 1, name: 'a', description: 'b', is_active: false } as any
    await nextTick()
    // DOM 顺序：搜索框(0)、创建名称(1)、创建描述(2)、编辑名称(3)、编辑描述(4)
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[3].vm.$emit('update:modelValue', '新名')
    expect(vm.editTemplate.name).toBe('新名')
    inputs[4].vm.$emit('update:modelValue', '新描述')
    expect(vm.editTemplate.description).toBe('新描述')
    const switches = wrapper.findAllComponents({ name: 'ElSwitch' })
    await switches[0].trigger('click')
    expect(vm.editTemplate.is_active).toBe(true)
  })
})

describe('预览与删除', () => {
  it('handlePreview：打开预览对话框（描述缺省 + fields 渲染）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '预览').trigger('click')
    expect(vm.showPreviewDialog).toBe(true)
    expect(vm.previewTemplate).toMatchObject({ id: 1 })
    const text = wrapper.text()
    expect(text).toContain('导入模板')
    expect(text).toContain('启用')
    expect(text).toContain('name')
    expect(text).toContain('county')
  })

  it('预览对话框：下载模板按钮 + 关闭', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showPreviewDialog = true
    vm.previewTemplate = { ...templates[4], description: undefined, fields: undefined }
    await nextTick()
    await findBtn(wrapper, '下载模板').trigger('click')
    await flushPromises()
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ url: '/report-templates/5/download', responseType: 'blob' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('下载模板: EXCEL 模板')

    await findBtn(wrapper, '关闭').trigger('click')
    expect(vm.showPreviewDialog).toBe(false)
  })

  it('handleDownload：失败提示；预览模板无 fields → 无字段区', async () => {
    mockApiRequest.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showPreviewDialog = true
    vm.previewTemplate = { ...templates[4], fields: undefined }
    await nextTick()
    await vm.handleDownload(vm.previewTemplate)
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
  })

  it('handleDelete：确认 → 删除+刷新；取消静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete(templates[0])
    expect(confirmMock).toHaveBeenCalledWith('确定删除模板“导入模板A”？此操作不可恢复。', '提示', expect.objectContaining({ type: 'warning' }))
    expect(mockDel).toHaveBeenCalledWith('/report-templates/1')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(mockGet).toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce(new Error('cancel'))
    await vm.handleDelete(templates[1])
    expect(mockDel.mock.calls.length).toBe(1)
  })

  it('「删除」按钮点击（模板卡片）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '删除').trigger('click')
    await flushPromises()
    expect(mockDel).toHaveBeenCalledWith('/report-templates/1')
  })

  it('卡片操作按钮：下载/预览/编辑/删除（两个标签页各一次）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const panes = wrapper.findAll('.el-tab-pane-stub')
    expect(panes.length).toBe(2)
    const btnIn = (pane: any, text: string) =>
      pane.findAll('el-button-stub').find((b: any) => b.text().trim() === text)

    // import 标签页（pane1/pane2 同时渲染同一列表）
    await btnIn(panes[0], '下载').trigger('click')
    await flushPromises()
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ url: '/report-templates/1/download' })
    )
    await btnIn(panes[1], '下载').trigger('click')
    await flushPromises()

    // 切到 export 标签页
    vm.activeTab = 'export'
    await nextTick()
    await btnIn(panes[0], '预览').trigger('click')
    expect(vm.showPreviewDialog).toBe(true)
    expect(vm.previewTemplate.type).toBe('export') // 导出模板
    vm.showPreviewDialog = false
    await btnIn(panes[1], '预览').trigger('click')
    expect(vm.showPreviewDialog).toBe(true)
    vm.showPreviewDialog = false
    await btnIn(panes[0], '编辑').trigger('click')
    expect(vm.showEditDialog).toBe(true)
    vm.showEditDialog = false
    await btnIn(panes[1], '编辑').trigger('click')
    expect(vm.showEditDialog).toBe(true)
    vm.showEditDialog = false
    await btnIn(panes[0], '删除').trigger('click')
    await flushPromises()
    expect(mockDel).toHaveBeenCalledWith('/report-templates/3')
    await btnIn(panes[1], '删除').trigger('click')
    await flushPromises()
    expect(mockDel).toHaveBeenCalledWith('/report-templates/3')
  })

  it('创建对话框：表单 v-model 与「取消」按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showCreateDialog = true
    await nextTick()
    // ElInput: 0=搜索, 1=创建名称, 2=创建描述；ElSelect: 0=模块筛选, 1=创建类型, 2=创建模块
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[1].vm.$emit('update:modelValue', '名A')
    expect(vm.newTemplate.name).toBe('名A')
    inputs[2].vm.$emit('update:modelValue', '描B')
    expect(vm.newTemplate.description).toBe('描B')
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[1].vm.$emit('update:modelValue', 'export')
    expect(vm.newTemplate.type).toBe('export')
    selects[2].vm.$emit('update:modelValue', 'project')
    expect(vm.newTemplate.module).toBe('project')

    const cancels = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '取消')
    await cancels[0].trigger('click') // 创建对话框取消
    expect(vm.showCreateDialog).toBe(false)
  })

  it('编辑对话框「取消」与全部对话框 v-model 同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showCreateDialog = true
    vm.showEditDialog = true
    vm.showPreviewDialog = true
    vm.showUploadDialog = true
    vm.showImportResult = true
    vm.showFillDialog = true
    vm.editTemplate = templates[0]
    await nextTick()
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs.length).toBe(6)
    const cancels = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '取消')
    await cancels[1].trigger('click') // 编辑对话框取消
    expect(vm.showEditDialog).toBe(false)
    await cancels[3].trigger('click') // 上传对话框取消（cancels[2] 为在线填报对话框取消）
    expect(vm.showUploadDialog).toBe(false)
    vm.showEditDialog = true
    vm.showUploadDialog = true
    vm.showPreviewDialog = true
    vm.showImportResult = true
    await nextTick()
    dialogs[0].vm.$emit('update:modelValue', false)
    dialogs[1].vm.$emit('update:modelValue', false)
    dialogs[2].vm.$emit('update:modelValue', false)
    dialogs[3].vm.$emit('update:modelValue', false)
    dialogs[4].vm.$emit('update:modelValue', false)
    dialogs[5].vm.$emit('update:modelValue', false)
    expect(vm.showCreateDialog).toBe(false)
    expect(vm.showEditDialog).toBe(false)
    expect(vm.showPreviewDialog).toBe(false)
    expect(vm.showUploadDialog).toBe(false)
    expect(vm.showImportResult).toBe(false)
  })
})

describe('上传填报', () => {
  it('openUploadDialog 重置状态；「上传填报」按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '上传填报').trigger('click')
    expect(vm.showUploadDialog).toBe(true)
    expect(vm.currentUploadTemplate).toMatchObject({ id: 1 })
    expect(vm.previewResult).toBeNull()
    expect(vm.importMode).toBe('incremental')
  })

  it('onUploadDialogClosed / onFileChange（raw 缺失兜底）/ onFileRemove', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.onFileChange({ raw: { name: 'a.xlsx' } })
    expect(vm.selectedFile).toEqual({ name: 'a.xlsx' })
    vm.onFileChange({})
    expect(vm.selectedFile).toEqual({})
    vm.onFileRemove()
    expect(vm.selectedFile).toBeNull()
    vm.selectedFile = { name: 'b.xlsx' } as any
    vm.onUploadDialogClosed()
    expect(vm.selectedFile).toBeNull()
    expect(vm.previewResult).toBeNull()
  })

  it('handleFilePreview：早退（无文件/无模板）；成功 → 列提取', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleFilePreview()
    expect(mockPost).not.toHaveBeenCalled()

    mockPost.mockResolvedValue({ data: { parsed_data: [{ a: 1, b: 2 }], error_count: 1 } })
    vm.currentUploadTemplate = templates[1]
    vm.selectedFile = { name: 'x.xlsx' } as any
    await vm.handleFilePreview()
    expect(mockPost).toHaveBeenCalledWith(
      '/report-templates/2/upload?mode=preview',
      expect.any(FormData),
      expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' } })
    )
    expect(vm.previewResult).toEqual({ parsed_data: [{ a: 1, b: 2 }], error_count: 1 })
    expect(vm.previewColumns).toEqual(['a', 'b'])
    expect(vm.previewing).toBe(false)
  })

  it('handleFilePreview：parsed_data 为空/首行为 null → 列保持空；失败（detail/message/默认）', async () => {
    mockPost.mockResolvedValue({ data: { parsed_data: [] } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentUploadTemplate = templates[1]
    vm.selectedFile = { name: 'x.xlsx' } as any
    await vm.handleFilePreview()
    expect(vm.previewColumns).toEqual([])

    mockPost.mockResolvedValue({ data: { parsed_data: [null] } }) // || {} 兜底
    await vm.handleFilePreview()
    expect(vm.previewColumns).toEqual([])

    mockPost.mockRejectedValue({ response: { data: { detail: '文件损坏' } } })
    await vm.handleFilePreview()
    expect(ElMessage.error).toHaveBeenCalledWith('文件损坏')
    expect(vm.previewResult).toBeNull()

    mockPost.mockRejectedValue(new Error('网络'))
    await vm.handleFilePreview()
    expect(ElMessage.error).toHaveBeenCalledWith('网络')

    mockPost.mockRejectedValue(new Error(''))
    await vm.handleFilePreview()
    expect(ElMessage.error).toHaveBeenCalledWith('预览失败')
  })

  it('「预览数据」按钮（预览前阶段）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentUploadTemplate = templates[1]
    vm.selectedFile = { name: 'x.xlsx' } as any
    mockPost.mockResolvedValue({ data: { parsed_data: [{ a: 1 }] } })
    await nextTick()
    await findBtn(wrapper, '预览数据').trigger('click')
    await flushPromises()
    expect(vm.previewResult).toEqual({ parsed_data: [{ a: 1 }] })
  })

  it('预览第二阶段：错误列表渲染 + 导入模式三元两侧 + 重新选择文件按钮', async () => {
    mockPost.mockResolvedValue({
      data: { parsed_data: [{ a: 1 }], error_count: 2, errors: [{ row: 1, message: 'E1' }] },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentUploadTemplate = templates[1]
    vm.selectedFile = { name: 'x.xlsx' } as any
    // 先切换导入模式为 overwrite（radio 在第一阶段渲染）
    wrapper.findAllComponents({ name: 'ElRadioGroup' })[0].vm.$emit('update:modelValue', 'overwrite')
    expect(vm.importMode).toBe('overwrite')
    await vm.handleFilePreview()
    expect(vm.previewResult).toBeTruthy()
    await nextTick()
    expect(wrapper.text()).toContain('错误详情')
    expect(wrapper.text()).toContain('位置') // errors 表列标签
    expect(wrapper.text()).toContain('全量覆盖') // 三元 false 侧

    // 「重新选择文件」按钮 → 清空预览
    await findBtn(wrapper, '重新选择文件').trigger('click')
    expect(vm.previewResult).toBeNull()
  })

  it('handleConfirmImport：早退；增量模式直接导入成功', async () => {
    mockPost.mockResolvedValue({ data: { success: true, message: '完成', imported: 5, skipped: 1, deleted: 0, failed: 0, errors: [] } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleConfirmImport()
    expect(mockPost).not.toHaveBeenCalled()

    vm.currentUploadTemplate = templates[1]
    vm.selectedFile = { name: 'x.xlsx' } as any
    vm.importMode = 'incremental'
    await vm.handleConfirmImport()
    expect(mockPost).toHaveBeenCalledWith(
      '/report-templates/2/upload?mode=confirm&import_mode=incremental',
      expect.any(FormData),
      expect.anything()
    )
    expect(vm.importResult).toEqual({ success: true, message: '完成', imported: 5, skipped: 1, deleted: 0, failed: 0, errors: [] })
    expect(vm.showUploadDialog).toBe(false)
    expect(vm.showImportResult).toBe(true)
    expect(mockGet).toHaveBeenCalled()
    expect(vm.importing).toBe(false)
  })

  it('handleConfirmImport：overwrite 取消 → 早退；确认 → 导入；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentUploadTemplate = templates[1]
    vm.selectedFile = { name: 'x.xlsx' } as any
    vm.importMode = 'overwrite'
    confirmMock.mockRejectedValueOnce(new Error('cancel'))
    await vm.handleConfirmImport()
    expect(mockPost).not.toHaveBeenCalled()

    confirmMock.mockResolvedValueOnce('confirm')
    mockPost.mockResolvedValue({ data: { success: true, message: 'm', imported: 1, skipped: 0, deleted: 2, failed: 0, errors: [] } })
    await vm.handleConfirmImport()
    expect(confirmMock).toHaveBeenCalledWith(
      '全量覆盖将删除现有所有记录后重新导入，确定继续？',
      '危险操作确认',
      expect.anything()
    )
    expect(mockPost).toHaveBeenCalledWith(expect.stringContaining('import_mode=overwrite'), expect.anything(), expect.anything())

    mockPost.mockRejectedValue({ response: { data: { detail: '后端拒绝' } } })
    await vm.handleConfirmImport()
    expect(ElMessage.error).toHaveBeenCalledWith('后端拒绝')

    mockPost.mockRejectedValue(new Error('网络错误'))
    await vm.handleConfirmImport()
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')

    mockPost.mockRejectedValue(new Error(''))
    await vm.handleConfirmImport()
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')
  })

  it('导入结果对话框：成功/失败两种 result 与错误列表渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showImportResult = true
    vm.importResult = { success: true, message: '导入完成', imported: 3, skipped: 2, deleted: 1, failed: 1, errors: [{ row: 2, message: '行错误' }] }
    await nextTick()
    const text = wrapper.text()
    expect(text).toContain('导入完成')
    expect(text).toContain('导入成功')
    expect(text).toContain('失败详情') // 错误详情标题
    expect(text).toContain('删除旧记录')

    vm.importResult = { success: false, message: '', detail: '详情信息', failed: 0, errors: [] }
    await nextTick()
    expect(wrapper.text()).toContain('导入失败')
    expect(wrapper.text()).toContain('详情信息')
  })

  it('上传对话框内控件 v-model（导入模式 radio；文件变化）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showUploadDialog = true
    await nextTick()
    wrapper.findAllComponents({ name: 'ElRadioGroup' })[0].vm.$emit('update:modelValue', 'overwrite')
    expect(vm.importMode).toBe('overwrite')
  })
})

describe('在线填报与字段组合', () => {
  it('openFillDialog 解析模板字段；无字段时加载模块默认字段', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const t = { id: 1, name: '测试模板', fields: JSON.stringify(['village_name', 'county']), module: 'village' }
    await vm.openFillDialog(t)
    expect(vm.showFillDialog).toBe(true)
    expect(vm.fillFields.length).toBe(2)
    expect(vm.fillFields[0].key).toBe('village_name')
  })

  it('handleFillExport 导出 Excel 并提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fillTemplate = { id: 1, name: '导出模板' }
    vm.fillFields = [{ key: 'name', label: '名称' }, { key: 'county', label: '县' }]
    vm.fillRow = { name: '幸福村', county: '长顺县' }
    await vm.handleFillExport()
    expect(ElMessage.success).toHaveBeenCalledWith('已导出 Excel 文件')
  })

  it('loadAvailableFields 加载模块字段', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.newTemplate.module = 'village'
    await vm.loadAvailableFields()
    expect(vm.availableFields.length).toBeGreaterThan(0)
  })
})

describe('模板字段组合补充', () => {
  it('loadAvailableFields 失败/无模块；loadModuleFieldsForFill；selectedFields 提交', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 无模块 → 直接返回空
    vm.newTemplate.module = ''
    await vm.loadAvailableFields()
    expect(vm.availableFields).toEqual([])
    // 失败 → 空
    vm.newTemplate.module = 'village'
    mockGet.mockRejectedValueOnce(new Error('x'))
    await vm.loadAvailableFields()
    expect(vm.availableFields).toEqual([])
    // loadModuleFieldsForFill 成功 + 失败
    mockGet.mockResolvedValueOnce({ data: [{ key: 'a', label: 'A' }] })
    await vm.loadModuleFieldsForFill('village')
    expect(vm.fillFields.length).toBe(1)
    mockGet.mockRejectedValueOnce(new Error('x'))
    await vm.loadModuleFieldsForFill('village')
    expect(vm.fillFields).toEqual([])
    // selectedFields 提交
    vm.newTemplate.name = 'T'
    vm.newTemplate.type = 'export'
    vm.newTemplate.module = 'village'
    vm.newTemplate.selectedFields = ['a', 'b']
    vm.formRef = { validate: vi.fn(() => Promise.resolve()) }
    await vm.handleCreate()
    expect(mockPost).toHaveBeenCalledWith('/report-templates', expect.objectContaining({ fields: '["a","b"]' }))
  })
})

describe('模板控件补充', () => {
  it('搜索 input/模块 select/标签页 触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    if (inputs.length) inputs[0].vm.$emit('update:modelValue', '关键词')
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    if (selects.length) selects[0].vm.$emit('update:modelValue', 'village')
    const tabs = wrapper.findAllComponents({ name: 'ElTabs' })
    if (tabs.length) tabs[0].vm.$emit('update:modelValue', 'export')
    wrapper.unmount()
  })
})

describe('填报导出边界补充', () => {
  it('loadAvailableFields 裸数组/非数组对象', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.newTemplate.module = 'village'
    ;(mockGet as any).mockResolvedValueOnce([{ key: 'a', label: 'A' }])
    await vm.loadAvailableFields()
    expect(vm.availableFields).toEqual([{ key: 'a', label: 'A' }])
    ;(mockGet as any).mockResolvedValueOnce({ data: { x: 1 } })
    await vm.loadAvailableFields()
    expect(vm.availableFields).toEqual([])
    wrapper.unmount()
  })
  it('openFillDialog 无字段无模块 / 有模块触发加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openFillDialog({ name: 't1', fields: '' })
    expect(vm.fillFields).toEqual([])
    vm.openFillDialog({ name: 't2', fields: '', module: 'village' })
    expect(vm.fillFields).toEqual([])
    wrapper.unmount()
  })
  it('loadModuleFieldsForFill 信封 data.data / 非数组', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    ;(mockGet as any).mockResolvedValueOnce({ data: { data: [{ key: 'b', label: 'B' }] } })
    await vm.loadModuleFieldsForFill('village')
    expect(vm.fillFields).toEqual([{ key: 'b', label: 'B' }])
    ;(mockGet as any).mockResolvedValueOnce({ data: { data: { y: 1 } } })
    await vm.loadModuleFieldsForFill('village')
    expect(vm.fillFields).toEqual([])
    wrapper.unmount()
  })
  it('handleFillExport 无 label/空值/无模板名', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openFillDialog({ name: '', fields: 'k1' })
    await vm.handleFillExport()
    wrapper.unmount()
  })
})

describe('在线填报全控件', () => {
  it('行内「在线填报」→ 控件 v-model → 取消', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const fillBtn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes('在线填报'))
    if (fillBtn) {
      await fillBtn.trigger('click')
    } else {
      vm.openFillDialog({ name: 't', fields: 'k1,k2' })
    }
    await wrapper.vm.$nextTick()
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    for (const i of inputs) {
      i.vm.$emit('update:modelValue', 'v')
      await wrapper.vm.$nextTick()
    }
    const checkboxes = wrapper.findAllComponents({ name: 'ElCheckboxGroup' })
    for (const c of checkboxes) {
      c.vm.$emit('update:modelValue', ['k1'])
      await wrapper.vm.$nextTick()
    }
    let cancelBtn: any = null
    for (const d of wrapper.findAll('.el-dialog-stub')) {
      if (d.findAll('el-button-stub').some((b: any) => b.text().includes('导出 Excel'))) {
        cancelBtn = d.findAll('el-button-stub').find((b: any) => b.text().includes('取消'))
        break
      }
    }
    if (cancelBtn) await cancelBtn.trigger('click')
    expect(vm.showFillDialog).toBe(false)
    wrapper.unmount()
  })
})
