/**
 * views/schools/Edit.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：新增/编辑模式、loadData 全分支、附件管理（加载/上传成功失败/删除/下载）、
 * getFileIcon/formatFileSize 全分支、onRegionChange、handleSubmit 全分支、
 * beforeAttachmentUpload、模板 v-model 与按钮。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, mockConfirm, getMock, postMock, putMock, delMock, pushSafeMock, routeBox, logError, validateMock, authBox } =
  vi.hoisted(() => ({
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    mockConfirm: vi.fn(),
    getMock: vi.fn(),
    postMock: vi.fn(),
    putMock: vi.fn(),
    delMock: vi.fn(),
    pushSafeMock: vi.fn(),
    routeBox: { params: {} as Record<string, any> },
    logError: vi.fn(),
    validateMock: vi.fn(),
    authBox: { token: 'token-1' },
  }))

// ③ 离开拦截（useDirtyGuard）会 import onBeforeRouteLeave：只 mock useRoute 会让 setup 直接抛错
vi.mock('vue-router', () => ({ useRoute: () => routeBox, onBeforeRouteLeave: vi.fn() }))

vi.mock('element-plus', () => ({
  ElMessage,
  // ③ 草稿恢复询问：默认按"用户取消"返回，避免测试挂起；具体用例自行改 resolve
  ElMessageBox: { confirm: mockConfirm },
}))

vi.mock('@/api/request', () => ({
  get: getMock,
  post: postMock,
  put: putMock,
  del: delMock,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
  // ③ 草稿键要用 id：页面 imports safeRouteParam，mock 必须给出同名实现
  safeRouteParam: (v: unknown) => Number(v) || v,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: () => authBox.token },
}))

vi.mock('@/data/guizhouRegion', () => ({
  DEFAULT_PROVINCE: '贵州省',
}))

import Edit from '@/views/schools/Edit.vue'

const schoolData = {
  id: 3,
  name: '第一小学',
  code: 'SCH-001',
  type: 'middle',
  province: '贵州省',
  city: '都匀市',
  district: 'X区',
  address: '地址',
  latitude: 26.1,
  longitude: 107.5,
  student_count: 500,
  teacher_count: 20,
  class_count: 10,
  support_status: 'active',
  support_unit: '单位',
  principal: '校长',
  contact_phone: '13800138000',
  email: 'a@b.com',
  description: '简介',
  remarks: '备注',
}

const att = { id: 1, file_name: '报告.pdf', file_size: 2048 }
const att2 = { id: 2, file_name: '表格.xlsx', file_size: 2 * 1048576 }

const fetchMock = vi.hoisted(() => vi.fn())

function mountComp() {
  return mount(Edit, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-form': {
          name: 'ElForm',
          template: '<div class="el-form-stub"><slot /></div>',
          methods: {
            validate(cb?: any) {
              const p = validateMock()
              if (cb) {
                p.then((v: boolean) => cb(v))
                return undefined
              }
              return p
            },
          },
        },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
        'el-input': {
          template:
            '<div class="el-input-stub" @click="$emit(\'update:modelValue\', \'V\')" />',
        },
        'el-input-number': {
          template:
            '<div class="el-input-number-stub" @click="$emit(\'update:modelValue\', 99)" />',
        },
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', \'high\')"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-upload': {
          template:
            '<div class="el-upload-stub" @click="beforeAttachmentUpload && beforeAttachmentUpload({ size: 100 })"><slot /></div>',
          props: ['beforeAttachmentUpload'],
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
        'el-popconfirm': {
          template:
            '<div class="el-popconfirm-stub" @click="$emit(\'confirm\', attA)"><slot name="reference" /></div>',
        },
        'el-empty': {
          template: '<div class="el-empty-stub">{{ description }}<slot /></div>',
          props: ['description'],
        },
        'map-picker': {
          name: 'MapPicker',
          template:
            '<div class="map-picker-stub" @click="$emit(\'update:latitude\', 30.1); $emit(\'update:longitude\', 108.2)" />',
          props: ['latitude', 'longitude'],
        },
        'guizhou-region-selector': {
          name: 'GuizhouRegionSelector',
          template:
            '<div class="region-selector-stub" @click="$emit(\'update:modelValue\', { city: \'贵阳市\', county: \'南明区\' })" />',
          props: ['modelValue', 'showTownship'],
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.params = {}
  authBox.token = 'token-1'
  getMock.mockImplementation((url: string) => {
    if (url.includes('/attachments')) return Promise.resolve({ data: { items: [att, att2] } })
    return Promise.resolve({ data: schoolData })
  })
  postMock.mockResolvedValue({})
  putMock.mockResolvedValue({})
  delMock.mockResolvedValue({})
  validateMock.mockResolvedValue(true)
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValue({ ok: true, blob: vi.fn().mockResolvedValue(new Blob(['x'])) })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('挂载与模式', () => {
  it('新增模式：不加载数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isEdit).toBe(false)
    expect(getMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('新增学校')
  })

  it('编辑模式：加载学校与附件', async () => {
    routeBox.params = { id: '3' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isEdit).toBe(true)
    expect(getMock).toHaveBeenCalledWith('/schools/3')
    expect(getMock).toHaveBeenCalledWith('/schools/3/attachments')
    expect(vm.formData.name).toBe('第一小学')
    expect(vm.formData.type).toBe('middle')
    expect(vm.formData.latitude).toBe(26.1)
    expect(vm.formData.longitude).toBe(107.5)
    expect(vm.attachments).toHaveLength(2)
    expect(vm.loading).toBe(false)
  })

  it('loadData 无 id → 返回', async () => {
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    expect(getMock).not.toHaveBeenCalled()
  })

  it('直接调用 loadData 且无 id → 提前返回', async () => {
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    getMock.mockClear()
    await vm.loadData()
    expect(getMock).not.toHaveBeenCalled()
  })

  it('loadData 响应为 falsy 原始值 → 错误提示并返回列表', async () => {
    routeBox.params = { id: '3' }
    getMock.mockResolvedValue(0)
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载学校信息失败')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('loadData 扁平格式响应', async () => {
    routeBox.params = { id: '3' }
    getMock.mockResolvedValue(schoolData)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).formData.name).toBe('第一小学')
  })

  it('loadData 字段缺失走 || 兜底', async () => {
    routeBox.params = { id: '3' }
    getMock.mockResolvedValue({ data: { id: 3 } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formData.name).toBe('')
    expect(vm.formData.code).toBe('')
    expect(vm.formData.type).toBe('primary')
    expect(vm.formData.province).toBe('贵州省')
    expect(vm.formData.city).toBe('')
    expect(vm.formData.latitude).toBeNull()
    expect(vm.formData.longitude).toBeNull()
    expect(vm.formData.student_count).toBe(0)
    expect(vm.formData.support_status).toBe('inactive')
  })

  it('loadData 失败 → logger + 错误提示', async () => {
    routeBox.params = { id: '3' }
    getMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('加载学校信息失败')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('loadAttachments 失败 → logger', async () => {
    routeBox.params = { id: '3' }
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) return Promise.reject(new Error('a'))
      return Promise.resolve({ data: schoolData })
    })
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
  })

  it('附件直返数组格式', async () => {
    routeBox.params = { id: '3' }
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) return Promise.resolve({ data: [att] })
      return Promise.resolve({ data: schoolData })
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).attachments).toHaveLength(1)
  })

  it('附件响应空对象 → 空列表', async () => {
    routeBox.params = { id: '3' }
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) return Promise.resolve({ data: undefined })
      return Promise.resolve({ data: schoolData })
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).attachments).toEqual([])
  })

  it('uploadHeaders 无 token → 空 Authorization', async () => {
    authBox.token = ''
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).uploadHeaders).toMatchObject({ 'X-CSRF-Token': 'test-csrf' })
  })
})

describe('区域与表单', () => {
  it('onRegionChange 更新城市/区县', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.onRegionChange({ city: '贵阳市', county: '南明区' })
    expect(vm.formData.city).toBe('贵阳市')
    expect(vm.formData.district).toBe('南明区')

    vm.onRegionChange({ city: '', county: '' })
    expect(vm.formData.city).toBe('')
    expect(vm.formData.district).toBe('')
  })

  it('regionValue computed 与选择器交互', async () => {
    routeBox.params = { id: '3' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.regionValue.city).toBe('都匀市')
    expect(vm.regionValue.county).toBe('X区')
    await wrapper.find('.region-selector-stub').trigger('click')
    expect(vm.formData.city).toBe('贵阳市')
    expect(vm.formData.district).toBe('南明区')
  })

  it('MapPicker 坐标 v-model 更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.map-picker-stub').trigger('click')
    expect((wrapper.vm as any).formData.latitude).toBe(30.1)
    expect((wrapper.vm as any).formData.longitude).toBe(108.2)
  })

  it('表单 v-model 更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const el of wrapper.findAll('.el-input-stub')) {
      await el.trigger('click')
    }
    for (const el of wrapper.findAll('.el-input-number-stub')) {
      await el.trigger('click')
    }
    for (const sel of wrapper.findAll('.el-select-stub')) {
      await sel.trigger('click')
    }
    await flushPromises()
    expect(vm.formData.name).toBe('V')
    expect(vm.formData.address).toBe('V')
    expect(vm.formData.student_count).toBe(99)
    expect(vm.formData.teacher_count).toBe(99)
    expect(vm.formData.class_count).toBe(99)
    expect(vm.formData.type).toBe('high')
    expect(vm.formData.support_status).toBe('high')
  })
})

describe('附件管理', () => {
  it('beforeAttachmentUpload 超限/正常', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.beforeAttachmentUpload({ size: 100 })).toBe(true)
    expect(vm.beforeAttachmentUpload({ size: 11 * 1024 * 1024 })).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('文件大小不能超过 10MB')
  })

  it('onAttachmentUploaded / onAttachmentError', async () => {
    routeBox.params = { id: '3' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    getMock.mockClear()
    vm.onAttachmentUploaded({})
    expect(ElMessage.success).toHaveBeenCalledWith('上传成功')
    expect(getMock).toHaveBeenCalledWith('/schools/3/attachments')

    vm.onAttachmentError()
    expect(ElMessage.error).toHaveBeenCalledWith('上传失败')
  })

  it('deleteAttachment 成功/失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    delMock.mockClear()
    await vm.deleteAttachment(att)
    expect(delMock).toHaveBeenCalledWith('/schools/attachments/1')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')

    delMock.mockRejectedValueOnce(new Error('net'))
    await vm.deleteAttachment(att)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('downloadAttachment 成功/失败', async () => {
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).downloadAttachment(att)
    expect(fetchMock).toHaveBeenCalled()

    fetchMock.mockRejectedValue(new Error('net'))
    await (wrapper.vm as any).downloadAttachment(att)
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败，请重试')
    clickSpy.mockRestore()
  })

  it('downloadAttachment 无 token → 空 Authorization', async () => {
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    authBox.token = ''
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).downloadAttachment(att)
    const arg = fetchMock.mock.calls[0][1]
    expect(arg.headers.Authorization).toBe('')
    clickSpy.mockRestore()
  })

  it('getFileIcon / formatFileSize 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getFileIcon('a.pdf')).toBeTruthy()
    expect(vm.getFileIcon('a.doc')).toBeTruthy()
    expect(vm.getFileIcon('a.xlsx')).toBeTruthy()
    expect(vm.getFileIcon('a.pptx')).toBeTruthy()
    expect(vm.getFileIcon('a.jpg')).toBeTruthy()
    expect(vm.getFileIcon('a.zip')).toBeTruthy()
    expect(vm.getFileIcon('a.xyz')).toBeTruthy()
    expect(vm.getFileIcon('')).toBeTruthy()
    expect(vm.formatFileSize(0)).toBe('0B')
    expect(vm.formatFileSize(500)).toBe('500B')
    expect(vm.formatFileSize(2048)).toBe('2.0KB')
    expect(vm.formatFileSize(2 * 1048576)).toBe('2.0MB')
  })

  it('上传控件触发 beforeAttachmentUpload', async () => {
    routeBox.params = { id: '3' }
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.el-upload-stub').trigger('click')
  })

  it('附件列表渲染与按钮', async () => {
    routeBox.params = { id: '3' }
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('报告.pdf')
    expect(wrapper.text()).toContain('2.0KB')
    expect(wrapper.text()).toContain('2.0MB')

    const dl = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('下载'))
    await dl!.trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalled()

    delMock.mockClear()
    await wrapper.find('.el-popconfirm-stub').trigger('click')
    await flushPromises()
    expect(delMock).toHaveBeenCalledWith('/schools/attachments/1')
    clickSpy.mockRestore()
  })

  it('无附件 → 空态', async () => {
    routeBox.params = { id: '3' }
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) return Promise.resolve({ data: { items: [] } })
      return Promise.resolve({ data: schoolData })
    })
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('暂无电子资料')
  })
})

describe('提交与导航', () => {
  it('无 formRef → 返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = null
    await vm.handleSubmit()
    expect(postMock).not.toHaveBeenCalled()
  })

  it('校验失败 → 不提交', async () => {
    const wrapper = mountComp()
    await flushPromises()
    validateMock.mockResolvedValueOnce(false)
    await (wrapper.vm as any).handleSubmit()
    expect(postMock).not.toHaveBeenCalled()
  })

  it('新增成功 → 提示 + 返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleSubmit()
    expect(postMock).toHaveBeenCalledWith('/schools', vm.formData)
    expect(ElMessage.success).toHaveBeenCalledWith('创建成功')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')
  })

  it('编辑成功 → 提示 + 返回', async () => {
    routeBox.params = { id: '3' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleSubmit()
    expect(putMock).toHaveBeenCalledWith('/schools/3', vm.formData)
    expect(ElMessage.success).toHaveBeenCalledWith('更新成功')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')
  })

  it('提交失败 → logger + 错误', async () => {
    const wrapper = mountComp()
    await flushPromises()
    postMock.mockRejectedValueOnce(new Error('net'))
    await (wrapper.vm as any).handleSubmit()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    expect((wrapper.vm as any).submitLoading).toBe(false)
  })

  it('handleBack 与保存/取消按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleBack()
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')

    pushSafeMock.mockClear()
    const save = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('保存'))
    await save!.trigger('click')
    await flushPromises()
    expect(postMock).toHaveBeenCalled()

    pushSafeMock.mockClear()
    const cancel = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('取消'))
    await cancel!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')
  })
})

// ③ 草稿自动保存与离开拦截（学校编辑页，2026-10-26）
describe('③ 草稿与离开拦截', () => {
  const DRAFT_KEY = 'form:draft:schools:edit:new'

  function seedDraft(data: Record<string, unknown>) {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ data, savedAt: Date.now() }))
  }

  beforeEach(() => {
    localStorage.clear()
  })

  it('有草稿 + 用户确认 → 回填表单并提示', async () => {
    seedDraft({ name: '草稿学校', contact_person: '草稿联系人' })
    mockConfirm.mockResolvedValue('confirm')

    const wrapper = mountComp()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.formData.name).toBe('草稿学校')
    expect(ElMessage.success).toHaveBeenCalledWith('已恢复草稿')
    wrapper.unmount()
  })

  it('有草稿 + 用户忽略 → 丢弃草稿且不污染表单', async () => {
    seedDraft({ name: '不要了' })
    mockConfirm.mockRejectedValue(new Error('cancel'))

    const wrapper = mountComp()
    await flushPromises()

    expect(localStorage.getItem(DRAFT_KEY)).toBeNull()
    expect((wrapper.vm as any).formData.name).toBe('')
    wrapper.unmount()
  })

  it('卸载时立刻落盘（防抖窗口内离开也不丢）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(wrapper.vm as any).formData.name = '离开前填的学校'
    await nextTick()

    wrapper.unmount()

    const raw = localStorage.getItem(DRAFT_KEY)
    expect(raw).not.toBeNull()
    expect(JSON.parse(raw as string).data.name).toBe('离开前填的学校')
  })

  it('创建成功后清掉草稿（不复活已提交数据）', async () => {
    seedDraft({ name: '旧草稿' })
    mockConfirm.mockResolvedValue('confirm')
    validateMock.mockImplementation((cb?: any) => (cb ? Promise.resolve(cb(true)) : Promise.resolve(true)))
    postMock.mockResolvedValue({ code: 200 })

    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleSubmit()
    await flushPromises()

    expect(localStorage.getItem(DRAFT_KEY)).toBeNull()
    wrapper.unmount()
  })
})
