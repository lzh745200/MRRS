/**
 * views/system/DataTier.vue 覆盖率攻坚
 * 覆盖：统计/归档加载、归档/恢复/查询/清理全分支、工具函数
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, ElMessageBox, dataTierApi } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn(), alert: vi.fn() },
  dataTierApi: {
    getStats: vi.fn(),
    listArchives: vi.fn(),
    archiveModel: vi.fn(),
    restore: vi.fn(),
    getTierForRecord: vi.fn(),
    cleanup: vi.fn(),
  },
}))

vi.mock('@/api/dataTier', () => ({
  dataTierApi,
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox,
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import DataTier from '@/views/system/DataTier.vue'

const statsData = {
  hot_count: 100,
  hot_size_mb: 10.5,
  warm_count: 200,
  warm_size_mb: 20.5,
  cold_count: 300,
  cold_size_mb: 2048,
}

const archivesData = {
  cold_archives: [{ name: 'WorkLog_2024.json', size_mb: 5.5, modified: '2024-01-01' }],
  warm_archives: [{ name: 'Project_2024.json', size_mb: 1.5, modified: '2024-02-01' }],
}

async function mountComp() {
  const w = mount(DataTier, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-statistic': {
          name: 'ElStatistic',
          template: '<div class="el-statistic-stub"><slot /></div>',
          props: ['title', 'value'],
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub"><slot /></button>',
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
        'el-input-number': {
          name: 'ElInputNumber',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input class="el-input-number-stub" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
        },
        'el-tabs': { name: 'ElTabs', template: '<div class="el-tabs-stub"><slot /></div>' },
        'el-tab-pane': { name: 'ElTabPane', template: '<div class="el-tab-pane-stub"><slot /></div>' },
        'el-table': { name: 'ElTable', template: '<table class="el-table-stub"><slot /></table>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="row" /></div>',
          data() {
            return { row: { name: 'WorkLog_2024.json', size_mb: 5.5, modified: '2024-01-01' } }
          },
        },
        'el-date-picker': {
          name: 'ElDatePicker',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<div class="el-date-stub" @click="$emit(\'update:modelValue\', \'2024-01-01\')"><slot /></div>',
        },
        'el-alert': {
          name: 'ElAlert',
          template: '<div class="el-alert-stub"><slot /><slot name="title" /></div>',
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
  dataTierApi.getStats.mockResolvedValue(statsData)
  dataTierApi.listArchives.mockResolvedValue(archivesData)
  dataTierApi.archiveModel.mockResolvedValue({ message: '归档完成', archived_count: 100, model: 'WorkLog' })
  dataTierApi.restore.mockResolvedValue({ message: '恢复完成', restored_count: 100 })
  dataTierApi.getTierForRecord.mockResolvedValue({ record_date: '2024-01-01', tier: 'hot', age_days: 5 })
  dataTierApi.cleanup.mockResolvedValue({ message: '清理完成', deleted_count: 10, max_age_days: 365 })
  ElMessageBox.confirm.mockResolvedValue('confirm')
})

describe('DataTier.vue', () => {
  it('渲染并加载统计/归档', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(dataTierApi.getStats).toHaveBeenCalled()
    expect(dataTierApi.listArchives).toHaveBeenCalled()
    expect(vm.stats.hot_count).toBe(100)
    expect(vm.coldArchives.length).toBe(1)
    expect(vm.warmArchives.length).toBe(1)
    expect(vm.totalCount).toBe(600)
    expect(vm.countPercent('hot')).toBe(17)
    expect(vm.sizePercent('warm')).toBe(1)
  })

  it('loadStats 失败 → 错误提示', async () => {
    dataTierApi.getStats.mockRejectedValue(new Error('stats failed'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载存储统计失败')
  })

  it('loadArchives：返回非 ArchiveList 结构 → 空列表', async () => {
    dataTierApi.listArchives.mockResolvedValue({ other: 1 })
    const w = await mountComp()
    expect((w.vm as any).coldArchives).toEqual([])
    expect((w.vm as any).warmArchives).toEqual([])
  })

  it('loadArchives 失败 → 错误提示', async () => {
    dataTierApi.listArchives.mockRejectedValue(new Error('archives failed'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载归档列表失败')
  })

  it('refreshAll 成功提示', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vi.clearAllMocks()
    dataTierApi.getStats.mockResolvedValue(statsData)
    dataTierApi.listArchives.mockResolvedValue(archivesData)
    await vm.refreshAll()
    expect(ElMessage.success).toHaveBeenCalledWith('刷新完成')
    expect(vm.loading).toBe(false)
  })

  it('handleArchive：无模型名 → 警告', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleArchive()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入数据模型名称')
    expect(dataTierApi.archiveModel).not.toHaveBeenCalled()
  })

  it('handleArchive：归档成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.archiveForm.modelName = 'WorkLog'
    await vm.handleArchive()
    expect(dataTierApi.archiveModel).toHaveBeenCalledWith('WorkLog', 365, 1000)
    expect(ElMessage.success).toHaveBeenCalledWith('归档完成')
    expect(vm.archiveResult?.model).toBe('WorkLog')
    expect(vm.archiving).toBe(false)
  })

  it('handleArchive：失败 → 错误提示', async () => {
    dataTierApi.archiveModel.mockRejectedValue(new Error('archive failed'))
    const w = await mountComp()
    const vm = w.vm as any
    vm.archiveForm.modelName = 'WorkLog'
    await vm.handleArchive()
    expect(ElMessage.error).toHaveBeenCalledWith('归档失败')
  })

  it('handleRestore：确认 → 恢复成功并刷新', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleRestore({ name: 'WorkLog_2024.json', size_mb: 1, modified: 'x' })
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(dataTierApi.restore).toHaveBeenCalledWith('WorkLog_2024.json', 'WorkLog')
    expect(ElMessage.success).toHaveBeenCalledWith('恢复完成')
  })

  it('handleRestore：用户取消 → 返回', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleRestore({ name: 'WorkLog_2024.json' })
    expect(dataTierApi.restore).not.toHaveBeenCalled()
  })

  it('handleRestore：失败 → 错误提示', async () => {
    dataTierApi.restore.mockRejectedValue(new Error('restore failed'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleRestore({ name: 'WorkLog_2024.json' })
    expect(ElMessage.error).toHaveBeenCalledWith('恢复失败')
  })

  it('handleArchiveTabChange 无副作用', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.handleArchiveTabChange()
    expect(vm.archiveTab).toBe('cold')
  })

  it('归档消息兜底：无 message → 默认文案', async () => {
    dataTierApi.archiveModel.mockResolvedValue({ archived_count: 5 })
    const w = await mountComp()
    const vm = w.vm as any
    vm.archiveForm.modelName = 'WorkLog'
    await vm.handleArchive()
    expect(ElMessage.success).toHaveBeenCalledWith('归档完成')
  })

  it('恢复消息兜底 + 文件名无下划线', async () => {
    dataTierApi.restore.mockResolvedValue({ restored_count: 1 })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleRestore({ name: '_2024.json' })
    expect(dataTierApi.restore).toHaveBeenCalledWith('_2024.json', '')
    expect(ElMessage.success).toHaveBeenCalledWith('恢复完成')
  })

  it('清理消息兜底：无 message → 默认文案', async () => {
    dataTierApi.cleanup.mockResolvedValue({ deleted_count: 3 })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleCleanup()
    expect(ElMessage.success).toHaveBeenCalledWith('清理完成')
  })

  it('loadStats：data 为空 → 空对象', async () => {
    dataTierApi.getStats.mockResolvedValue(null)
    const w = await mountComp()
    expect((w.vm as any).stats.hot_count).toBe(0)
    expect((w.vm as any).stats.cold_size_mb).toBe(0)
  })

  it('loadArchives：缺少 cold/warm 字段 → 空数组兜底', async () => {
    dataTierApi.listArchives.mockResolvedValue({ cold_archives: null, warm_archives: null })
    const w = await mountComp()
    expect((w.vm as any).coldArchives).toEqual([])
    expect((w.vm as any).warmArchives).toEqual([])
  })

  it('统计字段缺失 → 0 兜底', async () => {
    dataTierApi.getStats.mockResolvedValue({ hot_count: 10, hot_size_mb: 5 })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.totalCount).toBe(10)
    expect(vm.totalSize).toBe(5)
    expect(vm.countPercent('warm')).toBe(0)
    expect(vm.sizePercent('warm')).toBe(0)
  })

  it('tab 切换（@tab-change）与恢复按钮点击', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const tabs = w.findComponent({ name: 'ElTabs' })
    tabs.vm.$emit('update:modelValue', 'warm')
    await nextTick()
    expect(vm.archiveTab).toBe('warm')
    const restoreBtns = w.findAll('button').filter((b) => b.text().includes('恢复'))
    for (const b of restoreBtns) {
      await b.trigger('click')
    }
    expect(dataTierApi.restore).toHaveBeenCalled()
  })

  it('handleLookup：无日期 → 警告', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleLookup()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择日期')
    expect(dataTierApi.getTierForRecord).not.toHaveBeenCalled()
  })

  it('handleLookup：查询成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.lookupDate = '2024-01-01'
    await vm.handleLookup()
    expect(dataTierApi.getTierForRecord).toHaveBeenCalledWith('2024-01-01')
    expect(vm.tierInfo?.tier).toBe('hot')
    expect(vm.lookingUp).toBe(false)
  })

  it('handleLookup：查询失败 → 错误提示', async () => {
    dataTierApi.getTierForRecord.mockRejectedValue(new Error('lookup failed'))
    const w = await mountComp()
    const vm = w.vm as any
    vm.lookupDate = '2024-01-01'
    await vm.handleLookup()
    expect(ElMessage.error).toHaveBeenCalledWith('分级查询失败')
    expect(vm.lookingUp).toBe(false)
  })

  it('handleCleanup：确认 → 清理成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleCleanup()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(dataTierApi.cleanup).toHaveBeenCalledWith(365)
    expect(ElMessage.success).toHaveBeenCalledWith('清理完成')
    expect(vm.cleanupResult?.deleted_count).toBe(10)
    expect(vm.cleaningUp).toBe(false)
  })

  it('handleCleanup：用户取消 → 返回', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleCleanup()
    expect(dataTierApi.cleanup).not.toHaveBeenCalled()
  })

  it('handleCleanup：失败 → 错误提示', async () => {
    dataTierApi.cleanup.mockRejectedValue(new Error('cleanup failed'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleCleanup()
    expect(ElMessage.error).toHaveBeenCalledWith('清理失败')
  })

  it('工具函数：formatSize / tierLabel / 百分比归零', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.formatSize(undefined)).toBe('-')
    expect(vm.formatSize(null)).toBe('-')
    expect(vm.formatSize(2048)).toBe('2.00 GB')
    expect(vm.formatSize(500)).toBe('500.00 MB')
    expect(vm.tierLabel('hot')).toBe('热数据')
    expect(vm.tierLabel('warm')).toBe('温数据')
    expect(vm.tierLabel('cold')).toBe('冷数据')
    expect(vm.tierLabel('unknown')).toBe('unknown')
    // 空统计 → 百分比 0
    vm.stats = {}
    await nextTick()
    expect(vm.countPercent('hot')).toBe(0)
    expect(vm.sizePercent('hot')).toBe(0)
    expect(vm.totalCount).toBe(0)
  })

  it('查询日期选择器 update:modelValue', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await w.find('.el-date-stub').trigger('click')
    expect(vm.lookupDate).toBe('2024-01-01')
  })

  it('归档表单输入（模型名）', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const inputs = w.findAll('input')
    await inputs[0].setValue('ProjectLog')
    expect(vm.archiveForm.modelName).toBe('ProjectLog')
  })

  it('清理最大天数输入', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const numInputs = w.findAll('.el-input-number-stub')
    // 顺序：beforeDays / batchSize / cleanupMaxAge
    await numInputs[0].setValue(200)
    expect(vm.archiveForm.beforeDays).toBe(200)
    await numInputs[1].setValue(5000)
    expect(vm.archiveForm.batchSize).toBe(5000)
    await numInputs[2].setValue(180)
    expect(vm.cleanupMaxAge).toBe(180)
  })
})
