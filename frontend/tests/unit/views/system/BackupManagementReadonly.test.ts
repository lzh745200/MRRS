/**
 * 备份管理页 普通用户只读模式测试 (T11)
 * canOperateBackup 角色矩阵：user=false；admin/super_admin/is_superuser=true。
 * 页面写按钮/只读标记均由此标志驱动，写接口另有后端 require_admin 兜底。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockGet, getUserMock } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  getUserMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn(), prompt: vi.fn() },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/api/backup', () => ({
  uploadRestoreBackup: vi.fn(),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: vi.fn(() => 'tok'), getUser: getUserMock },
}))

import BackupManagement from '@/views/system/BackupManagement.vue'

function mountComp(extraStubs: Record<string, any> = {}) {
  // 不开 renderStubDefaultSlot：开启后其余 true stub（如对话框）也会渲染插槽，
  // 部分插槽依赖未初始化的表单字段（如 backup_type）会报错。
  // 自定义 stub 自己显式渲染 <slot />，不依赖该开关。
  return mount(BackupManagement, {
    global: { stubs: { ...extraStubs } },
  })
}

// 全局 el-table-column: true 的默认 stub 不渲染作用域插槽，
// 无法触发操作列的 v-if="canOperateBackup" / v-else 两侧；此处注入一行样本。
// 表格位于 el-card 内，故 el-card 也需显式渲染插槽。
const rowStubs = {
  'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
  'el-table-column': {
    template: '<div class="el-table-column-stub"><slot :row="row" /></div>',
    data() {
      return { row: { id: 1, filename: 'backup-1.zip', created_at: '2024-01-01T00:00:00Z' } }
    },
  },
  'el-button': {
    template: '<button class="el-button-stub"><slot /></button>',
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockResolvedValue({ data: {} })
})

describe('备份管理只读模式（T11）', () => {
  it('user 角色：canOperateBackup=false（写按钮与只读标记随该标志隐藏/显示）', async () => {
    getUserMock.mockReturnValue({ role: 'user', is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canOperateBackup).toBe(false)
    w.unmount()
  })

  it('admin 角色：canOperateBackup=true', async () => {
    getUserMock.mockReturnValue({ role: 'admin', is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canOperateBackup).toBe(true)
    w.unmount()
  })

  it('super_admin 与 is_superuser 均具备操作权', async () => {
    getUserMock.mockReturnValue({ role: 'super_admin', is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canOperateBackup).toBe(true)
    w.unmount()

    getUserMock.mockReturnValue({ role: 'user', is_superuser: true })
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).canOperateBackup).toBe(true)
    w2.unmount()
  })

  it('branch@343：user 无 role 且非超管 → role || "" 兜底后判定为只读', async () => {
    getUserMock.mockReturnValue({ is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canOperateBackup).toBe(false)
    w.unmount()
  })

  it('branch@345 / stmts@346-347：getUser 抛错 → catch 内保持可操作（后端权限兜底）', async () => {
    getUserMock.mockImplementation(() => {
      throw new Error('storage corrupted')
    })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canOperateBackup).toBe(true)
    w.unmount()
  })

  it('branch@161：只读用户下操作列渲染 .readonly-hint，可操作时渲染三个写按钮', async () => {
    getUserMock.mockReturnValue({ role: 'user', is_superuser: false })
    const w = mountComp(rowStubs)
    await flushPromises()
    expect(w.find('.readonly-hint').exists()).toBe(true)
    expect(w.find('.readonly-hint').text()).toBe('—')
    const roTexts = w.findAll('.el-button-stub').map((b: any) => b.text().trim())
    expect(roTexts).not.toContain('下载')
    expect(roTexts).not.toContain('恢复')
    expect(roTexts).not.toContain('删除')
    w.unmount()

    getUserMock.mockReturnValue({ role: 'admin', is_superuser: false })
    const w2 = mountComp(rowStubs)
    await flushPromises()
    expect(w2.find('.readonly-hint').exists()).toBe(false)
    const texts = w2.findAll('.el-button-stub').map((b: any) => b.text().trim())
    expect(texts).toEqual(expect.arrayContaining(['下载', '恢复', '删除']))
    w2.unmount()
  })
})

/**
 * R36（2026-10-20）：创建备份对普通用户开放，viewer 仍只读。
 *
 * 安全性依据：创建接口只在服务器生成文件、不返回内容；下载/恢复/删除仍由
 * `canOperateBackup` + 后端 `require_admin` 双重把关。
 */
const fullStubs = {
  ...rowStubs,
  'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
}

describe('R36：创建备份对普通用户开放', () => {
  it('user 角色：canCreateBackup=true 且 canOperateBackup=false', async () => {
    getUserMock.mockReturnValue({ role: 'user', is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canCreateBackup).toBe(true)
    expect((w.vm as any).canOperateBackup).toBe(false)
    w.unmount()
  })

  it('admin / super_admin / is_superuser 均 canCreateBackup=true', async () => {
    for (const user of [
      { role: 'admin', is_superuser: false },
      { role: 'super_admin', is_superuser: false },
      { role: 'user', is_superuser: true },
    ]) {
      getUserMock.mockReturnValue(user)
      const w = mountComp()
      await flushPromises()
      expect((w.vm as any).canCreateBackup).toBe(true)
      w.unmount()
    }
  })

  it('viewer 角色：canCreateBackup=false（只读角色不产生写副作用）', async () => {
    getUserMock.mockReturnValue({ role: 'viewer', is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canCreateBackup).toBe(false)
    w.unmount()
  })

  it('无 role 且非超管：canCreateBackup=false（role || "" 兜底）', async () => {
    getUserMock.mockReturnValue({ is_superuser: false })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canCreateBackup).toBe(false)
    w.unmount()
  })

  it('getUser 抛错：canCreateBackup=true（后端权限兜底）', async () => {
    getUserMock.mockImplementation(() => {
      throw new Error('storage corrupted')
    })
    const w = mountComp()
    await flushPromises()
    expect((w.vm as any).canCreateBackup).toBe(true)
    w.unmount()
  })

  it('user 页面：有「创建备份」，无下载/恢复/删除，且不显示只读标记', async () => {
    getUserMock.mockReturnValue({ role: 'user', is_superuser: false })
    const w = mountComp(fullStubs)
    await flushPromises()

    const texts = w.findAll('.el-button-stub').map((b: any) => b.text().trim())
    expect(texts).toContain('创建备份')
    expect(texts).not.toContain('导入备份包')
    expect(texts).not.toContain('下载')
    expect(texts).not.toContain('恢复')
    expect(texts).not.toContain('删除')
    expect(w.find('.readonly-hint').exists()).toBe(true)
    expect(w.find('.el-tag-stub').text()).not.toContain('只读模式')
    w.unmount()
  })

  it('viewer 页面：无「创建备份」，显示只读标记', async () => {
    getUserMock.mockReturnValue({ role: 'viewer', is_superuser: false })
    const w = mountComp(fullStubs)
    await flushPromises()

    const texts = w.findAll('.el-button-stub').map((b: any) => b.text().trim())
    expect(texts).not.toContain('创建备份')
    expect(texts).not.toContain('导入备份包')
    expect(w.find('.el-tag-stub').text()).toContain('只读模式')
    w.unmount()
  })
})
