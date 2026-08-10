/**
 * views/system/ConfigPackage.vue 覆盖率攻坚
 * 覆盖：加载/导出/导入/重置配置、编辑对话框、文件导入各分支
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, ElMessageBox, mockGet, mockPost, mockPut, configStore } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn(), alert: vi.fn() },
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  configStore: { theme: 'light', setTheme: vi.fn() },
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox,
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/stores/config', () => ({
  useConfigStore: () => configStore,
}))

import ConfigPackage from '@/views/system/ConfigPackage.vue'

const configData = {
  code: 200,
  data: {
    SITE_NAME: '帮扶系统',
    SECRET_KEY: 'xxx',
    COUNT: 5,
  },
}

async function mountComp() {
  const w = mount(ConfigPackage, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
        'el-table': { name: 'ElTable', template: '<table class="el-table-stub"><slot /></table>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return {
              rowA: { key: 'SITE_NAME', value: 'v1', description: 'd1', sensitive: false },
              rowB: { key: 'SECRET_KEY', value: 's3cr3t', description: 'd2', sensitive: true },
            }
          },
        },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub"><slot /></button>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-form': { name: 'ElForm', template: '<form><slot /></form>' },
        'el-form-item': { name: 'ElFormItem', template: '<div><slot /></div>' },
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-radio-group': {
          name: 'ElRadioGroup',
          props: ['modelValue'],
          emits: ['update:modelValue', 'change'],
          template:
            '<div class="el-radio-group-stub" @click="$emit(\'update:modelValue\', \'dark\'); $emit(\'change\', \'dark\')"><slot /></div>',
        },
        'el-radio-button': {
          name: 'ElRadioButton',
          template: '<span class="el-radio-button-stub"><slot /></span>',
        },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockResolvedValue(configData)
  mockPost.mockResolvedValue({})
  mockPut.mockResolvedValue({})
  ElMessageBox.confirm.mockResolvedValue('confirm')
  configStore.theme = 'light'
  configStore.setTheme = vi.fn()
  document.documentElement.removeAttribute('data-theme')
})

describe('ConfigPackage.vue', () => {
  it('渲染并加载配置列表', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(mockGet).toHaveBeenCalledWith('/system/config')
    expect(vm.configList.length).toBe(3)
    expect(vm.configList[0].key).toBe('SITE_NAME')
    expect(vm.configList[0].sensitive).toBe(false)
    expect(vm.configList[1].sensitive).toBe(true)
    // 非字符串值 JSON 序列化
    expect(vm.configList[2].value).toBe('5')
  })

  it('主题应用：合法/非法主题', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.applyTheme('military')
    expect(vm.currentTheme).toBe('military')
    expect(configStore.setTheme).toHaveBeenCalledWith('military')
    expect(document.documentElement.getAttribute('data-theme')).toBe('military')
    vm.applyTheme('bogus-theme')
    expect(vm.currentTheme).toBe('light')
    expect(configStore.setTheme).toHaveBeenLastCalledWith('light')
  })

  it('主题为空 → 回退 light', async () => {
    configStore.theme = ''
    const w = await mountComp()
    expect((w.vm as any).currentTheme).toBe('light')
  })

  it('主题选择器（radio-group）→ 应用主题', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await w.find('.el-radio-group-stub').trigger('click')
    expect(vm.currentTheme).toBe('dark')
    expect(configStore.setTheme).toHaveBeenCalledWith('dark')
  })

  it('加载配置失败 → 空列表', async () => {
    mockGet.mockRejectedValue(new Error('boom'))
    const w = await mountComp()
    expect((w.vm as any).configList).toEqual([])
  })

  it('加载配置：非 200 → 不更新列表', async () => {
    mockGet.mockResolvedValue({ code: 500 })
    const w = await mountComp()
    expect((w.vm as any).configList).toEqual([])
  })

  it('editConfig 打开编辑对话框', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.editConfig({ key: 'SITE_NAME', value: 'v', description: 'd' })
    expect(vm.dialogVisible).toBe(true)
    expect(vm.editRow?.key).toBe('SITE_NAME')
  })

  it('saveConfig 成功 → 保存并刷新', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.editConfig({ key: 'SITE_NAME', value: '新值', description: 'd' })
    await vm.saveConfig()
    expect(mockPut).toHaveBeenCalledWith('/system/config', { key: 'SITE_NAME', value: '新值' })
    expect(ElMessage.success).toHaveBeenCalledWith('已保存')
    expect(vm.dialogVisible).toBe(false)
  })

  it('saveConfig 失败 → 错误提示', async () => {
    mockPut.mockRejectedValue(new Error('save failed'))
    const w = await mountComp()
    const vm = w.vm as any
    vm.editConfig({ key: 'SITE_NAME', value: 'v', description: 'd' })
    await vm.saveConfig()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
  })

  it('saveConfig：无编辑行 → 不请求', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.editRow = null
    await vm.saveConfig()
    expect(mockPut).not.toHaveBeenCalled()
  })

  it('exportConfig 导出 JSON 文件', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const clickSpy = vi.fn()
    vi.spyOn(document, 'createElement').mockImplementation(() => {
      return { href: '', download: '', click: clickSpy } as unknown as HTMLElement
    })
    vm.exportConfig()
    expect(clickSpy).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('配置已导出')
    vi.restoreAllMocks()
  })

  it('刷新按钮点击 → loadConfig', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const before = mockGet.mock.calls.length
    const refreshBtn = w
      .findAll('button')
      .find((b) => b.text().includes('刷新'))
    expect(refreshBtn).toBeTruthy()
    await refreshBtn!.trigger('click')
    await flushPromises()
    expect(mockGet.mock.calls.length).toBeGreaterThan(before)
    expect(vm.loading).toBe(false)
  })

  it('triggerImport 触发文件选择', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const clickSpy = vi.fn()
    ;(vm.fileInput as any) = { click: clickSpy }
    vm.triggerImport()
    expect(clickSpy).toHaveBeenCalled()
  })

  it('handleFileImport：无文件 → 返回', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleFileImport({ target: { files: [] } })
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleFileImport：导入成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const file = { text: vi.fn().mockResolvedValue(JSON.stringify({ A: '1' })) }
    await vm.handleFileImport({ target: { files: [file] } })
    expect(mockPost).toHaveBeenCalledWith('/system/config/import/json', { A: '1' })
    expect(ElMessage.success).toHaveBeenCalledWith('配置已导入')
  })

  it('handleFileImport：JSON 解析失败 → 错误提示', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const file = { text: vi.fn().mockResolvedValue('not-json') }
    await vm.handleFileImport({ target: { files: [file] } })
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败，请检查文件格式')
  })

  it('handleFileImport：接口失败 → 错误提示', async () => {
    mockPost.mockRejectedValue(new Error('import failed'))
    const w = await mountComp()
    const vm = w.vm as any
    const file = { text: vi.fn().mockResolvedValue('{}') }
    await vm.handleFileImport({ target: { files: [file] } })
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败，请检查文件格式')
  })

  it('resetConfig：确认成功（有默认配置）→ 批量写入', async () => {
    mockGet.mockResolvedValue({ data: { A: 1, B: 'x' } })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.resetConfig()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mockPut).toHaveBeenCalledWith('/system/config', {
      items: [
        { key: 'A', value: '1' },
        { key: 'B', value: 'x' },
      ],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已恢复默认配置')
  })

  it('resetConfig：无默认配置 → 跳过写入仍提示', async () => {
    mockGet.mockResolvedValue({ code: 200, data: {} })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.resetConfig()
    expect(mockPut).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('已恢复默认配置')
  })

  it('编辑对话框：敏感/非敏感输入 + 保存/取消按钮', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    // 非敏感配置编辑（input[0] 为禁用的配置项名）
    vm.editConfig({ key: 'SITE_NAME', value: 'old', description: '站点', sensitive: false })
    await nextTick()
    const dialogInputs = w.findAll('.el-dialog-stub input')
    expect(dialogInputs.length).toBeGreaterThanOrEqual(3)
    await dialogInputs[1].setValue('新站点名')
    expect(vm.editRow?.value).toBe('新站点名')
    // 敏感配置编辑（密码输入框）
    vm.editConfig({ key: 'SECRET_KEY', value: 'xxx', description: 'd', sensitive: true })
    await nextTick()
    const sensitiveInputs = w.findAll('.el-dialog-stub input')
    await sensitiveInputs[1].setValue('new-secret')
    expect(vm.editRow?.value).toBe('new-secret')
    // 说明字段
    await sensitiveInputs[2].setValue('新的说明')
    expect(vm.editRow?.description).toBe('新的说明')
    // 对话框 update:modelValue 关闭
    const dialog = w.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.dialogVisible).toBe(false)
    // 保存按钮（footer）点击
    vm.editConfig({ key: 'SITE_NAME', value: 'v', description: 'd', sensitive: false })
    await nextTick()
    const saveBtns = w.findAll('button').filter((b) => b.text().includes('保存'))
    for (const b of saveBtns) {
      await b.trigger('click')
    }
    expect(mockPut).toHaveBeenCalled()
    // 取消按钮（footer）点击 → 关闭对话框
    vm.editConfig({ key: 'SITE_NAME', value: 'v', description: 'd', sensitive: false })
    await nextTick()
    const cancelBtn = w
      .findAll('button')
      .find((b) => b.text().includes('取消'))
    await cancelBtn!.trigger('click')
    await nextTick()
    expect(vm.dialogVisible).toBe(false)
    // 编辑按钮（表格行）点击
    const editBtns = w.findAll('button').filter((b) => b.text().includes('编辑'))
    expect(editBtns.length).toBeGreaterThan(0)
    await editBtns[0].trigger('click')
    expect(vm.dialogVisible).toBe(true)
  })

  it('resetConfig：默认配置为空 → 跳过写入', async () => {
    mockGet.mockResolvedValue(null)
    const w = await mountComp()
    const vm = w.vm as any
    await vm.resetConfig()
    expect(mockPut).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('已恢复默认配置')
  })

  it('resetConfig：用户取消 → 无操作', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    const vm = w.vm as any
    await vm.resetConfig()
    expect(mockGet).not.toHaveBeenCalledWith('/system/config/defaults')
  })

  describe('外观主题（T2.4）', () => {
    it('挂载时应用已存主题到 data-theme', async () => {
      const w = await mountComp()
      expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    })

    it('applyTheme 切换主题并持久化到 store', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.applyTheme('dark')
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
      expect(configStore.setTheme).toHaveBeenCalledWith('dark')
      expect(vm.currentTheme).toBe('dark')
    })

    it('applyTheme 非法主题回退 light', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.applyTheme('neon')
      expect(document.documentElement.getAttribute('data-theme')).toBe('light')
      expect(vm.currentTheme).toBe('light')
    })

    it('applyTheme default 移除 data-theme 属性（回到军绿默认）', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      document.documentElement.setAttribute('data-theme', 'outdoor')
      vm.applyTheme('default')
      expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
      expect(configStore.setTheme).toHaveBeenCalledWith('default')
      expect(vm.currentTheme).toBe('default')
    })
  })
})

describe('配置 value 类型分支', () => {
  it('字符串原样/对象序列化', async () => {
    const wrapper = await mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockResolvedValueOnce({ items: [
      { key: 's', value: 'plain', description: 'd' },
      { key: 'o', value: { a: 1 } },
    ] })
    await vm.loadConfig()
    const s = vm.configList.find((c: any) => c.key === 's')
    const o = vm.configList.find((c: any) => c.key === 'o')
    expect(s.value).toBe('plain')
    expect(o.value).toBe('{"a":1}')
    wrapper.unmount()
  })
})
