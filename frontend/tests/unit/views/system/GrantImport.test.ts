/**
 * views/system/GrantImport.vue 测试（R33 授权包导入）
 *
 * 覆盖：空态渲染、未选文件提示、成功（已签名/未签名两种标签）、
 * 三类失败文案回退（后端 detail → Error.message → 兜底）、
 * onChange 只保留最后一个文件并清错、onRemove 清空。
 *
 * 用 `defineExpose` 暴露的方法驱动，避免 jsdom 下 el-upload 的 change 事件时序不稳定。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const { mockImport } = vi.hoisted(() => ({ mockImport: vi.fn() }))

vi.mock('@/api/orgGrants', () => ({
  importGrantPackage: mockImport,
}))

import GrantImport from '@/views/system/GrantImport.vue'

function factory() {
  return mount(GrantImport, { global: { plugins: [ElementPlus] } })
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

  it('初始态：不显示结果与错误', () => {
    const wrapper = factory()
    expect(wrapper.text()).toContain('导入单位授权包')
    expect(wrapper.find('.el-descriptions').exists()).toBe(false)
    expect(wrapper.find('.el-alert--error').exists()).toBe(false)
  })

  it('未选文件即提交：提示先选择文件，且不调用接口', async () => {
    const wrapper = factory()
    await wrapper.vm.submit()
    expect(mockImport).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请先选择授权包文件')
  })

  it('onChange：只保留最后一个文件并清除错误', async () => {
    const wrapper = factory()
    await wrapper.vm.submit() // 先制造一条错误
    expect(wrapper.text()).toContain('请先选择授权包文件')

    const f1 = { name: 'a.json', raw: new File(['{}'], 'a.json') }
    const f2 = { name: 'b.json', raw: new File(['{}'], 'b.json') }
    wrapper.vm.onChange(f2, [f1, f2])
    expect(wrapper.text()).not.toContain('请先选择授权包文件')
  })

  it('导入成功（已签名）：展示单位编码/版本/模块数/已签名', async () => {
    mockImport.mockResolvedValue({ org_code: 'C001', version: 5, modules: 3, signed: true })
    const wrapper = factory()
    pickFile(wrapper)
    await wrapper.vm.submit()

    expect(mockImport).toHaveBeenCalledTimes(1)
    const text = wrapper.text()
    expect(text).toContain('C001')
    expect(text).toContain('5')
    expect(text).toContain('3')
    expect(text).toContain('已签名')
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
    expect(wrapper.find('.el-descriptions').exists()).toBe(true)

    mockImport.mockRejectedValueOnce(new Error('boom'))
    await wrapper.vm.submit()
    expect(wrapper.find('.el-descriptions').exists()).toBe(false)
  })

  it('onRemove：清空文件与错误', async () => {
    const wrapper = factory()
    await wrapper.vm.submit()
    wrapper.vm.onRemove()
    expect(wrapper.text()).not.toContain('请先选择授权包文件')

    await wrapper.vm.submit()
    expect(mockImport).not.toHaveBeenCalled()
  })
})
