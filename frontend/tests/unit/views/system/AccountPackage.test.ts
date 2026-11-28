import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const { get, post, requestGet, downloadBlob, del, ElMessage } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  requestGet: vi.fn(),
  downloadBlob: vi.fn(),
  del: vi.fn(),
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

const authzCatalog = vi.hoisted(() => ({
  catalog_version: 'catalog-v1',
  modules: ['projects', 'villages'],
  pages: [
    {
      key: 'projects',
      label: '项目管理',
      section: 'business',
      section_label: '业务管理',
      kind: 'page',
      modules: ['projects'],
      can_edit: true,
      tabs: [],
    },
    {
      key: 'dashboard',
      label: '工作台',
      section: 'dashboard',
      section_label: '工作台',
      kind: 'page',
      modules: [],
      can_edit: false,
      tabs: [],
    },
    {
      key: 'system-console-org',
      label: '组织与权限',
      section: 'system',
      section_label: '系统管理',
      kind: 'console',
      modules: ['users-orgs', 'organizations'],
      can_edit: true,
      tabs: [
        { key: 'users-orgs', label: '用户与组织' },
        { key: 'organizations', label: '组织管理' },
      ],
    },
  ],
  sections: [
    {
      key: 'dashboard',
      label: '工作台',
      items: [
        {
          key: 'dashboard',
          label: '工作台',
          section: 'dashboard',
          section_label: '工作台',
          kind: 'page',
          modules: [],
          can_edit: false,
          tabs: [],
        },
      ],
    },
    {
      key: 'business',
      label: '业务管理',
      items: [
        {
          key: 'projects',
          label: '项目管理',
          section: 'business',
          section_label: '业务管理',
          kind: 'page',
          modules: ['projects'],
          can_edit: true,
          tabs: [],
        },
      ],
    },
    {
      key: 'system',
      label: '系统管理',
      items: [
        {
          key: 'system-console-org',
          label: '组织与权限',
          section: 'system',
          section_label: '系统管理',
          kind: 'console',
          modules: ['users-orgs', 'organizations'],
          can_edit: true,
          tabs: [
            { key: 'users-orgs', label: '用户与组织' },
            { key: 'organizations', label: '组织管理' },
          ],
        },
      ],
    },
  ],
}))

const canIssue = vi.hoisted(() => ({
  can_issue: true,
  enabled: true,
  signing_key_configured: true,
  is_superuser: true,
  reason: '',
  reason_code: null,
  signing_public_key: 'a'.repeat(64),
  signing_fingerprint: 'AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-0000-1111',
  signing_key_source: 'runtime',
}))

const signingKeys = vi.hoisted(() => ({
  public_key: 'a'.repeat(64),
  fingerprint: 'AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-0000-1111',
  source: 'runtime',
  ready: true,
  trusted_keys: [] as Array<{ public_key: string; fingerprint: string }>,
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
  default: { get: requestGet, del },
  get,
  post,
  del,
  downloadBlob,
  parseContentDisposition: (_h: unknown, fallback: string) => fallback,
}))
vi.mock('element-plus', async () => {
  const actual = await vi.importActual<any>('element-plus')
  return { ...actual, ElMessage }
})

import AccountPackage from '@/views/system/AccountPackage.vue'

function defaultGet(url: string) {
  if (url === '/account-packages/authorization-catalog') return Promise.resolve(authzCatalog)
  if (url === '/account-packages/can-issue') return Promise.resolve({ ...canIssue })
  if (url === '/account-packages/signing-keys') {
    return Promise.resolve({ ...signingKeys, trusted_keys: [...signingKeys.trusted_keys] })
  }
  return Promise.resolve({ items: [] })
}

function mountComp() {
  return mount(AccountPackage, { global: { plugins: [ElementPlus], stubs: { teleport: true } } })
}

async function mountAndOpen() {
  const wrapper = mountComp()
  await flushPromises()
  const vm = wrapper.vm as any
  vm.openExportDialog()
  await flushPromises()
  return { wrapper, vm }
}

function fillExport(vm: any, overrides: Record<string, unknown> = {}) {
  Object.assign(vm.exportForm, {
    organization_code: '520100',
    organization_name: '市局',
    parent_code: '520000',
    target_machine_code: 'MC-API-123',
    package_password: 'passw0rd-pass',
    valid_days: 7,
    ...overrides,
  })
  vm.exportForm.accounts[0] = {
    username: 'alice',
    full_name: 'A',
    role: 'admin',
    data_scope: 'org',
    initial_password: 'InitPass123',
    allowed_menus: ['projects'],
  }
}

describe('AccountPackage.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    get.mockImplementation(defaultGet)
  })

  it('挂载加载列表、回执、授权目录与签发状态', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/account-packages', { limit: 100 })
    expect(get).toHaveBeenCalledWith('/account-packages/receipts')
    expect(get).toHaveBeenCalledWith('/account-packages/authorization-catalog')
    expect(get).toHaveBeenCalledWith('/account-packages/can-issue')
    expect(get).toHaveBeenCalledWith('/account-packages/signing-keys')
    const vm = wrapper.vm as any
    expect(vm.packages).toEqual([])
    expect(vm.authzCatalog.catalog_version).toBe('catalog-v1')
    expect(vm.issueStatus.can_issue).toBe(true)
    expect(vm.signingKeys.fingerprint).toBe('AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-0000-1111')
  })

  it('展示本机签发密钥并支持信任/移除外部签发机', async () => {
    const trusted = {
      public_key: 'b'.repeat(64),
      fingerprint: 'BBBB-CCCC-DDDD-EEEE-FFFF-0000-1111-2222',
    }
    get.mockImplementation((url: string) => {
      if (url === '/account-packages/signing-keys') {
        return Promise.resolve({ ...signingKeys, trusted_keys: [trusted] })
      }
      return defaultGet(url)
    })
    post.mockResolvedValue({ fingerprint: 'CCCC-DDDD-EEEE-FFFF-0000-1111-2222-3333' })
    del.mockResolvedValue({ removed: true })
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as any)

    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.signingKeys.trusted_keys[0].fingerprint).toBe(trusted.fingerprint)

    vm.trustKeyPublicKey = 'c'.repeat(64)
    await vm.trustSigningKey()
    expect(post).toHaveBeenCalledWith('/account-packages/signing-keys/trusted', {
      public_key: 'c'.repeat(64),
    })

    await vm.untrustSigningKey(trusted.fingerprint)
    expect(del).toHaveBeenCalledWith(
      `/account-packages/signing-keys/trusted/${encodeURIComponent(trusted.fingerprint)}`
    )
  })

  it('取消移除信任时不发删除请求', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel' as any)
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.untrustSigningKey('BBBB-CCCC-DDDD-EEEE')
    expect(del).not.toHaveBeenCalled()
  })

  it('移除信任失败时提示错误', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as any)
    del.mockRejectedValue({ response: { data: { detail: { message: '服务不可用' } } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.untrustSigningKey('BBBB-CCCC-DDDD-EEEE')
    expect(ElMessage.error).toHaveBeenCalledWith('服务不可用')
  })

  it('复制公钥/指纹并处理浏览器拒绝复制', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.copyText('abc', '公钥')
    expect(writeText).toHaveBeenCalledWith('abc')
    expect(ElMessage.success).toHaveBeenCalledWith('公钥已复制')
    writeText.mockRejectedValueOnce(new Error('denied'))
    await vm.copyText('abc', '指纹')
    expect(ElMessage.warning).toHaveBeenCalledWith('浏览器不允许自动复制，请手动选择文本')
    writeText.mockClear()
    await vm.copyText('', '空值')
    expect(writeText).not.toHaveBeenCalled()
  })

  it('拒绝非法公钥并处理添加信任失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.trustKeyPublicKey = 'short'
    await vm.trustSigningKey()
    expect(ElMessage.warning).toHaveBeenCalledWith('请粘贴 64 位十六进制的签发机公钥')
    expect(post).not.toHaveBeenCalled()
    vm.trustKeyPublicKey = 'c'.repeat(64)
    post.mockRejectedValueOnce({ response: { data: { detail: { message: '已存在' } } } })
    await vm.trustSigningKey()
    expect(ElMessage.error).toHaveBeenCalledWith('已存在')
  })

  it('首次来自未信任签发机时必须核对指纹确认', async () => {
    post.mockImplementation((url: string) => {
      if (url === '/account-packages/preview') {
        return Promise.resolve({
          package_id: 'p1',
          organization_code: '520100',
          organization_name: '市局',
          expires_at: '2030-01-01',
          accounts: [{ username: 'alice', full_name: 'A', role: 'user', data_scope: 'org' }],
          signer_public_key: 'd'.repeat(64),
          signer_fingerprint: 'DDDD-EEEE-FFFF-0000-1111-2222-3333-4444',
          signer_trusted: false,
          trust_required: true,
        })
      }
      if (url === '/account-packages/confirm') {
        return Promise.resolve({
          organization_code: '520100',
          users: [{ user_id: 1, username: 'alice', must_change_password: true }],
        })
      }
      return Promise.resolve({})
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openImportDialog()
    vm.importFile = new File(['x'], 'p.apkg')
    vm.importPassword = 'passw0rd-pass'
    await vm.previewImport()
    await flushPromises()
    expect(vm.importPreview.trust_required).toBe(true)

    await vm.confirmImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先通过独立渠道核对签发机指纹并勾选确认')
    expect(post).not.toHaveBeenCalledWith('/account-packages/confirm', expect.anything())

    vm.importTrustAcknowledged = true
    await vm.confirmImport()
    await flushPromises()
    const form = post.mock.calls.find(
      (call) => call[0] === '/account-packages/confirm'
    )?.[1] as FormData
    expect(form.get('confirmed_fingerprint')).toBe('DDDD-EEEE-FFFF-0000-1111-2222-3333-4444')
    expect(vm.importResult.users[0].username).toBe('alice')
  })

  it('按页面树推导授权并导出，不再提交权限码', async () => {
    post.mockResolvedValue({
      package_id: 'p1',
      file_name: 'p1.apkg',
      accounts: [{ username: 'alice', one_time_password: 'otp123' }],
    })
    const { vm } = await mountAndOpen()
    fillExport(vm)
    vm.selectGrant(vm.authzCatalog.pages[0], 'edit')
    await vm.exportPackage()
    await flushPromises()
    expect(post).toHaveBeenCalledWith(
      '/account-packages/export',
      expect.objectContaining({
        grants: { projects: 'edit' },
        accounts: [
          expect.objectContaining({
            username: 'alice',
            allowed_menus: ['projects'],
          }),
        ],
      })
    )
    const payload = post.mock.calls[0][1]
    expect(payload.accounts[0]).not.toHaveProperty('allowed_permissions')
    expect(vm.exportResult.accounts[0].one_time_password).toBe('otp123')
    expect(ElMessage.success).toHaveBeenCalled()
  })

  it('未勾选授权时阻止导出', async () => {
    const { vm } = await mountAndOpen()
    fillExport(vm)
    await vm.exportPackage()
    expect(ElMessage.warning).toHaveBeenCalledWith('请至少勾选一个页面的授权级别')
    expect(post).not.toHaveBeenCalled()
  })

  it('不可签发时按钮禁用并展示原因', async () => {
    get.mockImplementation((url: string) => {
      if (url === '/account-packages/can-issue') {
        return Promise.resolve({
          ...canIssue,
          can_issue: false,
          reason: '未配置签名私钥',
          reason_code: 'AP_SIGNING_MISSING',
        })
      }
      return defaultGet(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.issueStatus.can_issue).toBe(false)
    expect(vm.issueStatus.reason).toBe('未配置签名私钥')
    expect(vm.issueStatus.reason_code).toBe('AP_SIGNING_MISSING')
  })

  it('授权目录加载失败时给出错误且不阻断列表', async () => {
    get.mockImplementation((url: string) => {
      if (url.startsWith('/account-packages/authorization')) {
        return Promise.reject({ response: { data: { detail: { message: '目录不可用' } } } })
      }
      return defaultGet(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalled()
    expect((wrapper.vm as any).authzCatalog).toBeNull()
    expect((wrapper.vm as any).packages).toEqual([])
  })

  it('导入预览展示授权摘要，确认后展示用户', async () => {
    post.mockImplementation((url: string) => {
      if (url === '/account-packages/preview') {
        return Promise.resolve({
          package_id: 'p1',
          organization_code: '520100',
          organization_name: '市局',
          expires_at: '2030-01-01',
          accounts: [{ username: 'alice', full_name: 'A', role: 'user', data_scope: 'org' }],
          authorization: {
            page_count: 2,
            edit_page_count: 1,
            view_page_count: 1,
            module_count: 2,
            digest: 'a'.repeat(64),
          },
        })
      }
      if (url === '/account-packages/confirm') {
        return Promise.resolve({
          organization_code: '520100',
          users: [{ user_id: 1, username: 'alice', must_change_password: true }],
        })
      }
      return Promise.resolve({})
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openImportDialog()
    vm.importFile = new File(['x'], 'p.apkg')
    vm.importPassword = 'passw0rd-pass'
    await vm.previewImport()
    await flushPromises()
    expect(vm.importPreview.package_id).toBe('p1')
    expect(vm.importPreview.authorization).toEqual(
      expect.objectContaining({
        page_count: 2,
        edit_page_count: 1,
        view_page_count: 1,
        module_count: 2,
      })
    )
    await vm.confirmImport()
    await flushPromises()
    expect(vm.importResult.users[0].username).toBe('alice')
  })

  it('撤销走二次确认并刷新', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({ value: '过期' } as any)
    post.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).revokePackage({ package_id: 'p1', state: 'active' })
    expect(post).toHaveBeenCalledWith('/account-packages/p1/revoke', { reason: '过期' })
  })
})

describe('AccountPackage extra', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    get.mockImplementation(defaultGet)
  })

  it('列表状态与错误映射全分支', async () => {
    get.mockImplementation((url: string) => {
      if (url === '/account-packages') {
        return Promise.resolve({
          items: [
            { package_id: 'a', state: 'active' },
            { package_id: 'b', state: 'revoked' },
            { package_id: 'c' },
          ],
        })
      }
      if (url === '/account-packages/receipts') {
        return Promise.resolve({ items: [{ package_id: 'r' }] })
      }
      if (url === '/account-packages/authorization-catalog') {
        return Promise.resolve(authzCatalog)
      }
      if (url === '/account-packages/can-issue') {
        return Promise.resolve({ ...canIssue })
      }
      return Promise.reject({ response: { data: { detail: { message: '对象错误' } } } })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stateLabel('active')).toBe('有效')
    expect(vm.stateLabel('revoked')).toBe('已撤销')
    expect(vm.stateLabel(undefined)).toBe('未知')
    vm.openImportDialog()
    vm.importFile = null
    vm.importPassword = 'p'
    await vm.previewImport()
    expect(ElMessage.warning).toHaveBeenCalled()
    await vm.confirmImport()
    expect(ElMessage.warning).toHaveBeenCalled()
    vm.importFile = new File(['x'], 'x.apkg')
    vm.importPassword = 'p'
    vm.importPreview = { package_id: 'p' }
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
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalled()
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('非数组列表、空授权与无 raw 文件分支', async () => {
    get.mockImplementation((url: string) => {
      if (url === '/account-packages/authorization-catalog') return Promise.resolve(authzCatalog)
      if (url === '/account-packages/can-issue') return Promise.resolve({ ...canIssue })
      return Promise.resolve({ items: null })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.packages).toEqual([])
    expect(vm.receipts).toEqual([])
    vm.openExportDialog()
    fillExport(vm)
    await vm.exportPackage()
    expect(ElMessage.warning).toHaveBeenCalled()
    vm.onImportFileChange({} as any)
    expect(vm.importFile).toBeNull()
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    dialogs.forEach((d: any) => d.vm.$emit('update:modelValue', false))
  })

  it('导出校验与异常分支', async () => {
    const { vm } = await mountAndOpen()
    await vm.exportPackage()
    expect(ElMessage.warning).toHaveBeenCalled()
    fillExport(vm)
    post.mockRejectedValue({ response: { data: { detail: { message: '导出失败' } } } })
    vm.selectGrant(vm.authzCatalog.pages[0], 'view')
    await vm.exportPackage()
    expect(ElMessage.error).toHaveBeenCalled()
    vm.selectGrant(vm.authzCatalog.pages[0], '')
    expect(vm.buildGrants()).toEqual({})
    vm.addAccount()
    expect(vm.exportForm.accounts).toHaveLength(2)
    expect(vm.exportForm.accounts[1].role).toBe('user')
    vm.removeAccount(1)
    expect(vm.exportForm.accounts).toHaveLength(1)
    vm.removeAccount(0)
    expect(vm.exportForm.accounts).toHaveLength(1)
    vm.closeOtpDialog()
  })

  it('下载成功/失败、撤销取消与失败、文件事件', async () => {
    requestGet.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })
    const wrapper = mountComp()
    await flushPromises()
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

  it('菜单选项与菜单加载失败分支', async () => {
    menuState.loaded = true
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).menuOptions).toEqual([
      { key: 'projects', label: '项目管理', group: '业务管理' },
      { key: 'dashboard', label: '工作台', group: '菜单' },
    ])
    w.unmount()
    menuState.loaded = false
    menuState.fetchError = false
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).menuOptions).toEqual([
      { key: 'projects', label: '项目管理', group: '业务管理' },
      { key: 'dashboard', label: '工作台', group: '菜单' },
    ])
    w2.unmount()
    menuState.loaded = false
    menuState.fetchError = true
    const w3 = mountComp()
    await flushPromises()
    w3.unmount()
    menuState.loaded = true
    menuState.fetchError = false
  })

  it('页面树把无写模块页面限制为只读', async () => {
    const { vm } = await mountAndOpen()
    const dashboard = vm.authzCatalog.pages.find((page: any) => page.key === 'dashboard')
    expect(vm.canEditPage(dashboard)).toBe(false)
    expect(vm.canEditPage(vm.authzCatalog.pages[0])).toBe(true)
    expect(vm.authzCatalog.sections.map((section: any) => section.key)).toEqual([
      'dashboard',
      'business',
      'system',
    ])
  })

  it('树节点辅助函数与凭证清单下载覆盖模板分支', async () => {
    const { vm } = await mountAndOpen()
    const page = vm.authzCatalog.pages[0]
    const group = { key: 'business', label: '业务管理', kind: 'group', children: [page] }
    expect(vm.groupChildren(group)).toEqual([page])
    expect(vm.groupChildren(page)).toEqual([])
    expect(vm.pageItem(page)).toBe(page)
    expect(vm.grantValue(page)).toBe('')
    vm.selectGrant(page, 'edit')
    expect(vm.grantValue(page)).toBe('edit')
    expect(vm.buildGrants()).toEqual({ projects: 'edit' })

    vm.exportResult = {
      package_id: 'p1',
      organization_code: '520100',
      organization_name: '市局',
      expires_at: '2030-01-01',
      accounts: [
        {
          username: 'alice',
          one_time_password: 'otp123',
          role: 'user',
          data_scope: 'org',
        },
      ],
    }
    vm.downloadCredentialSheet()
    expect(downloadBlob).toHaveBeenCalledTimes(1)
    const [blob, filename] = downloadBlob.mock.calls[0]
    expect(blob).toBeInstanceOf(Blob)
    expect(filename).toBe('account-package-p1-credentials.csv')
    vm.resetGrantSelections()
    vm.resetGrantSelections()
    vm.exportResult = {
      package_id: 'p2',
      accounts: [
        {
          username: 'bob',
          one_time_password: 'otp456',
          generated_password: false,
        },
      ],
    }
    vm.downloadCredentialSheet()
    expect(downloadBlob).toHaveBeenCalledTimes(2)
    vm.exportResult = null
    vm.downloadCredentialSheet()
    expect(downloadBlob).toHaveBeenCalledTimes(2)
  })
})
