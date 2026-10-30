/**
 * views/system/Feedback.vue 覆盖率攻坚
 * 覆盖：列表加载、筛选、重置、详情对话框
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, mockApiRequest, dsMock } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockApiRequest: vi.fn(),
  dsMock: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  apiRequest: mockApiRequest,
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: dsMock }),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn() },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import Feedback from '@/views/system/Feedback.vue'

/** `/feedback` 的真实响应：`ok_list()` 信封，数组 payload 另被拦截器展开到 items/total */
const listData = {
  code: 200,
  success: true,
  message: '成功',
  data: {
    items: [
      { id: 1, type: 'bug', content: '页面报错', username: 'admin', contact: 'a@b.c', created_at: '2024-01-01' },
      { id: 2, type: 'suggestion', content: '加个按钮', username: '', contact: '', created_at: '2024-01-02' },
      { id: 3, type: 'other', content: '其他反馈', username: 'op', contact: '13800000000', created_at: '2024-01-03' },
      { id: 4, type: 'unknown', content: '未知类型' },
    ],
    total: 4,
  },
  items: [
    { id: 1, type: 'bug', content: '页面报错', username: 'admin', contact: 'a@b.c', created_at: '2024-01-01' },
    { id: 2, type: 'suggestion', content: '加个按钮', username: '', contact: '', created_at: '2024-01-02' },
    { id: 3, type: 'other', content: '其他反馈', username: 'op', contact: '13800000000', created_at: '2024-01-03' },
    { id: 4, type: 'unknown', content: '未知类型' },
  ],
  total: 4,
}

async function mountComp() {
  const w = mount(Feedback, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-form': { name: 'ElForm', template: '<form><slot /></form>' },
        'el-form-item': { name: 'ElFormItem', template: '<div><slot /></div>' },
        'el-select': {
          name: 'ElSelect',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<select class="el-select-stub" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
        },
        'el-option': { name: 'ElOption', props: ['value'], template: '<option :value="value"><slot /></option>' },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub"><slot /></button>',
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-table': { name: 'ElTable', template: '<table class="el-table-stub"><slot /></table>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return {
              rowA: { type: 'bug', content: '页面报错', username: 'admin', contact: 'a@b.c', created_at: '2024-01-01' },
              rowB: { type: 'unknown', content: '未知', username: '', contact: '', created_at: '2024-01-02' },
            }
          },
        },
        'el-pagination': {
          name: 'ElPagination',
          template: '<div class="el-pagination-stub"><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-descriptions': { name: 'ElDescriptions', template: '<dl><slot /></dl>' },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          template: '<div class="el-desc-item-stub"><slot /></div>',
        },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  mockApiRequest.mockResolvedValue(listData)
  dsMock.mockImplementation((v: unknown) => v as string)
})

describe('Feedback.vue', () => {
  it('渲染并加载反馈列表', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ url: '/feedback', params: expect.objectContaining({ page: 1, page_size: 20 }) })
    )
    expect(vm.tableData.length).toBe(4)
    expect(vm.pagination.total).toBe(4)
  })

  it('列表加载失败 → 清空并提示', async () => {
    mockApiRequest.mockRejectedValue(new Error('load failed'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载反馈列表失败')
    expect((w.vm as any).tableData).toEqual([])
    expect((w.vm as any).pagination.total).toBe(0)
    expect((w.vm as any).loading).toBe(false)
  })

  it('响应无 data → 不更新', async () => {
    mockApiRequest.mockResolvedValue({ data: null })
    const w = await mountComp()
    expect((w.vm as any).tableData).toEqual([])
    expect((w.vm as any).pagination.total).toBe(0)
  })

  it('响应 data 缺字段 → 空兜底', async () => {
    mockApiRequest.mockResolvedValue({ data: { data: {} } })
    const w = await mountComp()
    expect((w.vm as any).tableData).toEqual([])
    expect((w.vm as any).pagination.total).toBe(0)
  })

  it('handleReset：重置类型并重新加载', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.searchForm.type = 'bug'
    await vm.handleReset()
    expect(vm.searchForm.type).toBeUndefined()
    expect(mockApiRequest).toHaveBeenCalled()
  })

  it('筛选类型 select + 查询按钮', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const select = w.find('.el-select-stub')
    await select.setValue('bug')
    expect(vm.searchForm.type).toBe('bug')
    vi.clearAllMocks()
    mockApiRequest.mockResolvedValue(listData)
    const searchBtn = w
      .findAll('button')
      .find((b) => b.text().includes('查询'))
    await searchBtn!.trigger('click')
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ params: expect.objectContaining({ type: 'bug' }) })
    )
  })

  it('分页 current-change 重新加载', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const pagination = w.findComponent({ name: 'ElPagination' })
    pagination.vm.$emit('update:currentPage', 2)
    await nextTick()
    expect(vm.pagination.page).toBe(2)
    pagination.vm.$emit('current-change', 2)
    await nextTick()
    expect(mockApiRequest).toHaveBeenCalled()
    pagination.vm.$emit('update:pageSize', 50)
    await nextTick()
    expect(vm.pagination.pageSize).toBe(50)
  })

  it('类型标签映射：未知类型回退', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.typeNameMap['unknown']).toBeUndefined()
    expect(vm.typeTagMap['unknown']).toBeUndefined()
    expect(w.text()).toContain('Bug反馈')
    expect(w.text()).toContain('unknown')
    expect(w.text()).toContain('匿名')
  })

  it('详情对话框：打开与关闭', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.currentItem = { type: 'bug', content: '内容', username: 'u', contact: 'x@y.z', created_at: '2024-01-01' }
    vm.detailVisible = true
    await nextTick()
    expect(w.find('.el-dialog-stub').exists()).toBe(true)
    const dialog = w.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.detailVisible).toBe(false)
  })
})
