/**
 * views/system/BackupManagement.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：onMounted 三路加载、fetchBackupList/fetchBackupStats 多级 ?? 链、
 * loadScheduleConfig/saveSchedule 全分支、localStorage 自动备份配置（读取/watch/保存）、
 * nextBackupTime computed（daily/weekly/monthly/非枚举）、创建/删除/恢复/下载全流程、
 * formatSize/formatTime 工具函数、模板 v-if/三元/??/?. 两侧。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂会被提升到模块顶部注册，直接引用下方 const 会触发 TDZ；
// 所有被工厂引用的对象放入 vi.hoisted 中先行初始化。
const { ElMessage, confirmMock, mockGet, mockPost, mockPut, mockDel, getTokenMock, fetchMock } =
  vi.hoisted(() => {
    return {
      ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
      confirmMock: vi.fn(),
      mockGet: vi.fn(),
      mockPost: vi.fn(),
      mockPut: vi.fn(),
      mockDel: vi.fn(),
      getTokenMock: vi.fn(),
      fetchMock: vi.fn(),
    }
  })

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: getTokenMock },
}))

import BackupManagement from '@/views/system/BackupManagement.vue'

const STORAGE_KEY = 'auto-backup-config'

const statsFull = {
  totalBackups: 2,
  totalSize: 4096,
  lastBackup: '2024-01-01T02:00:00',
  fullBackups: 1,
  incrementalBackups: 1,
  scheduleEnabled: true,
}

const backupA = {
  file_name: 'bak-a.zip',
  description: '全量A',
  backup_type: 'full',
  file_size: 2048,
  created_at: '2024-01-01T02:00:00',
  is_encrypted: false,
}
const backupB = {
  file_name: 'bak-b.zip',
  description: '增量B',
  backup_type: 'incremental',
  file_size: 1024,
  created_at: '2024-01-02T02:00:00',
  is_encrypted: true,
}

function defaultGetImpl(url: string) {
  if (url === '/system/backup') {
    return Promise.resolve({ data: { data: { items: [backupA, backupB] } } })
  }
  if (url === '/system/backup/stats') {
    return Promise.resolve({ data: { data: { ...statsFull } } })
  }
  if (url === '/system/backup/schedule') {
    return Promise.resolve({
      data: { data: { enabled: true, frequency: 'weekly', backup_time: '03:30', retention_count: 10 } },
    })
  }
  return Promise.resolve({ data: {} })
}

function mountComp() {
  // setup.ts 的全局 el-* stub 默认不渲染插槽，需 renderStubDefaultSlot；
  // 具名插槽（card 的 header、dialog 的 footer）与作用域插槽（表格行）需自定义 stub。
  return mount(BackupManagement, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-upload': {
          name: 'ElUpload',
          props: ['onRemove', 'onChange'],
          template: '<div class="el-upload-stub"><slot /></div>',
          emits: ['remove', 'change'],
        },
        // 注入两行样本数据，覆盖 backup_type 三元两侧、formatSize/formatTime 不同输入
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return {
              rowA: {
                file_name: 'row-a.zip',
                description: 'A',
                backup_type: 'incremental',
                file_size: 2048,
                created_at: '2024-01-01T02:00:00',
                is_encrypted: true,
              },
              rowB: {
                file_name: 'row-b.zip',
                description: 'B',
                backup_type: 'full',
                file_size: 0,
                created_at: null,
                is_encrypted: false,
              },
            }
          },
        },
      },
    },
  })
}

/** 按文本点击按钮（多个同名按钮时取第 index 个） */
async function clickButton(wrapper: any, text: string, index = 0) {
  const btns = wrapper.findAll('el-button-stub').filter((b: any) => b.text().includes(text))
  expect(btns.length).toBeGreaterThan(index)
  await btns[index].trigger('click')
  await flushPromises()
}

/** 第 idx 个 el-dialog-stub 内按文本点击 */
async function clickDialogButton(wrapper: any, dialogIdx: number, text: string) {
  const dialogs = wrapper.findAll('.el-dialog-stub')
  const btns = dialogs[dialogIdx].findAll('el-button-stub').filter((b: any) => b.text().includes(text))
  expect(btns.length).toBeGreaterThan(0)
  await btns[0].trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGet.mockImplementation(defaultGetImpl)
  mockPost.mockResolvedValue({ success: true })
  mockPut.mockResolvedValue({ success: true })
  mockDel.mockResolvedValue({ success: true })
  confirmMock.mockResolvedValue('confirm')
  getTokenMock.mockReturnValue('test-token')
  fetchMock.mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(['x'])) })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe('挂载与数据加载', () => {
  it('onMounted 并行加载列表/统计/计划配置', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/system/backup')
    expect(mockGet).toHaveBeenCalledWith('/system/backup/stats')
    expect(mockGet).toHaveBeenCalledWith('/system/backup/schedule')
    expect(vm.backupList).toHaveLength(2)
    expect(vm.backupStats).toEqual(statsFull)
    expect(vm.scheduleConfig).toEqual({
      enabled: true,
      frequency: 'weekly',
      backupTime: '03:30',
      retentionCount: 10,
    })
    expect(vm.loading).toBe(false)
  })

  it('fetchBackupList：resData.items 形态 / 空对象 / null 三级 ?? 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockResolvedValueOnce({ data: { items: [backupA] } })
    await vm.fetchBackupList()
    expect(vm.backupList).toEqual([backupA])
    mockGet.mockResolvedValueOnce({ data: {} })
    await vm.fetchBackupList()
    expect(vm.backupList).toEqual([])
    mockGet.mockResolvedValueOnce({ data: null })
    await vm.fetchBackupList()
    expect(vm.backupList).toEqual([])
  })

  it('fetchBackupList：请求失败 → 错误提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/backup') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    await vm.fetchBackupList()
    expect(ElMessage.error).toHaveBeenCalledWith('获取备份列表失败')
  })

  it('fetchBackupStats：res.data 直返形态 + 字段全缺省 ?? 兜底', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/backup/stats') return Promise.resolve({ data: { totalBackups: 5 } })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).backupStats).toEqual({
      totalBackups: 5,
      totalSize: 0,
      lastBackup: null,
      fullBackups: 0,
      incrementalBackups: 0,
      scheduleEnabled: false,
    })
  })

  it('fetchBackupStats：请求失败 → 静默（不弹错误）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    ElMessage.error.mockClear()
    mockGet.mockRejectedValueOnce(new Error('net'))
    await vm.fetchBackupStats()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('loadScheduleConfig：camelCase 字段 / 全缺省 / res.data 直返 / res 直返 / falsy 数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // backupTime / retentionCount camelCase 侧
    mockGet.mockResolvedValueOnce({
      data: { data: { enabled: false, frequency: 'monthly', backupTime: '01:00', retentionCount: 3 } },
    })
    await vm.loadScheduleConfig()
    expect(vm.scheduleConfig).toEqual({ enabled: false, frequency: 'monthly', backupTime: '01:00', retentionCount: 3 })
    // 空对象 → 全部 ?? 默认值
    mockGet.mockResolvedValueOnce({ data: { data: {} } })
    await vm.loadScheduleConfig()
    expect(vm.scheduleConfig).toEqual({ enabled: false, frequency: 'daily', backupTime: '02:00', retentionCount: 7 })
    // res.data 直返（无嵌套 data）
    mockGet.mockResolvedValueOnce({ data: { enabled: true, frequency: 'weekly', backup_time: '04:00', retention_count: 5 } })
    await vm.loadScheduleConfig()
    expect(vm.scheduleConfig.backupTime).toBe('04:00')
    // res 直返（axios 已拆包形态）
    mockGet.mockResolvedValueOnce({ enabled: true, frequency: 'daily', backup_time: '05:00', retention_count: 6 })
    await vm.loadScheduleConfig()
    expect(vm.scheduleConfig.backupTime).toBe('05:00')
    // falsy 数据（0）→ if (data) 为假，保持原值
    mockGet.mockResolvedValueOnce(0)
    await vm.loadScheduleConfig()
    expect(vm.scheduleConfig.backupTime).toBe('05:00')
  })

  it('loadScheduleConfig：请求失败 → 保留默认值', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/backup/schedule') return Promise.reject(new Error('404'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).scheduleConfig).toEqual({
      enabled: false,
      frequency: 'daily',
      backupTime: '02:00',
      retentionCount: 7,
    })
  })

  it('saveSchedule 成功：点击保存计划按钮，PUT 携带 snake_case 载荷', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.scheduleConfig = { enabled: true, frequency: 'monthly', backupTime: '06:00', retentionCount: 12 }
    await clickButton(wrapper, '保存计划')
    expect(mockPut).toHaveBeenCalledWith('/system/backup/schedule', {
      enabled: true,
      frequency: 'monthly',
      backup_time: '06:00',
      retention_count: 12,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('备份计划已保存')
    expect(vm.savingSchedule).toBe(false)
  })

  it('saveSchedule 失败：后端 detail 与兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockPut.mockRejectedValueOnce({ response: { data: { detail: '频率非法' } } })
    await vm.saveSchedule()
    expect(ElMessage.error).toHaveBeenCalledWith('频率非法')
    mockPut.mockRejectedValueOnce(new Error('net'))
    await vm.saveSchedule()
    expect(ElMessage.error).toHaveBeenCalledWith('保存备份计划失败')
    expect(vm.savingSchedule).toBe(false)
  })
})

describe('自动备份设置（localStorage）', () => {
  it('无存储 → 默认配置；nextBackupTime 显示未启用', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.autoBackupConfig).toEqual({ enabled: false, frequency: 'daily', retentionCount: 7 })
    expect(vm.nextBackupTime).toBe('未启用')
  })

  it('合法存储 → 原样载入', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ enabled: true, frequency: 'weekly', retentionCount: 15 }))
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).autoBackupConfig).toEqual({ enabled: true, frequency: 'weekly', retentionCount: 15 })
  })

  it('非法字段逐项回退：enabled 非布尔 / frequency 非枚举 / retentionCount 非数、越界', async () => {
    const cases: Array<[any, any]> = [
      [
        { enabled: 'yes', frequency: 'weekly', retentionCount: 15 },
        { enabled: false, frequency: 'weekly', retentionCount: 15 },
      ],
      [
        { enabled: true, frequency: 'hourly', retentionCount: 15 },
        { enabled: true, frequency: 'daily', retentionCount: 15 },
      ],
      [
        { enabled: true, frequency: 'daily', retentionCount: '5' },
        { enabled: true, frequency: 'daily', retentionCount: 7 },
      ],
      [
        { enabled: true, frequency: 'daily', retentionCount: 0 },
        { enabled: true, frequency: 'daily', retentionCount: 7 },
      ],
      [
        { enabled: true, frequency: 'daily', retentionCount: 99 },
        { enabled: true, frequency: 'daily', retentionCount: 7 },
      ],
    ]
    for (const [stored, expected] of cases) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
      const wrapper = mountComp()
      expect((wrapper.vm as any).autoBackupConfig).toEqual(expected)
      wrapper.unmount()
    }
  })

  it('存储 JSON 损坏 → catch 后回退默认', async () => {
    localStorage.setItem(STORAGE_KEY, '{broken-json')
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).autoBackupConfig).toEqual({ enabled: false, frequency: 'daily', retentionCount: 7 })
  })

  it('watch：修改配置 → 写入 localStorage', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.autoBackupConfig.enabled = true
    vm.autoBackupConfig.retentionCount = 20
    await nextTick()
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    expect(saved).toMatchObject({ enabled: true, retentionCount: 20 })
  })

  it('watch：localStorage 写入抛错 → 静默吞掉', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const spy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded')
    })
    vm.autoBackupConfig.enabled = true
    await nextTick()
    expect(spy).toHaveBeenCalled()
    spy.mockRestore()
  })

  it('saveAutoBackupConfig：点击保存设置 → 成功提示并落盘', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.autoBackupConfig.frequency = 'monthly'
    await clickButton(wrapper, '保存设置')
    expect(ElMessage.success).toHaveBeenCalledWith('自动备份设置已保存')
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')).toMatchObject({ frequency: 'monthly' })
  })

  it('saveAutoBackupConfig：写入抛错 → 错误提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const spy = vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded')
    })
    vm.saveAutoBackupConfig()
    expect(ElMessage.error).toHaveBeenCalledWith('保存自动备份设置失败')
    spy.mockRestore()
  })
})

describe('nextBackupTime 计算', () => {
  function mountWithConfig() {
    return mountComp()
  }

  it('daily：凌晨 1 点 → 今日 02:00（不加一天）', async () => {
    const wrapper = mountWithConfig()
    await flushPromises()
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2024, 0, 1, 1, 0, 0))
    const vm = wrapper.vm as any
    vm.autoBackupConfig.enabled = true
    vm.autoBackupConfig.frequency = 'daily'
    expect(vm.nextBackupTime).toContain('2024/1/1')
    expect(vm.nextBackupTime).toContain('02:00')
  })

  it('daily：上午 10 点 → 次日 02:00', async () => {
    const wrapper = mountWithConfig()
    await flushPromises()
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2024, 0, 1, 10, 0, 0))
    const vm = wrapper.vm as any
    vm.autoBackupConfig.enabled = true
    vm.autoBackupConfig.frequency = 'daily'
    expect(vm.nextBackupTime).toContain('2024/1/2')
  })

  it('weekly：周日 → 次日周一 02:00（dayOfWeek===0 分支）', async () => {
    const wrapper = mountWithConfig()
    await flushPromises()
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2024, 0, 7, 10, 0, 0)) // 2024-01-07 为周日
    const vm = wrapper.vm as any
    vm.autoBackupConfig.enabled = true
    vm.autoBackupConfig.frequency = 'weekly'
    expect(vm.nextBackupTime).toContain('2024/1/8')
  })

  it('weekly：周三 → 下周一 02:00（(8-day)%7 分支）', async () => {
    const wrapper = mountWithConfig()
    await flushPromises()
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2024, 0, 3, 10, 0, 0)) // 周三
    const vm = wrapper.vm as any
    vm.autoBackupConfig.enabled = true
    vm.autoBackupConfig.frequency = 'weekly'
    expect(vm.nextBackupTime).toContain('2024/1/8')
  })

  it('monthly：月中 → 次月 1 号 02:00', async () => {
    const wrapper = mountWithConfig()
    await flushPromises()
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2024, 0, 15, 10, 0, 0))
    const vm = wrapper.vm as any
    vm.autoBackupConfig.enabled = true
    vm.autoBackupConfig.frequency = 'monthly'
    expect(vm.nextBackupTime).toContain('2024/2/1')
  })

  it('非枚举 frequency（防御路径）→ switch 无命中，保持今日 02:00', async () => {
    const wrapper = mountWithConfig()
    await flushPromises()
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2024, 0, 5, 10, 0, 0))
    const vm = wrapper.vm as any
    vm.autoBackupConfig.enabled = true
    vm.autoBackupConfig.frequency = 'bogus'
    expect(vm.nextBackupTime).toContain('2024/1/5')
    expect(vm.nextBackupTime).toContain('02:00')
  })
})

describe('创建备份', () => {
  it('点击创建备份 → 表单重置并打开对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.backupForm = { description: '脏数据', include_uploads: false, password: 'x' }
    await clickButton(wrapper, '创建备份')
    expect(vm.backupForm).toEqual({ description: '手动备份', include_uploads: true, password: '' })
    expect(vm.createDialogVisible).toBe(true)
  })

  it('确定创建成功：密码非空明文传递，关弹窗并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreateBackup()
    vm.backupForm.description = '全量备份'
    vm.backupForm.password = 'secret'
    mockGet.mockClear()
    await clickDialogButton(wrapper, 0, '确定')
    expect(mockPost).toHaveBeenCalledWith('/system/backup', {
      description: '全量备份',
      include_uploads: true,
      password: 'secret',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已创建')
    expect(vm.createDialogVisible).toBe(false)
    expect(mockGet).toHaveBeenCalled() // 成功后刷新列表
    expect(vm.creating).toBe(false)
  })

  it('确定创建：密码为空 → 传 null', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreateBackup()
    vm.backupForm.password = ''
    await vm.confirmCreateBackup()
    expect(mockPost).toHaveBeenCalledWith('/system/backup', expect.objectContaining({ password: null }))
  })

  it('创建返回 success:false → 不提示不刷新', async () => {
    mockPost.mockResolvedValue({ success: false })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreateBackup()
    mockGet.mockClear()
    await vm.confirmCreateBackup()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.createDialogVisible).toBe(true)
    expect(mockGet).not.toHaveBeenCalled()
  })

  it('创建失败：后端 detail 与兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreateBackup()
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '空间不足' } } })
    await vm.confirmCreateBackup()
    expect(ElMessage.error).toHaveBeenCalledWith('空间不足')
    mockPost.mockRejectedValueOnce(new Error('net'))
    await vm.confirmCreateBackup()
    expect(ElMessage.error).toHaveBeenCalledWith('创建备份失败')
    expect(vm.creating).toBe(false)
  })

  it('创建对话框取消按钮 → 关闭弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreateBackup()
    await nextTick()
    await clickDialogButton(wrapper, 0, '取消')
    expect(vm.createDialogVisible).toBe(false)
  })
})

describe('删除备份', () => {
  it('确认删除成功：点击行内删除按钮，提示并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockClear()
    await clickButton(wrapper, '删除', 0)
    expect(confirmMock).toHaveBeenCalledWith(expect.stringContaining('row-a.zip'), '警告', expect.objectContaining({ type: 'warning' }))
    expect(mockDel).toHaveBeenCalledWith('/system/backup/row-a.zip')
    expect(ElMessage.success).toHaveBeenCalledWith('已删除')
    expect(mockGet).toHaveBeenCalled()
    expect(vm.loading).toBe(false)
  })

  it('删除返回 success:false → 不提示', async () => {
    mockDel.mockResolvedValue({ success: false })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete({ file_name: 'x.zip' })
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('用户取消确认 → 静默返回，不发请求不报错', async () => {
    confirmMock.mockRejectedValue('cancel')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete({ file_name: 'x.zip' })
    expect(mockDel).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('删除接口异常 → 错误提示', async () => {
    mockDel.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete({ file_name: 'x.zip' })
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})

describe('恢复备份', () => {
  it('点击行内恢复按钮 → 设置目标、清空密码、打开对话框（加密行渲染密码表单）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.restoreForm.password = 'dirty'
    await clickButton(wrapper, '恢复', 0) // row-a.zip（is_encrypted: true）
    expect(vm.restoreTarget.file_name).toBe('row-a.zip')
    expect(vm.restoreForm.password).toBe('')
    expect(vm.restoreDialogVisible).toBe(true)
    await nextTick() // 渲染 is_encrypted 为真的密码表单分支
  })

  it('confirmRestore：无目标 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.restoreTarget = null
    await vm.confirmRestore()
    expect(mockPost.mock.calls.some((c) => c[0] === '/system/backup/restore')).toBe(false)
  })

  it('确认恢复成功：密码非空明文传递，关弹窗并定时跳转登录页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'enc.zip', is_encrypted: true })
    vm.restoreForm.password = 'pw123'
    vi.useFakeTimers()
    await vm.confirmRestore()
    expect(mockPost).toHaveBeenCalledWith('/system/backup/restore', { filename: 'enc.zip', password: 'pw123' })
    expect(ElMessage.success).toHaveBeenCalledWith('系统恢复成功，请重新登录')
    expect(vm.restoreDialogVisible).toBe(false)
    expect(vm.restoring).toBe(false)
    vi.advanceTimersByTime(2000) // 触发 setTimeout 回调（window.location.href = '/login'）
    vi.useRealTimers()
  })

  it('确认恢复：密码为空 → 传 null', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'plain.zip', is_encrypted: false })
    vi.useFakeTimers()
    await vm.confirmRestore()
    expect(mockPost).toHaveBeenCalledWith('/system/backup/restore', { filename: 'plain.zip', password: null })
    vi.useRealTimers()
  })

  it('恢复返回 success:false → 不提示不关窗', async () => {
    mockPost.mockResolvedValue({ success: false })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'x.zip' })
    await vm.confirmRestore()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.restoreDialogVisible).toBe(true)
  })

  it('恢复失败：后端 detail 与兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'x.zip' })
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '密码错误' } } })
    await vm.confirmRestore()
    expect(ElMessage.error).toHaveBeenCalledWith('密码错误')
    mockPost.mockRejectedValueOnce(new Error('net'))
    await vm.confirmRestore()
    expect(ElMessage.error).toHaveBeenCalledWith('恢复失败')
    expect(vm.restoring).toBe(false)
  })

  it('恢复对话框取消按钮 → 关闭弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleRestore({ file_name: 'x.zip' })
    await nextTick()
    await clickDialogButton(wrapper, 1, '取消')
    expect(vm.restoreDialogVisible).toBe(false)
  })
})

describe('下载备份', () => {
  it('点击行内下载按钮 → fetch 携带 token，创建 a 标签触发下载', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    await clickButton(wrapper, '下载', 0)
    expect(getTokenMock).toHaveBeenCalled()
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/v1/system/backup/download/row-a.zip')
    expect(opts.headers.Authorization).toBe('Bearer test-token')
    expect(clickSpy).toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it('VITE_API_BASE_URL 自定义 → 使用环境变量前缀', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://api.test')
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDownload({ file_name: 'x.zip' })
    expect(fetchMock.mock.calls[0][0]).toBe('http://api.test/system/backup/download/x.zip')
    clickSpy.mockRestore()
  })

  it('response.ok 为假 → 抛错并提示下载失败', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 404, blob: () => Promise.resolve(new Blob(['x'])) })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDownload({ file_name: 'x.zip' })
    expect(ElMessage.error).toHaveBeenCalledWith('下载备份失败')
  })

  it('fetch 网络异常 → 提示下载失败', async () => {
    fetchMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDownload({ file_name: 'x.zip' })
    expect(ElMessage.error).toHaveBeenCalledWith('下载备份失败')
  })
})

describe('工具函数', () => {
  it('formatSize：空值 / B / KB / MB / GB', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatSize(0)).toBe('0 B')
    expect(vm.formatSize(null)).toBe('0 B')
    expect(vm.formatSize(512)).toBe('512 B')
    expect(vm.formatSize(2048)).toBe('2 KB')
    expect(vm.formatSize(5 * 1024 * 1024)).toBe('5 MB')
    expect(vm.formatSize(3 * 1024 * 1024 * 1024)).toBe('3 GB')
  })

  it('formatTime：空值 / 正常时间 / 异常输入', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatTime(null)).toBe('-')
    expect(vm.formatTime('')).toBe('-')
    expect(vm.formatTime('2024-01-01T02:00:00')).toContain('2024')
    expect(vm.formatTime(Symbol('bad') as any)).toBe('-')
  })
})

describe('模板分支渲染', () => {
  it('backupStats 置空 → descriptions 的 ?? 0 右侧与 scheduleEnabled 假侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.text()).toContain('已启用') // scheduleEnabled: true（真侧）
    vm.backupStats = {}
    await nextTick() // totalBackups/totalSize/fullBackups/incrementalBackups ?? 0 + 假侧 tag
    expect(wrapper.text()).toContain('未启用')
  })

  it('el-empty：列表为空且非加载时渲染；loading 为真时短路', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/backup') return Promise.resolve({ data: { data: { items: [] } } })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.find('el-empty-stub').exists()).toBe(true)
    const vm = wrapper.vm as any
    vm.loading = true
    await nextTick() // !loading 为假的短路侧
    vm.backupList = [backupA]
    vm.loading = false
    await nextTick() // 列表非空 → 不渲染
    expect(wrapper.find('el-empty-stub').exists()).toBe(false)
  })

  it('备份计划卡 tag：enabled 真假两侧文本', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.text()).toContain('已启用') // loadScheduleConfig 载入 enabled: true
    vm.scheduleConfig.enabled = false
    await nextTick()
    expect(wrapper.text()).toContain('未启用')
  })

  it('恢复对话框：restoreTarget 为 null 的 ?. 短路侧与 file_size 缺失的 ?? 右侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 初始 restoreTarget=null 时模板中 restoreTarget?.file_name 等走 nullish 侧
    await nextTick()
    vm.handleRestore({ file_name: 'nofsize.zip', created_at: null, is_encrypted: false })
    await nextTick() // file_size 缺失时 formatSize(restoreTarget?.file_size ?? 0)
    expect(wrapper.text()).toContain('nofsize.zip')
  })

  describe('备份目标目录（T1.2）', () => {
    it('loadBackupDirs 成功填充 dirs 与 current', async () => {
      mockGet.mockResolvedValueOnce({}) // fetchBackupList
      mockGet.mockResolvedValueOnce({}) // fetchBackupStats
      mockGet.mockResolvedValueOnce({}) // loadScheduleConfig
      mockGet.mockResolvedValueOnce({
        dirs: [{ path: 'E:\\', type: 'removable', available: true }],
        current: 'E:\\',
      }) // loadBackupDirs
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      expect(vm.backupDirs.length).toBe(1)
      expect(vm.backupTarget).toBe('E:\\')
      expect(vm.dirTypeLabel('removable')).toBe('可移动')
      expect(vm.dirTypeLabel('fixed')).toBe('固定盘')
      expect(vm.dirTypeLabel('network')).toBe('网络盘')
      expect(vm.dirTypeLabel('configured')).toBe('已配置')
      expect(vm.dirTypeLabel('unknown-x')).toBe('unknown-x')
    })

    it('loadBackupDirs 失败提示 error', async () => {
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({})
      mockGet.mockRejectedValueOnce(new Error('net'))
      const wrapper = mountComp()
      await flushPromises()
      expect(ElMessage.error).toHaveBeenCalledWith('检测备份目录失败')
    })

    it('saveBackupTarget 成功保存并刷新', async () => {
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({ dirs: [], current: 'E:\\bk' })
      mockPut.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({ dirs: [{ path: 'E:\\bk', type: 'fixed', available: true }], current: 'E:\\bk' })
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.backupTarget = 'E:\\bk'
      await vm.saveBackupTarget()
      expect(mockPut).toHaveBeenCalledWith('/system/backup/target', { target_dir: 'E:\\bk' })
      expect(ElMessage.success).toHaveBeenCalledWith('备份目标已保存')
      expect(vm.backupDirs.length).toBe(1)
    })

    it('saveBackupTarget 失败提示 detail', async () => {
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({ dirs: [], current: '' })
      mockPut.mockRejectedValueOnce({ detail: '目标目录不可用' })
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.backupTarget = 'Z:\\x'
      await vm.saveBackupTarget()
      expect(ElMessage.error).toHaveBeenCalledWith('目标目录不可用')
    })

    it('点击磁盘 tag 回填 backupTarget（模板 @click）', async () => {
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({})
      mockGet.mockResolvedValueOnce({
        dirs: [{ path: 'D:\\', type: 'removable', available: true }],
        current: '',
      })
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      expect(vm.backupTarget).toBe('')
      vm.backupTarget = 'D:\\'
      expect(wrapper.text()).toContain('D:\\')
    })
  })
})

describe('导入备份包恢复（上传恢复链路）', () => {
  it('onImportFileChange：raw 与非 raw 两臂', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.onImportFileChange({ raw: new File(['x'], 'a.zip') })
    expect(vm.importFile).toBeInstanceOf(File)
    vm.onImportFileChange({})
    expect(vm.importFile).toBeNull()
  })

  it('confirmImportRestore：无文件 → warning', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importFile = null
    await vm.confirmImportRestore()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择备份包文件')
    expect(mockPost).not.toHaveBeenCalledWith('/system/backup/upload-restore', expect.anything())
  })

  it('confirmImportRestore：成功 → 提示 + 关窗 + 清空 + 定时跳转登录', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importFile = new File(['x'], 'pkg.zip')
    mockPost.mockResolvedValue({ success: true })
    vi.useFakeTimers()
    await vm.confirmImportRestore()
    expect(mockPost).toHaveBeenCalledWith('/system/backup/upload-restore', expect.anything())
    expect(ElMessage.success).toHaveBeenCalledWith('导入恢复成功，系统将重新登录')
    expect(vm.importDialogVisible).toBe(false)
    expect(vm.importFile).toBeNull()
    vi.advanceTimersByTime(2000)
    vi.useRealTimers()
  })

  it('confirmImportRestore：成功但 success 为 false → 不提示不关窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importFile = new File(['x'], 'pkg.zip')
    vm.importDialogVisible = true
    mockPost.mockResolvedValue({ success: false })
    await vm.confirmImportRestore()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.importDialogVisible).toBe(true)
  })

  it('confirmImportRestore：失败 detail 与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importFile = new File(['x'], 'pkg.zip')
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '包校验失败' } } })
    await vm.confirmImportRestore()
    expect(ElMessage.error).toHaveBeenCalledWith('包校验失败')
    mockPost.mockRejectedValueOnce(new Error('net'))
    await vm.confirmImportRestore()
    expect(ElMessage.error).toHaveBeenCalledWith('导入恢复失败')
    expect(vm.importing).toBe(false)
  })

  it('handleDownload：fetch 成功触发下载；失败提示', async () => {
    getTokenMock.mockReturnValue('tk-1')
    const okResponse = {
      ok: true,
      blob: vi.fn(() => Promise.resolve(new Blob(['data']))),
    }
    fetchMock.mockResolvedValueOnce(okResponse)
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock')
    globalThis.URL.revokeObjectURL = vi.fn()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDownload({ file_name: 'bak.zip' })
    expect(fetchMock).toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()

    fetchMock.mockRejectedValueOnce(new Error('net'))
    await vm.handleDownload({ file_name: 'bak.zip' })
    expect(ElMessage.error).toHaveBeenCalledWith('下载备份失败')
    clickSpy.mockRestore()
    delete (globalThis as any).URL.createObjectURL
    delete (globalThis as any).URL.revokeObjectURL
    vi.restoreAllMocks()
  })

  it('导入备份包对话框模板事件：打开/取消/v-model/on-remove/密码输入', async () => {
    mockGet.mockResolvedValueOnce({})
    mockGet.mockResolvedValueOnce({})
    mockGet.mockResolvedValueOnce({})
    mockGet.mockResolvedValueOnce({ dirs: [], current: '' })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // L91 打开按钮 → importDialogVisible = true
    await clickButton(wrapper, '导入备份包')
    expect(vm.importDialogVisible).toBe(true)

    // L260 el-dialog v-model 关闭
    const dialogComps = wrapper.findAllComponents({ name: 'ElDialog' })
    const importDialog = dialogComps[dialogComps.length - 1]
    await importDialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.importDialogVisible).toBe(false)

    // 重新打开后 L297 取消按钮 → 关闭
    vm.importDialogVisible = true
    await nextTick()
    await clickDialogButton(wrapper, dialogComps.length - 1, '取消')
    expect(vm.importDialogVisible).toBe(false)

    // L289 el-input v-model 更新密码（导入对话框内的密码输入框）
    vm.importDialogVisible = true
    await nextTick()
    const dialogComps2 = wrapper.findAllComponents({ name: 'ElDialog' })
    const importDialogComp = dialogComps2[dialogComps2.length - 1]
    const importInputs = importDialogComp.findAllComponents({ name: 'ElInput' })
    expect(importInputs.length).toBeGreaterThan(0)
    await importInputs[0].vm.$emit('update:modelValue', 'secret')
    expect(vm.importForm.password).toBe('secret')

    // L278 el-upload on-remove → importFile = null
    vm.importFile = new File(['x'], 'a.zip')
    const uploadComps = wrapper.findAllComponents({ name: 'ElUpload' })
    if (uploadComps.length > 0) {
      const removeHandler = uploadComps[uploadComps.length - 1].props('onRemove')
      if (typeof removeHandler === 'function') {
        removeHandler()
        expect(vm.importFile).toBeNull()
      } else {
        uploadComps[uploadComps.length - 1].vm.$emit('remove')
      }
    }
    wrapper.unmount()
  })
})
