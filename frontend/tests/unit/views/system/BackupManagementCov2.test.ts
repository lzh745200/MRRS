/**
 * views/system/BackupManagement.vue 覆盖率补满（第二批次）
 *
 * 既有 BackupManagementCov.test.ts 已覆盖语句/行至 100%，本文件补齐剩余的：
 *  1. 模板 13 个 v-model 内联 onUpdate:modelValue 箭头函数
 *     （switch×3 / radio-group / input-number×2 / select / time-picker / dialog×2 / input×3）
 *  2. nextBackupTime weekly 分支 line 306：周一上午 next<=now 成立 → +7 天
 *  3. fetchBackupStats line 383：resData 空对象 → totalBackups ?? 0 右侧兜底
 *
 * 不改动既有 spec；与 BackupManagementCov.test.ts 合并统计后四指标 100%。
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
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: getTokenMock },
}))

import BackupManagement from '@/views/system/BackupManagement.vue'

const backupA = {
  file_name: 'bak-a.zip',
  description: '全量A',
  backup_type: 'full',
  file_size: 2048,
  created_at: '2024-01-01T02:00:00',
  is_encrypted: false,
}

function defaultGetImpl(url: string) {
  if (url === '/system/backup') {
    return Promise.resolve({ data: { data: { items: [backupA] } } })
  }
  if (url === '/system/backup/stats') {
    return Promise.resolve({
      data: {
        data: {
          totalBackups: 1,
          totalSize: 2048,
          lastBackup: '2024-01-01T02:00:00',
          fullBackups: 1,
          incrementalBackups: 0,
          scheduleEnabled: true,
        },
      },
    })
  }
  if (url === '/system/backup/schedule') {
    return Promise.resolve({
      data: {
        data: { enabled: true, frequency: 'weekly', backup_time: '03:30', retention_count: 10 },
      },
    })
  }
  return Promise.resolve({ data: {} })
}

function mountComp() {
  // setup.ts 的全局 el-* stub 默认不渲染插槽，需 renderStubDefaultSlot；
  // 具名插槽（card 的 header、dialog 的 footer）需自定义 stub；
  // el-time-picker 不在全局 stub 列表中，需具名 stub 才能捕获 v-model 事件。
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
          props: ['modelValue'],
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-time-picker': {
          name: 'ElTimePicker',
          props: ['modelValue'],
          template: '<div class="el-time-picker-stub" />',
          emits: ['update:modelValue'],
        },
        // 注入两行样本数据，表格列作用域插槽的 row 才有值
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
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
})

describe('模板 v-model 内联更新函数覆盖', () => {
  it('自动备份表单：el-switch / el-radio-group / el-input-number 更新 autoBackupConfig', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.autoBackupConfig).toEqual({ enabled: false, frequency: 'daily', retentionCount: 7 })

    // 模板顺序：ElSwitch[0]=自动备份启用（line 12）
    wrapper.findAllComponents({ name: 'ElSwitch' })[0].vm.$emit('update:modelValue', true)
    await nextTick()
    expect(vm.autoBackupConfig.enabled).toBe(true)

    // ElRadioGroup[0]=备份频率（line 16）
    wrapper.findAllComponents({ name: 'ElRadioGroup' })[0].vm.$emit('update:modelValue', 'weekly')
    await nextTick()
    expect(vm.autoBackupConfig.frequency).toBe('weekly')

    // ElInputNumber[0]=保留份数（line 26）
    wrapper.findAllComponents({ name: 'ElInputNumber' })[0].vm.$emit('update:modelValue', 15)
    await nextTick()
    expect(vm.autoBackupConfig.retentionCount).toBe(15)
    wrapper.unmount()
  })

  it('备份计划表单：el-switch / el-select / el-time-picker / el-input-number 更新 scheduleConfig', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.scheduleConfig).toEqual({
      enabled: true,
      frequency: 'weekly',
      backupTime: '03:30',
      retentionCount: 10,
    })

    // ElSwitch[1]=启用定时备份（line 122）
    wrapper.findAllComponents({ name: 'ElSwitch' })[1].vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.scheduleConfig.enabled).toBe(false)

    // ElSelect[0]=备份频率（line 126）
    wrapper.findAllComponents({ name: 'ElSelect' })[0].vm.$emit('update:modelValue', 'monthly')
    await nextTick()
    expect(vm.scheduleConfig.frequency).toBe('monthly')

    // ElTimePicker[0]=备份时间（line 137）
    wrapper.findAllComponents({ name: 'ElTimePicker' })[0].vm.$emit('update:modelValue', '05:45')
    await nextTick()
    expect(vm.scheduleConfig.backupTime).toBe('05:45')

    // ElInputNumber[1]=保留份数（line 146）
    wrapper.findAllComponents({ name: 'ElInputNumber' })[1].vm.$emit('update:modelValue', 20)
    await nextTick()
    expect(vm.scheduleConfig.retentionCount).toBe(20)
    wrapper.unmount()
  })

  it('创建备份对话框：el-dialog / el-input(描述) / el-switch(含上传) / el-input(密码)', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.createDialogVisible).toBe(false)

    // ElDialog[0]=创建备份对话框（line 161）
    wrapper.findAllComponents({ name: 'ElDialog' })[0].vm.$emit('update:modelValue', true)
    await nextTick()
    expect(vm.createDialogVisible).toBe(true)

    // ElInput[1]=备份描述（备份目标输入框占用 [0]）
    wrapper.findAllComponents({ name: 'ElInput' })[1].vm.$emit('update:modelValue', '周末备份')
    await nextTick()
    expect(vm.backupForm.description).toBe('周末备份')

    // ElSwitch[2]=包含上传文件（line 167）
    wrapper.findAllComponents({ name: 'ElSwitch' })[2].vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.backupForm.include_uploads).toBe(false)

    // ElInput[2]=加密密码（line 171）
    wrapper.findAllComponents({ name: 'ElInput' })[2].vm.$emit('update:modelValue', 'pw!')
    await nextTick()
    expect(vm.backupForm.password).toBe('pw!')
    wrapper.unmount()
  })

  it('恢复备份对话框：el-dialog 与解密密码 el-input（is_encrypted 表单渲染后）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 加密备份 → 渲染解密密码表单（line 195 v-if），ElInput[2] 才存在
    vm.handleRestore({ file_name: 'enc.zip', created_at: null, is_encrypted: true })
    await nextTick()
    expect(vm.restoreDialogVisible).toBe(true)

    // ElInput[3]=解密密码（备份目标输入框占 [0]，描述 [1]，密码 [2]，导入对话框密码占 [4]）
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBe(5)
    inputs[3].vm.$emit('update:modelValue', 'decrypt-pw')
    await nextTick()
    expect(vm.restoreForm.password).toBe('decrypt-pw')

    // ElDialog[1]=恢复备份对话框（line 187）
    wrapper.findAllComponents({ name: 'ElDialog' })[1].vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.restoreDialogVisible).toBe(false)
    wrapper.unmount()
  })
})

describe('分支补满', () => {
  it('weekly：周一上午（dayOfWeek=1 → daysUntilMonday=0 且 next<=now）→ +7 天', async () => {
    const wrapper = mountComp()
    await flushPromises()
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2024, 0, 1, 10, 0, 0)) // 2024-01-01 为周一
    const vm = wrapper.vm as any
    vm.autoBackupConfig.enabled = true
    vm.autoBackupConfig.frequency = 'weekly'
    // next=今日 02:00 已过期 → next.setDate(+7) → 下周一 2024-01-08
    expect(vm.nextBackupTime).toContain('2024/1/8')
    wrapper.unmount()
  })

  it('fetchBackupStats：resData 为空对象 → totalBackups ?? 0 右侧兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockResolvedValueOnce({ data: { data: {} } })
    await vm.fetchBackupStats()
    expect(vm.backupStats).toEqual({
      totalBackups: 0,
      totalSize: 0,
      lastBackup: null,
      fullBackups: 0,
      incrementalBackups: 0,
      scheduleEnabled: false,
    })
    wrapper.unmount()
  })

  it('saveBackupTarget 失败无 detail / 异常为 null → e?.detail || 兜底文案', async () => {
    mockGet.mockResolvedValueOnce({})
    mockGet.mockResolvedValueOnce({})
    mockGet.mockResolvedValueOnce({})
    mockGet.mockResolvedValueOnce({ dirs: [], current: '' })
    mockPut.mockRejectedValueOnce({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.saveBackupTarget()
    expect(ElMessage.error).toHaveBeenCalledWith('保存备份目标失败')
    mockPut.mockRejectedValueOnce(null)
    await vm.saveBackupTarget()
    expect(ElMessage.error).toHaveBeenCalledWith('保存备份目标失败')
    wrapper.unmount()
  })

  it('备份目标目录：不可写/非移动盘渲染（L73/77 假侧）+ tag 点击回填 + 目标输入框 v-model（L60/75 处理器）', async () => {
    mockGet.mockResolvedValueOnce({})
    mockGet.mockResolvedValueOnce({})
    mockGet.mockResolvedValueOnce({})
    mockGet.mockResolvedValueOnce({
      dirs: [
        { path: 'C:\\', type: 'fixed', available: true },
        { path: 'D:\\', type: 'removable', available: false },
      ],
      current: '',
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 模板 L73/77：available 假侧（danger 类型 + '·不可写'）与 type!=='removable' 侧
    expect(wrapper.text()).toContain('·不可写')
    // L75 磁盘 tag @click → 回填 backupTarget
    const dirTag = wrapper
      .findAllComponents({ name: 'ElTag' })
      .find((t: any) => t.text().includes('D:\\'))
    expect(dirTag, '磁盘目录 tag').toBeTruthy()
    dirTag!.vm.$emit('click')
    await nextTick()
    expect(vm.backupTarget).toBe('D:\\')
    // L60 备份目标输入框 v-model（ElInput[0]）
    wrapper.findAllComponents({ name: 'ElInput' })[0].vm.$emit('update:modelValue', 'E:\\bk')
    await nextTick()
    expect(vm.backupTarget).toBe('E:\\bk')
    wrapper.unmount()
  })
})

describe('导入备份包恢复', () => {
  function makeFile(): File {
    return new File(['zipbytes'], 'backup.zip', { type: 'application/zip' })
  }

  it('未选择文件点确认 → 提示先选择备份包', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importDialogVisible = true
    vm.importFile = null
    await vm.confirmImportRestore()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择备份包文件')
    expect(mockPost).not.toHaveBeenCalledWith('/system/backup/upload-restore', expect.anything())
    wrapper.unmount()
  })

  it('选择文件 + 密码 → 上传恢复成功 → 提示 + 清空 + 跳登录', async () => {
    mockPost.mockResolvedValueOnce({ success: true })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const file = makeFile()
    vm.onImportFileChange({ raw: file })
    expect(vm.importFile).toBe(file)
    vm.importForm.password = 'pwd123'
    await vm.confirmImportRestore()
    expect(mockPost).toHaveBeenCalledTimes(1)
    const [url, payload] = mockPost.mock.calls[0]
    expect(url).toBe('/system/backup/upload-restore')
    expect(payload).toBeInstanceOf(FormData)
    expect(payload.get('file')).toBe(file)
    expect(payload.get('password')).toBe('pwd123')
    expect(ElMessage.success).toHaveBeenCalled()
    expect(vm.importDialogVisible).toBe(false)
    expect(vm.importFile).toBe(null)
    expect(vm.importForm.password).toBe('')
    wrapper.unmount()
  })

  it('未填密码 → 不携带 password 字段', async () => {
    mockPost.mockResolvedValueOnce({ success: true })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.onImportFileChange({ raw: makeFile() })
    await vm.confirmImportRestore()
    const payload = mockPost.mock.calls[0][1] as FormData
    expect(payload.get('password')).toBeNull()
    wrapper.unmount()
  })

  it('上传失败 → 错误提示（含后端 detail）', async () => {
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '备份已加密' } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.onImportFileChange({ raw: makeFile() })
    await vm.confirmImportRestore()
    expect(ElMessage.error).toHaveBeenCalledWith('备份已加密')
    wrapper.unmount()
  })

  it('上传失败无 detail → 兜底文案', async () => {
    mockPost.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.onImportFileChange({ raw: makeFile() })
    await vm.confirmImportRestore()
    expect(ElMessage.error).toHaveBeenCalledWith('导入恢复失败')
    wrapper.unmount()
  })
})
