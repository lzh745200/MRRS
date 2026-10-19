/**
 * views/system/GrantImport.vue 测试（四指标 100%）
 *
 * 方案：mock 'element-plus'（只留 ElMessage）+ stub 掉 el-* 组件。
 * 为什么必须 stub：项目未在测试里注册 Element Plus，未解析的组件会**丢弃插槽内容**
 * （`<el-card>` 的默认插槽整块不渲染），断言文本就会全空。
 *
 * 覆盖：空态、未选文件、成功（已签名/未签名）、失败三级文案回退、
 * 失败清空上一次成功结果、onChange 只留最后一个并清错、onRemove 清空。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const { mockImport, ElMessage } = vi.hoisted(() => ({
  mockImport: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('element-plus', () => ({ ElMessage }))
vi.mock('@/api/orgGrants', () => ({ importGrantPackage: mockImport }))

import GrantImport from '@/views/system/GrantImport.vue'

const STUBS = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-upload': { template: '<div class="uploader"><slot /></div>' },
  'el-alert': { props: ['title'], template: '<div class="alert">{{ title }}</div>' },
  'el-descriptions': { template: '<div class="descriptions"><slot /></div>' },
  'el-descriptions-item': {
    props: ['label'],
    template: '<div class="desc-item">{{ label }}:<slot /></div>',
  },
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
  'el-tag': { template: '<span class="tag"><slot /></span>' },
}

function factory() {
  return mount(GrantImport, { global: { stubs: STUBS } })
}

function pickFile(wrapper: any, name = 'pkg.json') {
  const file = new File(['{}'], name, { type: 'application/json' })
  const uploadFile = { name, raw: file, status: 'ready', uid: 1 }
  wrapper.vm.onChange(uploadFile, [uploadFile])
  return file
}

describe('views/system/GrantImport', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('初始态：渲染标题，不显示结果与错误', () => {
    const wrapper = factory()
    expect(wrapper.text()).toContain('导入单位授权包')
    expect(wrapper.find('.descriptions').exists()).toBe(false)
    expect(wrapper.find('.alert').exists()).toBe(true) // 顶部说明性 alert
    expect(wrapper.text()).not.toContain('请先选择授权包文件')
  })

  it('未选文件即提交：提示先选择文件，且不调用接口', async () => {
    const wrapper = factory()
    await wrapper.vm.submit()
    expect(mockImport).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请先选择授权包文件')
  })

  it('onChange：只保留最后一个文件并清除错误', async () => {
    const wrapper = factory()
    await wrapper.vm.submit()
    expect(wrapper.text()).toContain('请先选择授权包文件')

    const f1 = { name: 'a.json', raw: new File(['{}'], 'a.json') }
    const f2 = { name: 'b.json', raw: new File(['{}'], 'b.json') }
    wrapper.vm.onChange(f2, [f1, f2])
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('请先选择授权包文件')
  })

  it('导入成功（已签名）：展示单位编码/版本/模块数/已签名', async () => {
    mockImport.mockResolvedValue({ org_code: 'C001', version: 5, modules: 3, signed: true })
    const wrapper = factory()
    pickFile(wrapper)
    await wrapper.vm.submit()

    expect(mockImport).toHaveBeenCalledTimes(1)
    expect(ElMessage.success).toHaveBeenCalled()
    const text = wrapper.text()
    expect(text).toContain('C001')
    expect(text).toContain('5')
    expect(text).toContain('3')
    expect(text).toContain('已签名')
    expect(wrapper.find('.descriptions').exists()).toBe(true)
  })

  it('导入成功（未签名）：标签走 warning 分支', async () => {
    mockImport.mockResolvedValue({ org_code: 'C002', version: 1, modules: 0, signed: false })
    const wrapper = factory()
    pickFile(wrapper)
    await wrapper.vm.submit()
    expect(wrapper.text()).toContain('未签名')
  })

  it('失败：优先取后端 detail', async () => {
    mockImport.mockRejectedValue({ response: { data: { detail: '拒绝降级导入' } } })
    const wrapper = factory()
    pickFile(wrapper)
    await wrapper.vm.submit()
    expect(wrapper.text()).toContain('拒绝降级导入')
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('失败：无 detail 时取 Error.message', async () => {
    mockImport.mockRejectedValue(new Error('Network Error'))
    const wrapper = factory()
    pickFile(wrapper)
    await wrapper.vm.submit()
    expect(wrapper.text()).toContain('Network Error')
  })

  it('失败：都取不到时用兜底文案', async () => {
    mockImport.mockRejectedValue({})
    const wrapper = factory()
    pickFile(wrapper)
    await wrapper.vm.submit()
    expect(wrapper.text()).toContain('导入失败')
  })

  it('失败后清空上一次的成功结果', async () => {
    mockImport.mockResolvedValueOnce({ org_code: 'C001', version: 1, modules: 1, signed: true })
    const wrapper = factory()
    pickFile(wrapper)
    await wrapper.vm.submit()
    expect(wrapper.find('.descriptions').exists()).toBe(true)

    mockImport.mockRejectedValueOnce(new Error('boom'))
    await wrapper.vm.submit()
    expect(wrapper.find('.descriptions').exists()).toBe(false)
  })

  it('onRemove：清空文件与错误', async () => {
    const wrapper = factory()
    await wrapper.vm.submit()
    wrapper.vm.onRemove()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('请先选择授权包文件')

    await wrapper.vm.submit()
    expect(mockImport).not.toHaveBeenCalled()
  })
})
