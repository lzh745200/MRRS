import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'


const { get, post, requestGet, downloadBlob, ElMessage } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  requestGet: vi.fn(),
  downloadBlob: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const menuState = vi.hoisted(() => ({
  loaded: true,
  fetchError: false,
  flatEntries: [
    { key: 'projects', label: '项目管理', sectionLabel: '业务管理' },
    { key: 'dashboard', label: '工作台' },
  ],
}))

vi.mock('@/stores/menu', () => ({
  useMenuStore: () => ({
    get loaded() {
      return menuState.loaded
    },
    flatEntries: menuState.flatEntries,
    fetchMenus: vi.fn(async () => {
      if (menuState.fetchError) throw new Error('menu fail')
    }),
  }),
}))

vi.mock('@/api/request', () => ({
  default: { get: requestGet },
  get,
  post,
  downloadBlob,
  parseContentDisposition: (_h: unknown, fallback: string) => fallback,
}))
vi.mock('element-plus', async () => {
  const actual = await vi.importActual<any>('element-plus')
  return { ...actual, ElMessage }
})

import AccountPackage from '@/views/system/AccountPackage.vue'

function mountComp() {
  return mount(AccountPackage, { global: { plugins: [ElementPlus], stubs: { teleport: true } } })
}

describe('AccountPackage.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    get.mockImplementation((url: string) =>
      Promise.resolve(url.endsWith('/receipts') ? { items: [] } : { items: [] })
    )
  })

  it('挂载加载列表和回执', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/account-packages', { limit: 100 })
    expect(get).toHaveBeenCalledWith('/account-packages/receipts')
    expect((wrapper.vm as any).packages).toEqual([])
  })

  it('导出后展示一次性口令并刷新列表', async () => {
    post.mockResolvedValue({ package_id: 'p1', file_name: 'p1.apkg', accounts: [{ username: 'alice', one_time_password: 'otp123' }] })
    const wrapper = mountComp(); await flushPromises()
    const vm = wrapper.vm as any
    vm.openExportDialog()
    Object.assign(vm.exportForm, {
      organization_code: '520100', organization_name: '市局', parent_code: '520000',
      target_machine_code: 'MC-API-123', package_password: 'passw0rd-pass', valid_days: 7,
      grantsText: '{"projects":"edit"}',
    })
    vm.exportForm.accounts[0] = { username: 'alice', full_name: 'A', role: 'admin', data_scope: 'org' }
    await vm.exportPackage(); await flushPromises()
    expect(post).toHaveBeenCalledWith('/account-packages/export', expect.objectContaining({ accounts: expect.any(Array) }))
    expect(vm.exportResult.accounts[0].one_time_password).toBe('otp123')
    expect(ElMessage.success).toHaveBeenCalled()
  })

  it('导入预览后确认', async () => {
    post.mockResolvedValueOnce({ package_id: 'p1', organization_code: '520100', organization_name: '市局', expires_at: '2030-01-01' })
      .mockResolvedValueOnce({ organization_code: '520100', users: [{ user_id: 1, username: 'alice', must_change_password: true }] })
    const wrapper = mountComp(); await flushPromises()
    const vm = wrapper.vm as any
    vm.importFile = new File(['x'], 'p.apkg')
    vm.importPassword = 'passw0rd-pass'
    await vm.previewImport(); await flushPromises()
    expect(vm.importPreview.package_id).toBe('p1')
    await vm.confirmImport(); await flushPromises()
    expect(vm.importResult.users[0].username).toBe('alice')
  })

  it('撤销走二次确认并刷新', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({ value: '过期' } as any)
    post.mockResolvedValue({})
    const wrapper = mountComp(); await flushPromises()
    await (wrapper.vm as any).revokePackage({ package_id: 'p1', state: 'active' })
    expect(post).toHaveBeenCalledWith('/account-packages/p1/revoke', { reason: '过期' })
  })
})

describe('AccountPackage extra', () => {
  it('列表状态与错误映射全分支', async () => {
    get.mockImplementation((url: string) => {
      if (url === '/account-packages') {
        return Promise.resolve({ items: [
          { package_id: 'a', state: 'active' },
          { package_id: 'b', state: 'revoked' },
          { package_id: 'c' },
        ] })
      }
      if (url === '/account-packages/receipts') {
        return Promise.resolve({ items: [{ package_id: 'r' }] })
      }
      return Promise.reject({ response: { data: { detail: { message: '对象错误' } } } })
    })
    const wrapper = mountComp(); await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stateLabel('active')).toBe('有效')
    expect(vm.stateLabel('revoked')).toBe('已撤销')
    expect(vm.stateLabel(undefined)).toBe('未知')
    vm.openImportDialog()
    vm.importFile = null; vm.importPassword = 'p'
    await vm.previewImport()
    expect(ElMessage.warning).toHaveBeenCalled()
    await vm.confirmImport()
    expect(ElMessage.warning).toHaveBeenCalled()
    vm.importFile = new File(['x'], 'x.apkg'); vm.importPassword = 'p'; vm.importPreview = { package_id: 'p' }
    post.mockRejectedValue({ response: { data: { detail: { message: '预览对象错误' } } } })
    await vm.previewImport()
    expect(ElMessage.error).toHaveBeenCalled()
    post.mockRejectedValue({ response: { data: { detail: '字符串错误' } } })
    vm.importPreview = { package_id: 'p' } as any
    await vm.confirmImport()
    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('列表/回执加载异常进入错误提示', async () => {
    get.mockRejectedValue({ response: { data: { detail: { message: '网络错误' } } } })
    const wrapper = mountComp(); await flushPromises()
    expect(ElMessage.error).toHaveBeenCalled()
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('非数组列表、空授权与无 raw 文件分支', async () => {
    get.mockImplementation((url: string) => Promise.resolve({ items: null }))
    const wrapper = mountComp(); await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.packages).toEqual([])
    expect(vm.receipts).toEqual([])
    Object.assign(vm.exportForm, {
      organization_code: '520100', target_machine_code: 'MC-API-123', package_password: 'passw0rd-pass',
      accounts: [{ username: 'a', full_name: 'A', role: 'admin', data_scope: 'org' }], grantsText: '   ',
    })
    post.mockResolvedValue({ package_id: 'p', file_name: 'p.apkg', accounts: [] })
    await vm.exportPackage()
    expect(post).toHaveBeenCalledWith('/account-packages/export', expect.objectContaining({ grants: {} }))
    vm.onImportFileChange({} as any)
    expect(vm.importFile).toBeNull()
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    dialogs.forEach((d: any) => d.vm.$emit('update:modelValue', false))
  })

  it('导出校验、授权 JSON 与异常分支', async () => {
    const wrapper = mountComp(); await flushPromises()
    const vm = wrapper.vm as any
    vm.openExportDialog()
    await vm.exportPackage()
    expect(ElMessage.warning).toHaveBeenCalled()
    Object.assign(vm.exportForm, {
      organization_code: '520100', target_machine_code: 'MC-API-123', package_password: 'passw0rd-pass',
      accounts: [{ username: 'a', full_name: 'A', role: 'admin', data_scope: 'org' }],
      grantsText: '[1]',
    })
    await vm.exportPackage()
    expect(ElMessage.error).toHaveBeenCalled()
    vm.exportForm.grantsText = '{"x":"edit"}'
    post.mockRejectedValue({ response: { data: { detail: { message: '导出失败' } } } })
    await vm.exportPackage()
    expect(ElMessage.error).toHaveBeenCalled()
    vm.addAccount(); expect(vm.exportForm.accounts).toHaveLength(2)
    vm.removeAccount(1); expect(vm.exportForm.accounts).toHaveLength(1)
    vm.removeAccount(0); expect(vm.exportForm.accounts).toHaveLength(1)
    vm.closeOtpDialog()
  })

  it('下载成功/失败、撤销取消与失败、文件事件', async () => {
    requestGet.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })
    const wrapper = mountComp(); await flushPromises()
    const vm = wrapper.vm as any
    await vm.downloadPackage({ package_id: 'p1' })
    expect(downloadBlob).toHaveBeenCalled()
    requestGet.mockRejectedValueOnce({ response: { data: { detail: { message: '下载失败' } } } })
    await vm.downloadPackage({ package_id: 'p1' })
    expect(ElMessage.error).toHaveBeenCalled()
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'prompt').mockRejectedValueOnce('cancel')
    await vm.revokePackage({ package_id: 'p1' })
    vi.spyOn(ElMessageBox, 'prompt').mockResolvedValueOnce({ value: '' } as any)
    post.mockRejectedValueOnce({ response: { data: { detail: '撤销失败' } } })
    await vm.revokePackage({ package_id: 'p1' })
    const raw = new File(['x'], 'x.apkg')
    vm.onImportFileChange({ raw } as any)
    expect(vm.importFile).toBe(raw)
    vm.onImportFileRemove()
    expect(vm.importFile).toBeNull()
    vm.openImportDialog()
    expect(vm.importPassword).toBe('')
  })


})

describe('AccountPackage offline handoff', () => {
  it('passes visual authorization lists and downloads CSV', async () => {
    post.mockResolvedValue({
      package_id: 'pkg-1', file_name: 'pkg.apkg', organization_code: '520100',
      organization_name: '市局', expires_at: '2030-01-01',
      accounts: [{ username: 'a', one_time_password: 'InitPass123', generated_password: false }],
    })
    get.mockResolvedValue({ items: [] })
    const wrapper = mountComp(); await flushPromises()
    const vm = wrapper.vm as any
    vm.openExportDialog()
    Object.assign(vm.exportForm, {
      organization_code: '520100', organization_name: '市局', target_machine_code: 'MC-API-123',
      package_password: 'passw0rd-pass', grantsText: '',
      accounts: [{
        username: 'a', full_name: 'A', role: 'user', data_scope: 'self',
        initial_password: 'InitPass123', allowed_menus: ['projects', 'funds'],
        allowed_permissions: ['project:view', 'fund:view'],
      }],
    })
    await vm.exportPackage()
    expect(post).toHaveBeenCalledWith('/account-packages/export', expect.objectContaining({
      accounts: [expect.objectContaining({
        allowed_menus: ['projects', 'funds'],
        allowed_permissions: ['project:view', 'fund:view'],
        initial_password: 'InitPass123',
      })],
    }))
    vm.downloadCredentialSheet()
    expect(downloadBlob).toHaveBeenCalled()
    vm.exportResult = { package_id: 'p2', target_org_code: '520100', accounts: [{ username: 'b', one_time_password: 'x', generated_password: true }] }
    vm.downloadCredentialSheet()
    vm.exportResult = { package_id: 'p3', accounts: [{ username: 'c', one_time_password: 'y' }] }
    vm.downloadCredentialSheet()
    vm.exportResult = null
    vm.downloadCredentialSheet()
  })



  it('菜单选项与菜单加载失败分支', async () => {
    menuState.loaded = true
    const w = mountComp(); await flushPromises()
    expect((w.vm as any).menuOptions).toEqual([
      { key: 'projects', label: '项目管理', group: '业务管理' },
      { key: 'dashboard', label: '工作台', group: '菜单' },
    ])
    w.unmount()
    menuState.loaded = false
    menuState.fetchError = false
    const w2 = mountComp(); await flushPromises()
    expect((w2.vm as any).menuOptions).toEqual([
      { key: 'projects', label: '项目管理', group: '业务管理' },
      { key: 'dashboard', label: '工作台', group: '菜单' },
    ])
    w2.unmount()
    menuState.loaded = false
    menuState.fetchError = true
    const w3 = mountComp(); await flushPromises()
    w3.unmount()
    menuState.loaded = true
    menuState.fetchError = false
  })

  it('权限选项数组与非数组分支', async () => {
    get.mockImplementation((url: string) => {
      if (url === '/users/form-options') {
        return Promise.resolve({ permissions: [{ code: 'data:view', name: '查看', category: '操作' }] })
      }
      return Promise.resolve({ items: [] })
    })
    const w = mountComp(); await flushPromises()
    expect((w.vm as any).permissionOptions).toHaveLength(1)
    w.unmount()
    get.mockResolvedValue({ items: [] })
    const w2 = mountComp(); await flushPromises()
    expect((w2.vm as any).permissionOptions).toEqual([])
    w2.unmount()
  })
})
