/**
 * views/system/UpdateLogs.vue 覆盖率攻坚
 * 覆盖：加载列表/最新、添加记录、删除、格式化时间、管理员分支
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, ElMessageBox, updateLogsApi, authState } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn(), alert: vi.fn() },
  updateLogsApi: {
    listLogs: vi.fn(),
    getLatest: vi.fn(),
    createLog: vi.fn(),
    deleteLog: vi.fn(),
  },
  authState: { isAdmin: true },
}))

vi.mock('@/api/updateLogs', () => ({
  updateLogsApi,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox,
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import UpdateLogs from '@/views/system/UpdateLogs.vue'

const logData = {
  success: true,
  data: {
    items: [
      { id: '1', version: 'V1.2.0', description: '修复若干问题', updated_by: 'admin', created_at: '2024-01-01T10:00:00Z' },
      { id: '2', version: 'V1.1.0', description: '新增功能', created_at: '2023-12-01T10:00:00Z' },
    ],
    total: 2,
  },
}

const latestData = {
  success: true,
  data: { id: '1', version: 'V1.2.0', description: '修复若干问题', updated_by: 'admin', created_at: '2024-01-01T10:00:00Z' },
}

async function mountComp() {
  const w = mount(UpdateLogs, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub"><slot /></button>',
        },
        'el-skeleton': { name: 'ElSkeleton', template: '<div class="el-skeleton-stub" />' },
        'el-timeline': { name: 'ElTimeline', template: '<div class="el-timeline-stub"><slot /></div>' },
        'el-timeline-item': {
          name: 'ElTimelineItem',
          template: '<div class="el-timeline-item-stub"><slot /></div>',
        },
        'el-empty': { name: 'ElEmpty', template: '<div class="el-empty-stub"><slot /></div>' },
        'el-pagination': {
          name: 'ElPagination',
          template: '<div class="el-pagination-stub"><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-form': { name: 'ElForm', template: '<form><slot /></form>' },
        'el-form-item': { name: 'ElFormItem', template: '<div><slot /></div>' },
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
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
  authState.isAdmin = true
  updateLogsApi.listLogs.mockResolvedValue(logData)
  updateLogsApi.getLatest.mockResolvedValue(latestData)
  updateLogsApi.createLog.mockResolvedValue({})
  updateLogsApi.deleteLog.mockResolvedValue({})
  ElMessageBox.confirm.mockResolvedValue('confirm')
})

describe('UpdateLogs.vue', () => {
  it('渲染并加载日志列表/最新版本', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(updateLogsApi.listLogs).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    expect(updateLogsApi.getLatest).toHaveBeenCalled()
    expect(vm.logs.length).toBe(2)
    expect(vm.latestLog?.version).toBe('V1.2.0')
    expect(vm.isAdmin).toBe(true)
    expect(w.text()).toContain('最新版本')
  })

  it('非管理员：不显示添加/删除按钮', async () => {
    authState.isAdmin = false
    const w = await mountComp()
    expect((w.vm as any).isAdmin).toBe(false)
    expect(w.text()).not.toContain('添加更新记录')
  })

  it('管理员按钮：添加更新记录 / 删除日志', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const addBtn = w
      .findAll('button')
      .find((b) => b.text().includes('添加更新记录'))
    await addBtn!.trigger('click')
    expect(vm.showAddDialog).toBe(true)
    const delBtn = w
      .findAll('button')
      .find((b) => b.text().includes('删除'))
    await delBtn!.trigger('click')
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(updateLogsApi.deleteLog).toHaveBeenCalled()
  })

  it('最新版本无操作人 → 显示系统', async () => {
    updateLogsApi.getLatest.mockResolvedValue({
      success: true,
      data: { id: '1', version: 'V1.2.0', description: 'x', created_at: '2024-01-01T10:00:00Z' },
    })
    const w = await mountComp()
    expect(w.text()).toContain('系统')
  })

  it('loadLogs：success=false → 不更新', async () => {
    updateLogsApi.listLogs.mockResolvedValue({ success: false })
    const w = await mountComp()
    expect((w.vm as any).logs).toEqual([])
    expect((w.vm as any).total).toBe(0)
  })

  it('loadLogs：success 但无 data → 不更新', async () => {
    updateLogsApi.listLogs.mockResolvedValue({ success: true })
    const w = await mountComp()
    expect((w.vm as any).logs).toEqual([])
  })

  it('loadLogs：data 缺 items 字段 → 空数组兜底', async () => {
    updateLogsApi.listLogs.mockResolvedValue({ success: true, data: { total: 5 } })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.logs).toEqual([])
    expect(vm.total).toBe(5)
  })

  it('分页：总数大于页大小 → 渲染分页并切换', async () => {
    updateLogsApi.listLogs.mockResolvedValue({
      success: true,
      data: {
        items: [{ id: '1', version: 'V1.2.0', description: 'x', created_at: '2024-01-01T10:00:00Z' }],
        total: 25,
      },
    })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.total).toBe(25)
    const pagination = w.findComponent({ name: 'ElPagination' })
    expect(pagination.exists()).toBe(true)
    pagination.vm.$emit('update:currentPage', 2)
    await nextTick()
    expect(vm.currentPage).toBe(2)
    pagination.vm.$emit('current-change', 2)
    await nextTick()
    expect(updateLogsApi.listLogs).toHaveBeenCalledWith({ page: 2, page_size: 20 })
  })

  it('loadLogs 失败 → 错误提示', async () => {
    updateLogsApi.listLogs.mockRejectedValue(new Error('list failed'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载更新日志失败')
    expect((w.vm as any).loading).toBe(false)
  })

  it('loadLatest 失败 → 静默忽略', async () => {
    updateLogsApi.getLatest.mockRejectedValue(new Error('latest failed'))
    const w = await mountComp()
    expect((w.vm as any).latestLog).toBeNull()
  })

  it('refreshData 并行刷新', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vi.clearAllMocks()
    updateLogsApi.listLogs.mockResolvedValue(logData)
    updateLogsApi.getLatest.mockResolvedValue(latestData)
    await vm.refreshData()
    expect(updateLogsApi.listLogs).toHaveBeenCalled()
    expect(updateLogsApi.getLatest).toHaveBeenCalled()
  })

  it('submitLog：字段缺失 → 警告', async () => {
    const w = await mountComp()
    await (w.vm as any).submitLog()
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写版本号和更新内容')
    expect(updateLogsApi.createLog).not.toHaveBeenCalled()
  })

  it('submitLog：添加成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.showAddDialog = true
    vm.newLog.version = 'V1.3.0'
    vm.newLog.description = '新增模块'
    await vm.submitLog()
    expect(updateLogsApi.createLog).toHaveBeenCalledWith({
      version: 'V1.3.0',
      description: '新增模块',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('更新日志已添加')
    expect(vm.showAddDialog).toBe(false)
    expect(vm.currentPage).toBe(1)
    expect(vm.saving).toBe(false)
  })

  it('submitLog：失败 → 错误提示', async () => {
    updateLogsApi.createLog.mockRejectedValue(new Error('create failed'))
    const w = await mountComp()
    const vm = w.vm as any
    vm.newLog.version = 'V1.3.0'
    vm.newLog.description = 'x'
    await vm.submitLog()
    expect(ElMessage.error).toHaveBeenCalledWith('create failed')
  })

  it('submitLog：失败无 message → 默认文案', async () => {
    updateLogsApi.createLog.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    vm.newLog.version = 'V1.3.0'
    vm.newLog.description = 'x'
    await vm.submitLog()
    expect(ElMessage.error).toHaveBeenCalledWith('添加失败')
  })

  it('handleDelete：确认 → 删除成功并刷新', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDelete({ id: '1', version: 'V1.2.0' })
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(updateLogsApi.deleteLog).toHaveBeenCalledWith('1')
    expect(ElMessage.success).toHaveBeenCalledWith('已删除')
    expect(vm.currentPage).toBe(1)
  })

  it('handleDelete：用户取消（cancel）→ 无操作', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDelete({ id: '1', version: 'V1.2.0' })
    expect(updateLogsApi.deleteLog).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('handleDelete：失败 → 错误提示', async () => {
    updateLogsApi.deleteLog.mockRejectedValue(new Error('delete failed'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDelete({ id: '1', version: 'V1.2.0' })
    expect(ElMessage.error).toHaveBeenCalledWith('delete failed')
  })

  it('handleDelete：失败无 message → 默认文案', async () => {
    updateLogsApi.deleteLog.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDelete({ id: '1', version: 'V1.2.0' })
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('formatDate：空值 / 正常 / 异常日期', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.formatDate('')).toBe('-')
    expect(vm.formatDate('2024-01-01T10:00:00Z')).toContain('2024')
    // 2026-10-03 收敛到 @/utils format：非法值统一兜底 '-'
    // （旧实现直连 toLocaleDateString，jsdom 下会渲染出英文 'Invalid Date'）
    expect(vm.formatDate('not-a-date')).toBe('-')
  })

  it('空列表 → 空状态展示', async () => {
    updateLogsApi.listLogs.mockResolvedValue({ success: true, data: { items: [], total: 0 } })
    const w = await mountComp()
    expect((w.vm as any).logs).toEqual([])
    expect(w.find('.el-empty-stub').exists()).toBe(true)
  })

  it('添加对话框：输入 + 取消按钮 + update:modelValue', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.showAddDialog = true
    await nextTick()
    const inputs = w.findAll('.el-dialog-stub input')
    await inputs[0].setValue('V9.9.9')
    expect(vm.newLog.version).toBe('V9.9.9')
    await inputs[1].setValue('更新说明内容')
    expect(vm.newLog.description).toBe('更新说明内容')
    const cancelBtn = w
      .findAll('button')
      .find((b) => b.text().includes('取消'))
    await cancelBtn!.trigger('click')
    await nextTick()
    expect(vm.showAddDialog).toBe(false)
    vm.showAddDialog = true
    await nextTick()
    const dialog = w.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.showAddDialog).toBe(false)
  })
})
