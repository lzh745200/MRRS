/**
 * components/dataPackage/ImportEncryptedDialog.vue 覆盖率攻坚
 *
 * 重点回归：加密包导入必须按后端三步契约串联
 * upload-encrypted（仅落盘建 pending）→ decrypt-preview（带密码）→ confirm-import（落库），
 * 任一步失败都必须如实报错，绝不能提示"导入成功"。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, mockPost } = vi.hoisted(() => {
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    mockPost: vi.fn(),
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn() },
}))

vi.mock('@/api/request', () => ({
  post: mockPost,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import ImportEncryptedDialog from '@/components/dataPackage/ImportEncryptedDialog.vue'

const UPLOAD_URL = '/data-packages/upload-encrypted'
const DECRYPT_URL = '/data-packages/decrypt-preview/42'
const CONFIRM_URL = '/data-packages/confirm-import/42'

/** 默认三步都成功的后端桩（各用例可按需覆盖单步） */
function mockThreeStepOk() {
  mockPost.mockImplementation((url: string) => {
    if (url === UPLOAD_URL) return Promise.resolve({ id: 42, status: 'pending' })
    if (url === DECRYPT_URL) return Promise.resolve({ package_id: 42, status: 'validated' })
    if (url === CONFIRM_URL)
      return Promise.resolve({ success: true, message: '导入并解决冲突完成' })
    return Promise.resolve({})
  })
}

function mountDialog(props = {}) {
  return mount(ImportEncryptedDialog, {
    props: { modelValue: true, ...props },
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-form': { name: 'ElForm', template: '<form><slot /></form>' },
        'el-upload': {
          name: 'ElUpload',
          props: ['modelValue', 'fileList'],
          emits: ['change', 'remove'],
          template: '<div class="upload-stub"><slot /><slot name="tip" /></div>',
        },
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<div class="input-stub" />',
        },
      },
    },
  })
}

/** 选中文件 + 通过表单校验，返回可直接调用 handleImport 的 wrapper */
async function readyToImport(props = {}) {
  const wrapper = mountDialog(props)
  await flushPromises()
  wrapper.vm.handleFileChange({ raw: new File(['x'], 'a.rrs') })
  wrapper.vm.formRef = { validate: vi.fn(() => Promise.resolve()) }
  wrapper.vm.form.password = '12345678'
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mockThreeStepOk()
})

describe('dataPackage/ImportEncryptedDialog.vue', () => {
  it('打开时重置', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.form.password = '12345678'
    wrapper.vm.selectedFile = new File(['x'], 'a.rrs')
    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    expect(wrapper.vm.form.password).toBe('')
    expect(wrapper.vm.selectedFile).toBeNull()
    wrapper.unmount()
  })

  it('未选文件时警告', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.vm.handleImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择数据包文件')
    expect(mockPost).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('导入成功：严格按 upload → decrypt-preview → confirm-import 三步串联', async () => {
    const wrapper = await readyToImport()
    await wrapper.vm.handleImport()

    // 第一步：上传（密码随 multipart 表单字段）
    expect(mockPost).toHaveBeenNthCalledWith(
      1,
      UPLOAD_URL,
      expect.any(FormData),
      expect.any(Object)
    )
    // 第二步：带密码解密预览（用第一步返回的数据包 ID）
    expect(mockPost).toHaveBeenNthCalledWith(2, DECRYPT_URL, { password: '12345678' })
    // 第三步：确认导入（后端以 {success, message} 表达业务成败；加密包需带上解密口令）
    expect(mockPost).toHaveBeenNthCalledWith(3, CONFIRM_URL, {
      conflict_strategy: 'KEEP_BOTH',
      password: '12345678',
    })

    expect(ElMessage.success).toHaveBeenCalledWith('导入并解决冲突完成')
    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(wrapper.emitted('success')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
    wrapper.unmount()
  })

  it('上传响应为 envelope（data.id）时同样能取到数据包 ID', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === UPLOAD_URL) return Promise.resolve({ data: { id: 7 } })
      if (url === '/data-packages/decrypt-preview/7') return Promise.resolve({ ok: true })
      if (url === '/data-packages/confirm-import/7')
        return Promise.resolve({ data: { success: true, message: '已导入' } })
      return Promise.resolve({})
    })
    const wrapper = await readyToImport()
    await wrapper.vm.handleImport()

    expect(mockPost).toHaveBeenNthCalledWith(2, '/data-packages/decrypt-preview/7', {
      password: '12345678',
    })
    // 加密包确认导入必须同时提交解密口令（后端 confirm-import 自行解密后落库）
    expect(mockPost).toHaveBeenNthCalledWith(3, '/data-packages/confirm-import/7', {
      conflict_strategy: 'KEEP_BOTH',
      password: '12345678',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已导入')
    wrapper.unmount()
  })

  it('上传未返回数据包 ID：如实报错且不再调用后续两步', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === UPLOAD_URL) return Promise.resolve({ message: '上传完成' })
      return Promise.resolve({ success: true })
    })
    const wrapper = await readyToImport()
    await wrapper.vm.handleImport()

    expect(mockPost).toHaveBeenCalledTimes(1)
    expect(ElMessage.error).toHaveBeenCalledWith('上传加密数据包失败：服务端未返回数据包 ID')
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(wrapper.emitted('success')).toBeUndefined()
    wrapper.unmount()
  })

  it('解密预览失败：如实报错，绝不调用 confirm-import、绝不报成功', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === UPLOAD_URL) return Promise.resolve({ id: 42 })
      if (url === DECRYPT_URL)
        return Promise.reject({ response: { data: { detail: '密码错误，请检查后重试' } } })
      return Promise.resolve({ success: true })
    })
    const wrapper = await readyToImport()
    await wrapper.vm.handleImport()

    expect(ElMessage.error).toHaveBeenCalledWith('密码错误，请检查后重试')
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(wrapper.emitted('success')).toBeUndefined()
    // confirm-import 未被调用（仅 upload + decrypt-preview）
    expect(mockPost).toHaveBeenCalledTimes(2)
    expect(mockPost).not.toHaveBeenCalledWith(CONFIRM_URL, expect.anything())
    wrapper.unmount()
  })

  it('确认导入返回 success=false（HTTP 200）：必须按失败处理并透出后端原因', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === UPLOAD_URL) return Promise.resolve({ id: 42 })
      if (url === DECRYPT_URL) return Promise.resolve({ ok: true })
      if (url === CONFIRM_URL)
        return Promise.resolve({ success: false, message: '数据包状态不正确: pending' })
      return Promise.resolve({})
    })
    const wrapper = await readyToImport()
    await wrapper.vm.handleImport()

    expect(ElMessage.error).toHaveBeenCalledWith('数据包状态不正确: pending')
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(wrapper.emitted('success')).toBeUndefined()
    // 失败时保持对话框打开、文件保留，便于用户重试
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.vm.selectedFile).toBeInstanceOf(File)
    wrapper.unmount()
  })

  it('确认导入返回空载荷：走默认失败文案', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === UPLOAD_URL) return Promise.resolve({ id: 42 })
      if (url === CONFIRM_URL) return Promise.resolve(null)
      return Promise.resolve({ ok: true })
    })
    const wrapper = await readyToImport()
    await wrapper.vm.handleImport()

    expect(ElMessage.error).toHaveBeenCalledWith('确认导入失败')
    expect(ElMessage.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('confirm 返回 success=true 但无 message：用默认成功文案', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === UPLOAD_URL) return Promise.resolve({ id: 42 })
      if (url === CONFIRM_URL) return Promise.resolve({ success: true })
      return Promise.resolve({ ok: true })
    })
    const wrapper = await readyToImport()
    await wrapper.vm.handleImport()

    expect(ElMessage.success).toHaveBeenCalledWith('加密数据包导入成功')
    expect(wrapper.emitted('success')).toBeTruthy()
    wrapper.unmount()
  })

  it('校验失败直接返回', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.handleFileChange({ raw: new File(['x'], 'a.rrs') })
    wrapper.vm.formRef = { validate: vi.fn(() => Promise.reject(new Error('bad'))) }
    await wrapper.vm.handleImport()
    expect(mockPost).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('移除文件清空选择', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.handleFileChange({ raw: new File(['x'], 'a.rrs') })
    expect(wrapper.vm.selectedFile).toBeInstanceOf(File)
    wrapper.vm.handleFileRemove()
    expect(wrapper.vm.selectedFile).toBeNull()
    expect(wrapper.vm.fileList).toEqual([])
    wrapper.unmount()
  })

  it('接口异常提示错误', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.handleFileChange({ raw: new File(['x'], 'a.rrs') })
    wrapper.vm.formRef = { validate: vi.fn(() => Promise.resolve()) }
    mockPost.mockRejectedValue({ response: { data: { detail: '解密失败' } } })
    await wrapper.vm.handleImport()
    expect(ElMessage.error).toHaveBeenCalledWith('解密失败')
    expect(wrapper.vm.submitting).toBe(false)
    wrapper.unmount()
  })

  it('错误对象无 detail 时回退 err.message，再回退默认文案', async () => {
    const wrapper = await readyToImport()
    mockPost.mockRejectedValue(new Error('网络中断'))
    await wrapper.vm.handleImport()
    expect(ElMessage.error).toHaveBeenCalledWith('网络中断')

    mockPost.mockRejectedValue({})
    await wrapper.vm.handleImport()
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')
    wrapper.unmount()
  })
})

it('模板事件处理器(dialog/upload/input)与分支补齐', async () => {
  const wrapper = mountDialog()
  await flushPromises()
  wrapper.findComponent({ name: 'ElDialog' }).vm.$emit('update:modelValue', false)
  expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
  for (const input of wrapper.findAllComponents({ name: 'ElInput' })) {
    input.vm.$emit('update:modelValue', 'pw123456')
  }
  expect(wrapper.vm.form.password).toBe('pw123456')
  // file.raw 为空 → null
  wrapper.vm.handleFileChange({ raw: null })
  expect(wrapper.vm.selectedFile).toBeNull()
  // formRef 缺失直接返回
  wrapper.vm.handleFileChange({ raw: new File(['x'], 'a.rrs') })
  wrapper.vm.formRef = null
  await wrapper.vm.handleImport()
  expect(mockPost).not.toHaveBeenCalled()
  wrapper.unmount()
})
