/**
 * views/system/BackupManagement.vue — 跨密钥恢复（allow_key_mismatch）UI 流程
 *
 * 契约（backend/app/services/backup_service.py 的 KEY_MISMATCH_MESSAGE）：
 * - 先**不带参**恢复；备份的 PII 密钥指纹与本机不一致时后端返回 **409**，
 *   detail 文案含「不同密钥的机器…敏感字段将不可读」；
 * - 前端此时不得静默强制：展示后端 detail + 危险勾选，用户勾选后点「强制恢复」
 *   并经 `useDangerConfirm().confirmDanger` 二次确认，才带 `allow_key_mismatch=true` 重试**一次**；
 * - 取消 → 不重试、不抛错、弹窗保持原状态；
 * - 其它错误码行为不变（直接 ElMessage.error）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, confirmMock, mockGet, mockPost, mockPut, mockDel } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, prompt: vi.fn() },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: {
    getToken: vi.fn(() => 'tok'),
    getUser: () => ({ role: 'admin' }),
  },
}))

import BackupManagement from '@/views/system/BackupManagement.vue'

const KEY_MISMATCH_DETAIL =
  '备份来自不同密钥的机器，恢复后敏感字段（身份证号/联系电话等）将不可读；' +
  '如确认使用旧密钥，请先导入密钥或使用强制恢复（allow_key_mismatch=true）。'

/** 危险勾选文案（必须明确"不可读风险"） */
const DANGER_LABEL = '我确认：该备份来自不同密钥的机器，恢复后敏感字段（身份证号/联系电话等）可能不可读'

function mismatchError(detail = KEY_MISMATCH_DETAIL) {
  return { response: { status: 409, data: { detail } } }
}

const stubs = {
  'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-alert': {
    props: ['title', 'description'],
    template: '<div class="el-alert-stub">{{ title }} {{ description }}</div>',
  },
  'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
  'el-table-column': {
    template: '<div class="el-table-column-stub"><slot :row="row" /></div>',
    data() {
      return { row: { file_name: 'bak-a.zip', created_at: '2024-01-01T00:00:00Z' } }
    },
  },
  'el-dialog': {
    template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
  },
  'el-button': {
    name: 'ElButton',
    props: ['disabled', 'loading'],
    emits: ['click'],
    template:
      '<button class="el-button-stub" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  'el-checkbox': {
    name: 'ElCheckbox',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<label class="el-checkbox-stub"><slot /></label>',
  },
  'el-upload': { template: '<div class="el-upload-stub"><slot /><slot name="tip" /></div>' },
  'el-descriptions': { template: '<dl><slot /></dl>' },
  'el-descriptions-item': { template: '<div><slot /></div>' },
}

async function mountComp() {
  const wrapper = mount(BackupManagement, { global: { stubs } })
  await flushPromises()
  await nextTick()
  return wrapper
}

function findButton(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button').find((b) => b.text().includes(text))
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useRealTimers()
  mockGet.mockResolvedValue({ data: {} })
  mockPost.mockResolvedValue({ success: true })
  mockPut.mockResolvedValue({ success: true })
  mockDel.mockResolvedValue({ success: true })
  confirmMock.mockResolvedValue('confirm')
})

describe('BackupManagement 跨密钥恢复 — 先不带参，409 才进入强制路径', () => {
  it('首次恢复不带 allow_key_mismatch=true；409 显示后端 detail 且不弹通用错误', async () => {
    mockPost.mockRejectedValueOnce(mismatchError())
    const wrapper = await mountComp()
    const vm = wrapper.vm as any

    vm.handleRestore({ file_name: 'cross-key.zip', is_encrypted: false })
    await vm.confirmRestore()

    const [url, payload] = mockPost.mock.calls.at(-1)!
    expect(url).toBe('/system/backup/restore')
    expect(payload).toEqual({
      filename: 'cross-key.zip',
      password: null,
      allow_key_mismatch: false,
    })
    expect(vm.keyMismatchDetail).toContain('不同密钥')
    expect(vm.restoreDialogVisible).toBe(true) // 保持原状态，等用户确认
    expect(vm.restoring).toBe(false)
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('409 后展示危险勾选与「强制恢复」按钮；未勾选时按钮禁用', async () => {
    mockPost.mockRejectedValueOnce(mismatchError())
    const wrapper = await mountComp()
    const vm = wrapper.vm as any

    vm.handleRestore({ file_name: 'cross-key.zip', is_encrypted: false })
    await vm.confirmRestore()
    await nextTick()

    expect(wrapper.text()).toContain(DANGER_LABEL)
    expect(wrapper.text()).toContain('不同密钥') // 后端 detail 可见
    const forceBtn = findButton(wrapper, '强制恢复')
    expect(forceBtn).toBeTruthy()
    expect(forceBtn!.attributes('disabled')).toBeDefined()

    vm.restoreForm.allowKeyMismatch = true
    await nextTick()
    expect(findButton(wrapper, '强制恢复')!.attributes('disabled')).toBeUndefined()
  })

  it('未勾选危险勾选 → 拒绝强制恢复，不弹二次确认也不重试', async () => {
    mockPost.mockRejectedValueOnce(mismatchError())
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'cross-key.zip' })
    await vm.confirmRestore()
    const callsBefore = mockPost.mock.calls.length

    vm.restoreForm.allowKeyMismatch = false
    await vm.forceRestoreWithKeyMismatch()

    expect(confirmMock).not.toHaveBeenCalled()
    expect(mockPost.mock.calls.length).toBe(callsBefore)
    expect(ElMessage.warning).toHaveBeenCalled()
  })

  it('勾选 + 二次确认 → 带 allow_key_mismatch=true 重试一次并成功', async () => {
    mockPost.mockRejectedValueOnce(mismatchError())
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'cross-key.zip', is_encrypted: false })
    await vm.confirmRestore()

    vm.restoreForm.allowKeyMismatch = true
    mockPost.mockResolvedValueOnce({ success: true })
    vi.useFakeTimers()
    await vm.forceRestoreWithKeyMismatch()

    expect(confirmMock).toHaveBeenCalledTimes(1)
    expect(confirmMock.mock.calls[0][0]).toContain('不同密钥')
    const [url, payload] = mockPost.mock.calls.at(-1)!
    expect(url).toBe('/system/backup/restore')
    expect(payload).toEqual({
      filename: 'cross-key.zip',
      password: null,
      allow_key_mismatch: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('系统恢复成功，请重新登录')
    expect(vm.restoreDialogVisible).toBe(false)
    expect(vm.keyMismatchDetail).toBe('')
    vi.advanceTimersByTime(2000)
    vi.useRealTimers()
  })

  it('二次确认取消 → 不重试、不抛错、弹窗与勾选状态保持', async () => {
    mockPost.mockRejectedValueOnce(mismatchError())
    confirmMock.mockRejectedValueOnce('cancel')
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'cross-key.zip' })
    await vm.confirmRestore()
    const callsBefore = mockPost.mock.calls.length

    vm.restoreForm.allowKeyMismatch = true
    await expect(vm.forceRestoreWithKeyMismatch()).resolves.toBeUndefined()

    expect(confirmMock).toHaveBeenCalledTimes(1)
    expect(mockPost.mock.calls.length).toBe(callsBefore)
    expect(vm.restoreDialogVisible).toBe(true)
    expect(vm.keyMismatchDetail).toContain('不同密钥')
    expect(vm.restoring).toBe(false)
  })

  it('409 但 detail 不含「密钥」→ 按普通错误处理，不进入强制路径', async () => {
    mockPost.mockRejectedValueOnce(mismatchError('备份文件与当前系统不兼容'))
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'x.zip' })
    await vm.confirmRestore()

    expect(vm.keyMismatchDetail).toBe('')
    expect(ElMessage.error).toHaveBeenCalledWith('备份文件与当前系统不兼容')
  })

  it('非 409 错误（500/网络错误）行为不变：直接报错，不出现强制恢复入口', async () => {
    mockPost.mockRejectedValueOnce({ response: { status: 500, data: { detail: '恢复备份失败' } } })
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'x.zip' })
    await vm.confirmRestore()

    expect(ElMessage.error).toHaveBeenCalledWith('恢复备份失败')
    expect(vm.keyMismatchDetail).toBe('')
    expect(findButton(wrapper, '强制恢复')).toBeUndefined()
  })

  it('重新打开恢复对话框会清空上一轮的密钥不一致状态与勾选', async () => {
    mockPost.mockRejectedValueOnce(mismatchError())
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'cross-key.zip' })
    await vm.confirmRestore()
    vm.restoreForm.allowKeyMismatch = true

    vm.handleRestore({ file_name: 'other.zip' })
    await nextTick()
    expect(vm.keyMismatchDetail).toBe('')
    expect(vm.restoreForm.allowKeyMismatch).toBe(false)
  })
})

describe('BackupManagement 跨密钥恢复 — 上传导入备份包', () => {
  it('上传恢复先带 allow_key_mismatch=false；409 后强制重试带 true', async () => {
    mockPost.mockRejectedValueOnce(mismatchError())
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    const file = new File(['zip'], 'cross-key.zip')
    vm.onImportFileChange({ raw: file })
    vm.importDialogVisible = true

    await vm.confirmImportRestore()
    const first = mockPost.mock.calls.at(-1)!
    expect(first[0]).toBe('/system/backup/upload-restore')
    expect((first[1] as FormData).get('allow_key_mismatch')).toBe('false')
    expect(vm.importKeyMismatchDetail).toContain('不同密钥')
    expect(vm.importDialogVisible).toBe(true)
    expect(ElMessage.error).not.toHaveBeenCalled()

    // 未勾选 → 拒绝
    vm.importForm.allowKeyMismatch = false
    await vm.forceImportRestoreWithKeyMismatch()
    expect(confirmMock).not.toHaveBeenCalled()

    // 勾选 + 确认 → 带参重试一次
    vm.importForm.allowKeyMismatch = true
    mockPost.mockResolvedValueOnce({ success: true })
    vi.useFakeTimers()
    await vm.forceImportRestoreWithKeyMismatch()

    const second = mockPost.mock.calls.at(-1)!
    expect((second[1] as FormData).get('allow_key_mismatch')).toBe('true')
    expect((second[1] as FormData).get('file')).toBe(file)
    expect(ElMessage.success).toHaveBeenCalledWith('导入恢复成功，系统将重新登录')
    expect(vm.importDialogVisible).toBe(false)
    vi.advanceTimersByTime(2000)
    vi.useRealTimers()
  })

  it('上传恢复二次确认取消 → 不重试、状态保持', async () => {
    mockPost.mockRejectedValueOnce(mismatchError())
    confirmMock.mockRejectedValueOnce('cancel')
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.onImportFileChange({ raw: new File(['zip'], 'p.zip') })
    await vm.confirmImportRestore()
    const callsBefore = mockPost.mock.calls.length

    vm.importForm.allowKeyMismatch = true
    await expect(vm.forceImportRestoreWithKeyMismatch()).resolves.toBeUndefined()

    expect(mockPost.mock.calls.length).toBe(callsBefore)
    expect(vm.importKeyMismatchDetail).toContain('不同密钥')
    expect(vm.importing).toBe(false)
  })

  it('上传恢复非 409 错误行为不变', async () => {
    mockPost.mockRejectedValueOnce({ response: { status: 400, data: { detail: '备份已加密' } } })
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.onImportFileChange({ raw: new File(['zip'], 'p.zip') })
    await vm.confirmImportRestore()

    expect(ElMessage.error).toHaveBeenCalledWith('备份已加密')
    expect(vm.importKeyMismatchDetail).toBe('')
  })
})

describe('BackupManagement 跨密钥恢复 — 模板交互（勾选与按钮）', () => {
  it('勾选危险项写入表单；点击「确认恢复」「确认导入并恢复」走默认（不带参）路径', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any

    // 两个危险勾选：恢复弹窗 / 导入弹窗
    const boxes = wrapper.findAllComponents({ name: 'ElCheckbox' })
    expect(boxes.length).toBe(2)
    boxes[0].vm.$emit('update:modelValue', true)
    boxes[1].vm.$emit('update:modelValue', true)
    await nextTick()
    expect(vm.restoreForm.allowKeyMismatch).toBe(true)
    expect(vm.importForm.allowKeyMismatch).toBe(true)

    // 默认路径：即便勾选了危险项，首次恢复仍**不带** allow_key_mismatch
    vm.handleRestore({ file_name: 'nodefault.zip', is_encrypted: false })
    await nextTick()
    mockPost.mockResolvedValueOnce({ success: true })
    const restoreBtn = findButton(wrapper, '确认恢复')
    expect(restoreBtn).toBeTruthy()
    await restoreBtn!.trigger('click')

    let [url, payload] = mockPost.mock.calls.at(-1)!
    expect(url).toBe('/system/backup/restore')
    expect((payload as any).allow_key_mismatch).toBe(false)

    // 导入恢复按钮（文件已选情况下）
    vm.onImportFileChange({ raw: new File(['zip'], 'pkg.zip') })
    await nextTick()
    mockPost.mockResolvedValueOnce({ success: true })
    const importBtn = findButton(wrapper, '确认导入并恢复')
    expect(importBtn).toBeTruthy()
    await importBtn!.trigger('click')
    await flushPromises()

    const last = mockPost.mock.calls.at(-1)!
    expect(last[0]).toBe('/system/backup/upload-restore')
    expect((last[1] as FormData).get('allow_key_mismatch')).toBe('false')
    void vm
  })
})

describe('BackupManagement 跨密钥恢复 — 边界与兜底分支', () => {
  it('函数内部防御：直接以 forceKeyMismatch=true 调用但未勾选 → 警告且不发请求', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any

    vm.handleRestore({ file_name: 'guard.zip', is_encrypted: false })
    vm.restoreForm.allowKeyMismatch = false
    await vm.confirmRestore({ forceKeyMismatch: true })
    expect(ElMessage.warning).toHaveBeenCalled()
    expect(mockPost).not.toHaveBeenCalledWith('/system/backup/restore', expect.anything())

    vm.onImportFileChange({ raw: new File(['zip'], 'guard.zip') })
    vm.importForm.allowKeyMismatch = false
    await vm.confirmImportRestore({ forceKeyMismatch: true })
    expect(mockPost).not.toHaveBeenCalledWith('/system/backup/upload-restore', expect.anything())
  })

  it('强制恢复：无目标 / 无导入文件时安全返回，不发请求也不弹确认', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.restoreTarget = null
    vm.importFile = null
    await vm.forceRestoreWithKeyMismatch()
    await vm.forceImportRestoreWithKeyMismatch()
    expect(confirmMock).not.toHaveBeenCalled()
    expect(mockPost).not.toHaveBeenCalledWith('/system/backup/restore', expect.anything())
    expect(mockPost).not.toHaveBeenCalledWith('/system/backup/upload-restore', expect.anything())
  })

  it('未经过 409 直接强制（detail 为空）→ 用兜底文案二次确认；后端返回无 body 也视为成功', async () => {
    mockPost.mockResolvedValueOnce(undefined) // res?.success 的 optional chaining 空值侧
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'direct.zip', is_encrypted: false })
    vm.restoreForm.allowKeyMismatch = true
    vi.useFakeTimers()
    await vm.forceRestoreWithKeyMismatch()

    expect(confirmMock.mock.calls[0][0]).toContain('备份来自不同密钥的机器')
    const [, payload] = mockPost.mock.calls.at(-1)!
    expect((payload as any).allow_key_mismatch).toBe(true)
    expect(ElMessage.success).toHaveBeenCalled()
    vi.advanceTimersByTime(2000)
    vi.useRealTimers()
  })

  it('导入强制路径：detail 为空 → 兜底文案；后端无 body 也视为成功', async () => {
    mockPost.mockResolvedValueOnce(undefined)
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.onImportFileChange({ raw: new File(['zip'], 'direct.zip') })
    vm.importForm.allowKeyMismatch = true
    vi.useFakeTimers()
    await vm.forceImportRestoreWithKeyMismatch()

    expect(confirmMock.mock.calls[0][0]).toContain('备份包来自不同密钥的机器')
    expect(ElMessage.success).toHaveBeenCalledWith('导入恢复成功，系统将重新登录')
    vi.advanceTimersByTime(2000)
    vi.useRealTimers()
  })

  it('serverMessage 兜底：仅 userMessage 时用它；detail 非字符串时回落默认文案', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any

    mockPost.mockRejectedValueOnce({ userMessage: '网络连接失败，请检查服务是否启动' })
    vm.handleRestore({ file_name: 'a.zip' })
    await vm.confirmRestore()
    expect(ElMessage.error).toHaveBeenCalledWith('网络连接失败，请检查服务是否启动')

    mockPost.mockRejectedValueOnce({ response: { status: 500, data: { detail: { oops: 1 } } } })
    await vm.confirmRestore()
    expect(ElMessage.error).toHaveBeenCalledWith('恢复失败')

    mockPost.mockRejectedValueOnce({ userMessage: '上传链路异常' })
    vm.onImportFileChange({ raw: new File(['zip'], 'b.zip') })
    await vm.confirmImportRestore()
    expect(ElMessage.error).toHaveBeenCalledWith('上传链路异常')
  })
})
