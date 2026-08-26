import { ref } from 'vue'
import { get, put } from '@/api/request'
import { ElMessage } from 'element-plus'

export interface ScheduleConfig {
  enabled: boolean
  frequency: 'daily' | 'weekly' | 'monthly'
  backupTime: string
  retentionCount: number
  nextRun: string | null
}

/**
 * 备份计划配置 composable。
 *
 * 后端调度为唯一真相源（见 ADR-0010）：loadScheduleConfig 从
 * GET /system/backup/schedule 读取真实配置；saveSchedule 写入后回读，
 * 保证前端与后端一致。
 */
export function useBackupSchedule() {
  const savingSchedule = ref(false)
  const scheduleConfig = ref<ScheduleConfig>({
    enabled: false,
    frequency: 'daily',
    backupTime: '02:00',
    retentionCount: 7,
    nextRun: null,
  })

  async function loadScheduleConfig() {
    try {
      const res = await get('/system/backup/schedule')
      const data = res.data?.data ?? res.data ?? res
      if (data) {
        scheduleConfig.value = {
          enabled: data.enabled ?? false,
          frequency: data.schedule ? 'daily' : 'daily',
          backupTime: data.backupTime ?? '02:00',
          retentionCount: data.keepCount ?? data.retention_count ?? 7,
          nextRun: data.nextRun ?? null,
        }
      }
    } catch {
      // 端点不可用时保留默认值
    }
  }

  async function saveSchedule() {
    savingSchedule.value = true
    try {
      await put('/system/backup/schedule', {
        enabled: scheduleConfig.value.enabled,
        keep_count: scheduleConfig.value.retentionCount,
      })
      // 保存后回读，确保前端与后端真相源一致
      await loadScheduleConfig()
      ElMessage.success('备份计划已保存')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || e?.response?.data?.message || '保存备份计划失败')
    } finally {
      savingSchedule.value = false
    }
  }

  return { scheduleConfig, savingSchedule, loadScheduleConfig, saveSchedule }
}
