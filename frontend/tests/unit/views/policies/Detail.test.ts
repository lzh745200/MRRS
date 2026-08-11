/**
 * views/policies/Detail.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载（无 id/成功/失败）、canEdit 全分支、
 * 发布/归档（确认/取消/成功/失败）、收藏切换、预览/下载、相关政策、
 * 模板分支（v-html/状态标签/按钮显隐）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  confirmMock,
  policyApiMock,
  pushSafeMock,
  routeBox,
  authState,
  downloadBlobMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  policyApiMock: {
    getPolicy: vi.fn(),
    publishPolicy: vi.fn(),
    archivePolicy: vi.fn(),
    previewPolicyFile: vi.fn(),
    downloadPolicyFile: vi.fn(),
    addPolicyFavorite: vi.fn(),
    removePolicyFavorite: vi.fn(),
    getPolicyRelated: vi.fn(),
    getCategoryLabel: vi.fn((c: any) => `类别:${c}`),
    getLevelLabel: vi.fn((l: any) => `级别:${l}`),
    getStatusLabel: vi.fn((s: any) => `状态:${s}`),
    getStatusColor: vi.fn(() => 'danger'),
  },
  pushSafeMock: vi.fn(),
  routeBox: { params: { id: '1' } as Record<string, any> },
  authState: { user: { is_superuser: true } as any },
  downloadBlobMock: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRoute: () => routeBox }))

vi.mock('element-plus', () => ({ ElMessage, ElMessageBox: { confirm: confirmMock } }))

vi.mock('@/api/policy', () => policyApiMock)

vi.mock('@/api/request', () => ({
  downloadBlob: downloadBlobMock,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/utils/roleAccess', () => ({
  ADMIN_ROLES: ['admin', 'super_admin'],
  normalizeRole: (r?: string | null) => r || '',
}))

import Detail from '@/views/policies/Detail.vue'

const policy = {
  id: 1,
  title: '乡村振兴政策',
  category: 'military',
  level: 'national',
  status: 'draft',
  effective_date: '2024-01-01',
  expiry_date: '',
  created_at: '2024-01-02',
  updated_at: '',
  content: '<p>政策内容</p>',
}

const related = [{ id: 2, title: '相关政策', category: 'local', status: 'active' }]

function mountComp() {
  return mount(Detail, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-descriptions': { template: '<div class="el-descriptions-stub"><slot /></div>' },
        'el-descriptions-item': { template: '<div class="el-desc-item-stub"><slot /></div>' },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-space': { template: '<div class="el-space-stub"><slot /></div>' },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-table': {
          template: '<div class="el-table-stub"><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return {
              rowA: {
                id: 2,
                title: '相关政策',
                category: 'military',
                status: 'active',
                category_name: '',
                status_name: '',
              },
              rowB: {
                id: 3,
                title: 'B政策',
                category: 'local',
                status: 'invalid',
                category_name: '地方政策',
                status_name: '失效',
              },
            }
          },
        },
        'el-link': {
          template: '<a class="el-link-stub" @click="$emit(\'click\')"><slot /></a>',
          emits: ['click'],
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.params = { id: '1' }
  authState.user = { is_superuser: true }
  policyApiMock.getPolicy.mockResolvedValue(policy)
  policyApiMock.getPolicyRelated.mockResolvedValue(related)
  policyApiMock.publishPolicy.mockResolvedValue({})
  policyApiMock.archivePolicy.mockResolvedValue({})
  policyApiMock.previewPolicyFile.mockResolvedValue({ url: '/preview/1' })
  policyApiMock.downloadPolicyFile.mockResolvedValue(new Blob(['x']))
  policyApiMock.addPolicyFavorite.mockResolvedValue({})
  policyApiMock.removePolicyFavorite.mockResolvedValue({})
  policyApiMock.getCategoryLabel.mockImplementation((c: any) => `类别:${c}`)
  policyApiMock.getLevelLabel.mockImplementation((l: any) => `级别:${l}`)
  policyApiMock.getStatusLabel.mockImplementation((s: any) => `状态:${s}`)
  policyApiMock.getStatusColor.mockReturnValue('danger')
  confirmMock.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与加载', () => {
  it('onMounted 加载政策与相关政策', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(policyApiMock.getPolicy).toHaveBeenCalledWith(1)
    expect(vm.policy).toEqual(policy)
    expect(vm.relatedPolicies).toHaveLength(1)
    expect(vm.loading).toBe(false)
  })

  it('无 policyId → 直接返回', async () => {
    routeBox.params = { id: 'abc' }
    const wrapper = mountComp()
    await flushPromises()
    expect(policyApiMock.getPolicy).not.toHaveBeenCalled()
  })

  it('getPolicy 失败 → 错误提示', async () => {
    policyApiMock.getPolicy.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载政策详情失败')
  })

  it('loadRelated 失败 → 空数组', async () => {
    policyApiMock.getPolicyRelated.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).relatedPolicies).toEqual([])
  })

  it('loadRelated 直返数组', async () => {
    policyApiMock.getPolicyRelated.mockResolvedValue(related)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).relatedPolicies).toHaveLength(1)
  })

  it('loadRelated 空对象 → ?? [] 兜底', async () => {
    policyApiMock.getPolicyRelated.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).relatedPolicies).toEqual([])
  })
})

describe('canEdit 权限', () => {
  it('无用户 → false', async () => {
    authState.user = null
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).canEdit).toBe(false)
  })

  it('is_superuser → true；admin 角色 → true；user 角色 → false', async () => {
    authState.user = { is_superuser: false, role: 'admin' }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).canEdit).toBe(true)

    authState.user = { is_superuser: false, role: 'user' }
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).canEdit).toBe(false)
  })
})

describe('导航', () => {
  it('goBack/goEdit/goDetail', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.goBack()
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')
    vm.goEdit()
    expect(pushSafeMock).toHaveBeenCalledWith('/policies/1/edit')
    vm.goDetail(2)
    expect(pushSafeMock).toHaveBeenCalledWith('/policies/2')
  })

  it('返回/编辑按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    pushSafeMock.mockClear()
    const back = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('返回'))
    await back!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')

    pushSafeMock.mockClear()
    const edit = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('编辑'))
    await edit!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies/1/edit')
  })

  it('相关链接 → goDetail', async () => {
    const wrapper = mountComp()
    await flushPromises()
    pushSafeMock.mockClear()
    const link = wrapper.find('.el-link-stub')
    await link.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies/2')
  })
})

describe('发布/归档', () => {
  it('handlePublish 确认后成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    policyApiMock.getPolicy.mockClear()
    await vm.handlePublish()
    expect(confirmMock).toHaveBeenCalledWith('确定发布该政策？发布后将对所有用户可见。', '确认发布')
    expect(policyApiMock.publishPolicy).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('发布成功')
    expect(policyApiMock.getPolicy).toHaveBeenCalled()
  })

  it('handlePublish 取消 → 不发布', async () => {
    const wrapper = mountComp()
    await flushPromises()
    confirmMock.mockRejectedValueOnce('cancel')
    await (wrapper.vm as any).handlePublish()
    expect(policyApiMock.publishPolicy).not.toHaveBeenCalled()
  })

  it('handlePublish 失败 → 静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    policyApiMock.publishPolicy.mockRejectedValueOnce(new Error('x'))
    await (wrapper.vm as any).handlePublish()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('handleArchive 成功与取消', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleArchive()
    expect(confirmMock).toHaveBeenCalledWith(
      '确定归档该政策？归档后将不再显示为有效状态。',
      '确认归档'
    )
    expect(policyApiMock.archivePolicy).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('归档成功')

    confirmMock.mockRejectedValueOnce('cancel')
    policyApiMock.archivePolicy.mockClear()
    await vm.handleArchive()
    expect(policyApiMock.archivePolicy).not.toHaveBeenCalled()
  })

  it('发布/归档按钮显隐', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btns = wrapper.findAll('.el-button-stub')
    expect(btns.find((b) => b.text().includes('发布'))).toBeTruthy()
    expect(btns.find((b) => b.text().includes('归档'))).toBeFalsy()

    policyApiMock.getPolicy.mockResolvedValue({ ...policy, status: 'active' })
    const w2 = mountComp()
    await flushPromises()
    const b2 = w2.findAll('.el-button-stub')
    expect(b2.find((b) => b.text().includes('归档'))).toBeTruthy()
  })
})

describe('收藏', () => {
  it('toggleFavorite 收藏/取消收藏', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.toggleFavorite()
    expect(policyApiMock.addPolicyFavorite).toHaveBeenCalledWith(1)
    expect(vm.isFavorite).toBe(true)
    expect(ElMessage.success).toHaveBeenCalledWith('已收藏')

    await vm.toggleFavorite()
    expect(policyApiMock.removePolicyFavorite).toHaveBeenCalledWith(1)
    expect(vm.isFavorite).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('已取消收藏')
  })

  it('toggleFavorite 失败 → 操作失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    policyApiMock.addPolicyFavorite.mockRejectedValueOnce(new Error('x'))
    await (wrapper.vm as any).toggleFavorite()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
  })

  it('收藏按钮切换文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('收藏'))
    await btn!.trigger('click')
    await flushPromises()
    expect(policyApiMock.addPolicyFavorite).toHaveBeenCalled()
  })
})

describe('预览与下载', () => {
  it('handlePreview 成功 → previewUrl', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePreview()
    expect(policyApiMock.previewPolicyFile).toHaveBeenCalledWith(1)
    expect(vm.previewUrl).toBe('/preview/1')
    expect(vm.previewLoading).toBe(false)
  })

  it('handlePreview 无 url → info 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    policyApiMock.previewPolicyFile.mockResolvedValueOnce({})
    await (wrapper.vm as any).handlePreview()
    expect(ElMessage.info).toHaveBeenCalledWith('暂无可预览的文件')
  })

  it('handlePreview 失败 → warning', async () => {
    const wrapper = mountComp()
    await flushPromises()
    policyApiMock.previewPolicyFile.mockRejectedValueOnce(new Error('x'))
    await (wrapper.vm as any).handlePreview()
    expect(ElMessage.warning).toHaveBeenCalledWith('该政策暂无附件')
  })

  it('handleDownload 成功 → downloadBlob', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleDownload()
    expect(policyApiMock.downloadPolicyFile).toHaveBeenCalledWith(1)
    expect(downloadBlobMock).toHaveBeenCalledWith(expect.any(Blob), '乡村振兴政策.pdf')
  })

  it('handleDownload 无标题 → 兜底文件名', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(wrapper.vm as any).policy = { title: '' }
    await (wrapper.vm as any).handleDownload()
    expect(downloadBlobMock).toHaveBeenCalledWith(expect.any(Blob), '政策文件.pdf')
  })

  it('handleDownload 失败 → warning', async () => {
    const wrapper = mountComp()
    await flushPromises()
    policyApiMock.downloadPolicyFile.mockRejectedValueOnce(new Error('x'))
    await (wrapper.vm as any).handleDownload()
    expect(ElMessage.warning).toHaveBeenCalledWith('该政策暂无附件')
  })

  it('预览/下载按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btns = wrapper.findAll('.el-button-stub')
    const preview = btns.find((b) => b.text().includes('预览文件'))
    await preview!.trigger('click')
    await flushPromises()
    expect(policyApiMock.previewPolicyFile).toHaveBeenCalled()

    const download = btns.find((b) => b.text().includes('下载文件'))
    await download!.trigger('click')
    await flushPromises()
    expect(policyApiMock.downloadPolicyFile).toHaveBeenCalled()
  })
})

describe('模板渲染', () => {
  it('v-html 渲染政策内容', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.find('.policy-content').exists()).toBe(true)
    expect(wrapper.find('.policy-content').html()).toContain('政策内容')
  })

  it('无内容时不渲染内容卡片', async () => {
    policyApiMock.getPolicy.mockResolvedValue({ ...policy, content: '' })
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.find('.policy-content').exists()).toBe(false)
  })

  it('标签字典透传', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('类别:military')
    expect(wrapper.text()).toContain('级别:national')
    expect(wrapper.text()).toContain('状态:draft')
  })

  it('详情字段缺失 → 占位符', async () => {
    policyApiMock.getPolicy.mockResolvedValue({
      ...policy,
      effective_date: '',
      expiry_date: '',
      created_at: '',
      updated_at: '',
    })
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('-')
  })
})

describe('policies/Detail.vue 内容净化兜底分支', () => {
  it('政策内容为空 → 净化结果为空白（空内容兜底）', async () => {
    policyApiMock.getPolicy.mockResolvedValue({ ...policy, content: '' })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.sanitizedPolicyContent).toBe('')
  })
})
