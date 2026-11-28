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
    const w = mountPage()
    const vm = w.vm as any
    await vm.preview()
    expect(ElMessage.warning).toHaveBeenCalled()
    vm.file = new File(['x'], 'p.apkg')
    vm.password = ''
    await vm.preview()
    expect(ElMessage.warning).toHaveBeenCalled()
  })

  it('previews, confirms and navigates to login', async () => {
    post
      .mockResolvedValueOnce({
        organization_code: '520100',
        organization_name: '市局',
        expires_at: '2030-01-01',
        accounts: [{ username: 'a', full_name: 'A', role: 'admin', data_scope: 'org' }],
        authorization: { page_count: 2, edit_page_count: 1, view_page_count: 1, module_count: 2 },
      })
      .mockResolvedValueOnce({
        organization_code: '520100',
        users: [{ user_id: 1, username: 'a' }],
      })
    const w = mountPage()
    const vm = w.vm as any
    vm.file = new File(['x'], 'p.apkg')
    vm.password = 'passw0rd-pass'
    await vm.preview()
    await flushPromises()
    expect(vm.previewData.accounts[0].username).toBe('a')
    expect(vm.previewData.authorization.page_count).toBe(2)
    await vm.confirm()
    await flushPromises()
    expect(vm.result.users[0].username).toBe('a')
    expect(vm.result.organization_code).toBe('520100')
    expect(ElMessage.success).toHaveBeenCalled()
    vm.goLogin()
    expect(pushSafe).toHaveBeenCalledWith('/login')
  })

  it('handles preview/confirm errors and file events', async () => {
    post.mockRejectedValue({ response: { data: { detail: { message: '包口令错误' } } } })
    const w = mountPage()
    const vm = w.vm as any
    vm.onFileChange({ raw: new File(['x'], 'p.apkg') })
    expect(vm.file).not.toBeNull()
    vm.password = 'passw0rd-pass'
    await vm.preview()
    expect(ElMessage.error).toHaveBeenCalledWith('包口令错误')
    vm.previewData = {
      organization_code: '520100',
      organization_name: '市局',
      expires_at: '2030-01-01',
    }
    await vm.confirm()
    expect(ElMessage.error).toHaveBeenCalled()
    vm.onFileRemove()
    expect(vm.file).toBeNull()
    post.mockRejectedValue({ response: { data: { detail: '字符串错误' } } })
    vm.file = new File(['x'], 'p.apkg')
    vm.password = 'passw0rd-pass'
    await vm.preview()
    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('blocks confirm when the factory admin passwords differ, then submits the new password', async () => {
    const w = mountPage()
    const vm = w.vm as any
    vm.file = new File(['x'], 'p.apkg')
    vm.password = 'passw0rd-pass'
    vm.previewData = {
      organization_code: '520100',
      organization_name: '市局',
      expires_at: '2030-01-01',
    }
    vm.factoryPassword = 'Local#Pass2026'
    vm.factoryPasswordConfirm = 'Local#Pass2027'
    await vm.confirm()
    expect(ElMessage.warning).toHaveBeenCalledWith('两次输入的超级管理员新密码不一致')
    expect(post).not.toHaveBeenCalled()
    vm.factoryPasswordConfirm = 'Local#Pass2026'
    post.mockResolvedValueOnce({ organization_code: '520100', users: [] })
    await vm.confirm()
    const form = post.mock.calls[0][1] as FormData
    expect(form.get('factory_admin_password')).toBe('Local#Pass2026')
    expect(form.get('password')).toBe('passw0rd-pass')
  })

  it('warns confirm before preview and handles no raw file', async () => {
    const w = mountPage()
    const vm = w.vm as any
    await vm.confirm()
    expect(ElMessage.warning).toHaveBeenCalled()
    vm.onFileChange({})
    expect(vm.file).toBeNull()
  })

  it('blocks confirm until the signer fingerprint is acknowledged', async () => {
    const w = mountPage()
    const vm = w.vm as any
    vm.file = new File(['x'], 'p.apkg')
    vm.password = 'passw0rd-pass'
    vm.previewData = {
      organization_code: '520100',
      organization_name: '市局',
      expires_at: '2030-01-01',
      trust_required: true,
      signer_fingerprint: 'AAAA-BBBB-CCCC-DDDD',
    }
    await vm.confirm()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先通过独立渠道核对签发机指纹并勾选确认')
    expect(post).not.toHaveBeenCalled()
  })

  it('sends confirmed_fingerprint when the signer was acknowledged', async () => {
    const w = mountPage()
    const vm = w.vm as any
    vm.file = new File(['x'], 'p.apkg')
    vm.password = 'passw0rd-pass'
    vm.previewData = {
      organization_code: '520100',
      organization_name: '市局',
      expires_at: '2030-01-01',
      signer_fingerprint: 'AAAA-BBBB-CCCC-DDDD',
    }
    vm.trustAcknowledged = true
    post.mockResolvedValueOnce({ organization_code: '520100', users: [] })
    await vm.confirm()
    const form = post.mock.calls[0][1] as FormData
    expect(form.get('confirmed_fingerprint')).toBe('AAAA-BBBB-CCCC-DDDD')
  })
})
