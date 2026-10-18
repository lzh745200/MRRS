/**
 * views/reportTemplates/components/ReportOutputDialog.vue 测试（W22 唯一执行者）
 *
 * 覆盖：export 模式（年度/四种格式/文件下载 Blob 与字符串回退/成功与失败/缺失模板/缺失年度）、
 * print 模式（自动加载预览/三种行字段与 columns 派生/列名 label/空值占位/加载中/失败/重新加载/打印/无数据告警）、
 * 打开重置与关闭清理分支。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  get: vi.fn(),
  apiRequest: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage: mocks.ElMessage }))
vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mocks.get(...args),
  apiRequest: (...args: any[]) => mocks.apiRequest(...args),
}))

import ReportOutputDialog from '@/views/reportTemplates/components/ReportOutputDialog.vue'

const ElDialogStub = {
  name: 'ElDialog',
  props: ['modelValue', 'title', 'width'],
  emits: ['update:modelValue', 'closed'],
  template: '<div v-if="modelValue" class="dialog-stub"><h3>{{ title }}</h3><slot /></div>',
}
const ElFormStub = { name: 'ElForm', template: '<div class="form-stub"><slot /></div>' }
const ElFormItemStub = {
  name: 'ElFormItem',
  props: ['label'],
  template: '<div class="form-item-stub" :data-label="label"><slot /></div>',
}
const ElInputStub = {
  name: 'ElInput',
  props: ['modelValue', 'type', 'placeholder'],
  emits: ['update:modelValue'],
  template:
    '<input class="input-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}
const ElSelectStub = {
  name: 'ElSelect',
  props: ['modelValue'],
  emits: ['update:modelValue', 'change'],
  template: '<div class="select-stub" :data-value="modelValue"><slot /></div>',
}
const ElOptionStub = { name: 'ElOption', props: ['label', 'value'], template: '<span />' }
const ElButtonStub = {
  name: 'ElButton',
  props: ['type', 'loading'],
  emits: ['click'],
  template: '<button class="btn-stub" @click="$emit(\'click\')"><slot /></button>',
}

const stubs = {
  'el-dialog': ElDialogStub,
  'el-form': ElFormStub,
  'el-form-item': ElFormItemStub,
  'el-input': ElInputStub,
  'el-select': ElSelectStub,
  'el-option': ElOptionStub,
  'el-button': ElButtonStub,
}

const TEMPLATE = { id: 7, name: '帮扶村季度报表', module: 'village' }

function mountDialog(
  options: {
    mode?: 'export' | 'print'
    template?: typeof TEMPLATE | null
    modelValue?: boolean
  } = {}
): VueWrapper {
  return mount(ReportOutputDialog, {
    props: {
      modelValue: options.modelValue ?? true,
      mode: options.mode ?? 'export',
      template: options.template === undefined ? TEMPLATE : options.template,
    },
    global: { renderStubDefaultSlot: true, stubs },
  })
}

async function clickButton(wrapper: VueWrapper, text: string): Promise<void> {
  const btn = wrapper.findAll('button.btn-stub').find((b) => b.text().trim() === text)
  expect(btn, `按钮「${text}」`).toBeTruthy()
  await btn!.trigger('click')
  await flushPromises()
}

const CURRENT_YEAR = new Date().getFullYear()

describe('ReportOutputDialog.vue（报表导出 / 打印预览）', () => {
  let printSpy: any

  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ data: { columns: [], rows: [] } })
    mocks.apiRequest.mockResolvedValue(new Blob(['x'], { type: 'application/octet-stream' }))
    printSpy = vi.fn()
    ;(window as any).print = printSpy
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('export 模式：默认年度 + Excel 格式，导出下载文件并提示', async () => {
    const wrapper = mountDialog()
    expect(wrapper.find('.dialog-stub h3').text()).toBe('导出报表数据')
    expect(wrapper.text()).toContain('帮扶村季度报表')

    const createSpy = vi.spyOn(URL, 'createObjectURL')
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    await clickButton(wrapper, '导出报表')
    expect(mocks.apiRequest).toHaveBeenCalledWith({
      method: 'POST',
      url: '/report-templates/7/export',
      params: { format: 'xlsx', year: CURRENT_YEAR },
      responseType: 'blob',
    })
    expect(createSpy).toHaveBeenCalled()
    expect(anchorClick).toHaveBeenCalled()
    expect(revokeSpy).toHaveBeenCalled()
    expect(mocks.ElMessage.success).toHaveBeenCalledWith(
      `已导出 帮扶村季度报表_${CURRENT_YEAR}.xlsx`
    )
  })

  it('export 模式：四种格式均可导出（含非 Blob 响应回退）', async () => {
    const wrapper = mountDialog()
    const select = wrapper.findComponent(ElSelectStub)
    mocks.apiRequest.mockResolvedValue('plain-bytes')

    for (const format of ['csv', 'docx', 'pdf']) {
      select.vm.$emit('update:modelValue', format)
      await nextTick()
      await clickButton(wrapper, '导出报表')
      expect(mocks.apiRequest).toHaveBeenLastCalledWith(
        expect.objectContaining({
          params: { format, year: CURRENT_YEAR },
        })
      )
      expect(mocks.ElMessage.success).toHaveBeenLastCalledWith(
        expect.stringContaining(`.${format}`)
      )
    }
  })

  it('export 模式：缺失模板 / 缺失年度时告警且不发请求', async () => {
    let wrapper = mountDialog({ template: null })
    await clickButton(wrapper, '导出报表')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('模板信息缺失，无法导出')
    expect(mocks.apiRequest).not.toHaveBeenCalled()

    wrapper = mountDialog()
    // 年度输入框清空（v-model.number → 0）
    await wrapper.find('.input-stub').setValue('')
    await clickButton(wrapper, '导出报表')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('请输入报表年度')
    expect(mocks.apiRequest).not.toHaveBeenCalled()
  })

  it('export 模式：失败时展示后端详情或兜底文案', async () => {
    const wrapper = mountDialog()
    mocks.apiRequest.mockRejectedValueOnce({ response: { data: { detail: '模板字段为空' } } })
    await clickButton(wrapper, '导出报表')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('模板字段为空')

    mocks.apiRequest.mockRejectedValueOnce(new Error('network'))
    await clickButton(wrapper, '导出报表')
    expect(mocks.ElMessage.error).toHaveBeenLastCalledWith('导出失败')
  })

  it('print 模式：打开自动加载预览并按 columns 渲染表格', async () => {
    mocks.get.mockResolvedValue({
      data: {
        columns: [{ key: 'village_name', label: '帮扶村名称' }, { key: 'population' }],
        rows: [
          { village_name: '甲村', population: 1200 },
          { village_name: '', population: null },
        ],
      },
    })
    const wrapper = mountDialog({ mode: 'print' })
    await flushPromises()

    expect(wrapper.find('.dialog-stub h3').text()).toBe('报表打印预览')
    expect(mocks.get).toHaveBeenCalledWith('/report-templates/7/print-data', {
      year: CURRENT_YEAR,
    })
    // 表头使用 columns.label（缺失 label 时回退 key）
    expect(wrapper.find('.report-print-table thead').text()).toContain('帮扶村名称')
    expect(wrapper.find('.report-print-table thead').text()).toContain('population')
    // 空值占位 -
    expect(wrapper.findAll('.report-print-table tbody tr')[1].text()).toContain('-')

    await clickButton(wrapper, '打印')
    expect(printSpy).toHaveBeenCalledTimes(1)
  })

  it('print 模式：无 columns 时从首行派生列；items/data 行字段兼容', async () => {
    mocks.get.mockResolvedValueOnce({ items: [{ fund: 1, type: 'A' }] })
    let wrapper = mountDialog({ mode: 'print' })
    await flushPromises()
    expect(wrapper.find('.report-print-table thead').text()).toContain('fund')
    expect(wrapper.find('.report-print-table thead').text()).toContain('type')

    mocks.get.mockResolvedValueOnce({ data: { data: [{ x: 1 }] } })
    wrapper = mountDialog({ mode: 'print' })
    await flushPromises()
    expect(wrapper.find('.report-print-table thead').text()).toContain('x')

    // 无行数据 → 空态；null 响应也按空处理
    mocks.get.mockResolvedValueOnce({ data: { rows: 'not-array' } })
    wrapper = mountDialog({ mode: 'print' })
    await flushPromises()
    expect(wrapper.text()).toContain('暂无可打印数据')

    mocks.get.mockResolvedValueOnce(null)
    wrapper = mountDialog({ mode: 'print' })
    await flushPromises()
    expect(wrapper.text()).toContain('暂无可打印数据')
  })

  it('print 模式：加载中态、失败提示与重新加载', async () => {
    let resolveGet!: (value: unknown) => void
    mocks.get.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveGet = resolve
        })
    )
    const wrapper = mountDialog({ mode: 'print' })
    await nextTick()
    expect(wrapper.text()).toContain('预览数据加载中…')

    resolveGet({ rows: [{ a: 1 }] })
    await flushPromises()
    expect(wrapper.find('.report-print-table').exists()).toBe(true)

    // 重新加载失败 → 错误详情
    mocks.get.mockRejectedValueOnce({ response: { data: { detail: '无权限' } } })
    await clickButton(wrapper, '重新加载预览')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('无权限')
    expect(wrapper.text()).toContain('暂无可打印数据')

    // 无详情时兜底文案
    mocks.get.mockRejectedValueOnce(new Error('boom'))
    await clickButton(wrapper, '重新加载预览')
    expect(mocks.ElMessage.error).toHaveBeenLastCalledWith('预览数据加载失败')
  })

  it('print 模式：缺失模板 / 无数据时打印告警', async () => {
    let wrapper = mountDialog({ mode: 'print', template: null })
    await flushPromises()
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('模板信息缺失，无法预览')
    expect(mocks.get).not.toHaveBeenCalled()

    mocks.get.mockResolvedValue({ rows: [] })
    wrapper = mountDialog({ mode: 'print' })
    await flushPromises()
    await clickButton(wrapper, '打印')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('暂无可打印数据')
    expect(printSpy).not.toHaveBeenCalled()
  })

  it('打开时重置年度/格式；关闭时清理预览数据', async () => {
    mocks.get.mockResolvedValue({ rows: [{ a: 1 }] })
    const wrapper = mountDialog({ mode: 'print', modelValue: false })
    await nextTick()
    expect(mocks.get).not.toHaveBeenCalled()

    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(1)

    wrapper.findComponent(ElDialogStub).vm.$emit('closed')
    await nextTick()
    expect(wrapper.find('.report-print-table').exists()).toBe(false)

    // 再次打开会重新拉取
    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    expect(mocks.get).toHaveBeenCalledTimes(2)
  })

  it('模块标签映射：已知模块 / 未知模块 / 缺失模块', async () => {
    let wrapper = mountDialog({ template: { id: 1, name: 'A', module: 'village' } })
    expect(wrapper.text()).toContain('帮扶村')

    wrapper = mountDialog({ template: { id: 1, name: 'A', module: 'weird' } })
    expect(wrapper.text()).toContain('weird')

    wrapper = mountDialog({ template: { id: 1, name: 'A' } })
    expect(wrapper.find('.report-output-module').text()).toBe('-')
  })

  it('导出文件名：模板无名称时回退「报表」；el-dialog 关闭同步 v-model', async () => {
    const wrapper = mountDialog({ template: { id: 9 } })
    vi.spyOn(URL, 'createObjectURL')
    vi.spyOn(URL, 'revokeObjectURL')
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await clickButton(wrapper, '导出报表')
    expect(mocks.ElMessage.success).toHaveBeenCalledWith(`已导出 报表_${CURRENT_YEAR}.xlsx`)

    wrapper.findComponent(ElDialogStub).vm.$emit('update:modelValue', false)
    await nextTick()
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])
  })

  it('预览列派生：空数据 / 字符串列 / 无 key 对象列 / 无列且无行', async () => {
    // 弹窗未打开：printData 为空 → 列清单为空（覆盖 !data 分支）
    const closed = mountDialog({ mode: 'print', modelValue: false })
    expect((closed.vm as any).printColumns).toEqual([])

    mocks.get.mockResolvedValueOnce({
      columns: ['plain', { key: 'k' }, { label: '无key' }],
      rows: [{ a: 1 }],
    })
    let wrapper = mountDialog({ mode: 'print' })
    await flushPromises()
    expect((wrapper.vm as any).printColumns).toEqual(['plain', 'k', '[object Object]'])

    mocks.get.mockResolvedValueOnce({})
    wrapper = mountDialog({ mode: 'print' })
    await flushPromises()
    expect((wrapper.vm as any).printColumns).toEqual([])
  })
})
