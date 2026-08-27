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

  it('loadScheduleConfig 从后端读取真实配置（cron 解析为友好模型）', async () => {
    ;(get as any).mockResolvedValue({
      data: { data: { enabled: true, keepCount: 7, schedule: '0 2 * * *' } },
    })
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await loadScheduleConfig()
    expect(get).toHaveBeenCalledWith('/system/backup/schedule')
    expect(scheduleConfig.value.enabled).toBe(true)
    expect(scheduleConfig.value.retentionCount).toBe(7)
    // cron "0 2 * * *" 解析 → 每日 02:00
    expect(scheduleConfig.value.frequency).toBe('daily')
    expect(scheduleConfig.value.backupTime).toBe('02:00')
  })

  it('weekly cron 表达式解析为 weekly 频率', async () => {
    ;(get as any).mockResolvedValue({
      data: { data: { enabled: false, keepCount: 3, schedule: '30 3 * * 1' } },
    })
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await loadScheduleConfig()
    expect(scheduleConfig.value.frequency).toBe('weekly')
    expect(scheduleConfig.value.backupTime).toBe('03:30')
  })

  it('schedule 缺失时回退默认 daily 02:00', async () => {
    ;(get as any).mockResolvedValue({ data: { data: { enabled: false } } })
    const { scheduleConfig, loadScheduleConfig } = useBackupSchedule()
    await loadScheduleConfig()
    expect(scheduleConfig.value.frequency).toBe('daily')
    expect(scheduleConfig.value.backupTime).toBe('02:00')
  })

  it('saveSchedule 写入 cron + keep_count，并回读保持一致', async () => {
    ;(put as any).mockResolvedValue({ data: { success: true } })
    ;(get as any).mockResolvedValue({
      data: { data: { enabled: false, keepCount: 3, schedule: '0 2 * * *' } },
    })
    const { scheduleConfig, saveSchedule } = useBackupSchedule()
    scheduleConfig.value.enabled = false
    scheduleConfig.value.retentionCount = 3

    await saveSchedule()

    // PUT 携带后端契约字段：cron 字符串 + snake_case keep_count
    expect(put).toHaveBeenCalledWith('/system/backup/schedule', {
      enabled: false,
      keep_count: 3,
      schedule: '00 02 * * *',
    })
    // 保存后必须回读 GET，保证前端与后端一致
    expect(get).toHaveBeenCalled()
    expect(scheduleConfig.value.enabled).toBe(false)
    expect(scheduleConfig.value.retentionCount).toBe(3)
    expect(ElMessage.success).toHaveBeenCalled()
  })
})
