import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBackupSchedule } from '@/composables/useBackupSchedule'

vi.mock('@/api/request', () => ({
  get: vi.fn(),
  put: vi.fn(),
}))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn() },
}))

import { get, put } from '@/api/request'
import { ElMessage } from 'element-plus'

describe('useBackupSchedule (T044 唯一真相源)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loadScheduleConfig 从后端读取真实配置', async () => {
    ;(get as any).mockResolvedValue({
      data: { data: { enabled: true, keepCount: 7, nextRun: '2026-08-01T02:00:00', schedule: '0 2 * * *' } },
    })
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await loadScheduleConfig()
    expect(get).toHaveBeenCalledWith('/system/backup/schedule')
    expect(scheduleConfig.value.enabled).toBe(true)
    expect(scheduleConfig.value.retentionCount).toBe(7)
    expect(scheduleConfig.value.nextRun).toBe('2026-08-01T02:00:00')
  })

  it('saveSchedule 写入后回读保持一致', async () => {
    ;(put as any).mockResolvedValue({ data: { success: true } })
    ;(get as any).mockResolvedValue({
      data: { data: { enabled: false, keepCount: 3, nextRun: null } },
    })
    const { scheduleConfig, saveSchedule } = useBackupSchedule()
    scheduleConfig.value.enabled = false
    scheduleConfig.value.retentionCount = 3

    await saveSchedule()

    expect(put).toHaveBeenCalledWith('/system/backup/schedule', {
      enabled: false,
      keep_count: 3,
    })
    // 保存后必须回读 GET，保证前端与后端一致
    expect(get).toHaveBeenCalled()
    expect(scheduleConfig.value.enabled).toBe(false)
    expect(scheduleConfig.value.retentionCount).toBe(3)
    expect(ElMessage.success).toHaveBeenCalled()
  })
})
