import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const { post, pushSafe, ElMessage } = vi.hoisted(() => ({
  post: vi.fn(),
  pushSafe: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

vi.mock('@/api/request', () => ({ post }))
vi.mock('@/composables/useRouterSafe', () => ({ useRouterSafe: () => ({ pushSafe }) }))
vi.mock('element-plus', async () => {
  const actual = await vi.importActual<any>('element-plus')
  return { ...actual, ElMessage }
})

import Page from '@/views/auth/AccountPackageImport.vue'

function mountPage() {
  return mount(Page, { global: { plugins: [ElementPlus], stubs: { teleport: true } } })
}

describe('AccountPackageImport.vue', () => {
  beforeEach(() => vi.clearAllMocks())

  it('warns without file or password', async () => {
    const w = mountPage(); const vm = w.vm as any
    await vm.preview()
    expect(ElMessage.warning).toHaveBeenCalled()
    vm.file = new File(['x'], 'p.apkg'); vm.password = ''
    await vm.preview()
    expect(ElMessage.warning).toHaveBeenCalled()
  })

  it('previews, confirms and navigates to login', async () => {
    post.mockResolvedValueOnce({
      organization_code: '520100', organization_name: '市局', expires_at: '2030-01-01',
      accounts: [{ username: 'a', full_name: 'A', role: 'admin', data_scope: 'org' }],
    }).mockResolvedValueOnce({ organization_code: '520100', users: [{ user_id: 1, username: 'a' }] })
    const w = mountPage(); const vm = w.vm as any
    vm.file = new File(['x'], 'p.apkg'); vm.password = 'passw0rd-pass'
    await vm.preview(); await flushPromises()
    expect(vm.previewData.accounts[0].username).toBe('a')
    await vm.confirm(); await flushPromises()
    expect(vm.result.users[0].username).toBe('a')
    expect(ElMessage.success).toHaveBeenCalled()
    vm.goLogin()
    expect(pushSafe).toHaveBeenCalledWith('/login')
  })

  it('handles preview/confirm errors and file events', async () => {
    post.mockRejectedValue({ response: { data: { detail: { message: '包口令错误' } } } })
    const w = mountPage(); const vm = w.vm as any
    vm.onFileChange({ raw: new File(['x'], 'p.apkg') })
    expect(vm.file).not.toBeNull()
    vm.password = 'passw0rd-pass'
    await vm.preview()
    expect(ElMessage.error).toHaveBeenCalledWith('包口令错误')
    vm.previewData = { organization_code: '520100', organization_name: '市局', expires_at: '2030-01-01' }
    await vm.confirm()
    expect(ElMessage.error).toHaveBeenCalled()
    vm.onFileRemove()
    expect(vm.file).toBeNull()
    post.mockRejectedValue({ response: { data: { detail: '字符串错误' } } })
    vm.file = new File(['x'], 'p.apkg'); vm.password = 'passw0rd-pass'
    await vm.preview()
    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('warns confirm before preview and handles no raw file', async () => {
    const w = mountPage(); const vm = w.vm as any
    await vm.confirm()
    expect(ElMessage.warning).toHaveBeenCalled()
    vm.onFileChange({})
    expect(vm.file).toBeNull()
  })
})
