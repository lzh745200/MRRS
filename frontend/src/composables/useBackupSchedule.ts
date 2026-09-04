import { ref } from 'vue'
import { get, put } from '@/api/request'
import { ElMessage } from 'element-plus'

export interface ScheduleConfig {
  enabled: boolean
  frequency: 'daily' | 'weekly' | 'monthly'
  backupTime: string
  retentionCount: number
}

/**
 * 备份计划配置 composable。
 *
 * 后端调度为唯一真相源（见 ADR-0010）：loadScheduleConfig 从
 * GET /system/backup/schedule 读取真实配置；saveSchedule 写入后回读，
 * 保证前端与后端一致。
 */
/**
 * 后端以 cron 表达式存储调度（`schedule` 字段，如 "0 2 * * *"），并以
 * `keep_count` 控制保留份数（见 backend/app/api/backup.py:BackupScheduleUpdate）。
 * 前端以用户友好的 `frequency` / `backupTime` / `retentionCount` 呈现，
 * 因此读写时需做 cron ↔ 友好模型 的双向转换。
 */
type Frequency = 'daily' | 'weekly' | 'monthly'

function parseCron(schedule?: string | null): { frequency: Frequency; backupTime: string } {
  const fallback = { frequency: 'daily' as Frequency, backupTime: '02:00' }
  if (!schedule || typeof schedule !== 'string') return fallback
  const parts = schedule.trim().split(/\s+/)
  if (parts.length < 2) return fallback
  const [min, hour, dom, , dow] = parts
  const h = String(hour).padStart(2, '0')
  const m = String(min).padStart(2, '0')
  let frequency: Frequency = 'daily'
  if (dom && dom !== '*' && (!dow || dow === '*')) frequency = 'monthly'
  else if (dow && dow !== '*' && (!dom || dom === '*')) frequency = 'weekly'
  return { frequency, backupTime: `${h}:${m}` }
}

function toCron(frequency: Frequency, backupTime: string): string {
  // 小时位不给解构默认值：String.prototype.split 恒返回至少 1 个元素且元素必为
  // 字符串，故下标 0 永不为 undefined，原来的 `h = '2'` 是不可达死代码（任务#28 删除）。
  // 分钟位的 `m = '0'` 必须保留：backupTime 形如 '3'（无冒号）时 split 只得 ['3']，
  // m 为 undefined，该默认值真实生效（见 useBackupSchedule.test.ts「backupTime 无冒号」）。
  const [h, m = '0'] = (backupTime || '02:00').split(':')
  const hour = String(h).padStart(2, '0')
  const minute = String(m).padStart(2, '0')
  if (frequency === 'weekly') return `${minute} ${hour} * * 1`
  if (frequency === 'monthly') return `${minute} ${hour} 1 * *`
  return `${minute} ${hour} * * *`
}

export function useBackupSchedule() {
  const savingSchedule = ref(false)
  const scheduleConfig = ref<ScheduleConfig>({
    enabled: false,
    frequency: 'daily',
    backupTime: '02:00',
    retentionCount: 7,
  })

  async function loadScheduleConfig() {
    try {
      const res = await get('/system/backup/schedule')
      const data = res.data?.data ?? res.data ?? res
      if (data) {
        const parsed = parseCron(data.schedule)
        scheduleConfig.value = {
          enabled: data.enabled ?? false,
          // 兼容后端 cron 字段与测试/前端友好字段两种形态
          frequency: data.frequency ?? parsed.frequency,
          backupTime: data.backupTime ?? data.backup_time ?? parsed.backupTime,
          // 后端 GET /system/backup/schedule 返回驼峰 keepCount（见 backup.py:359）
          retentionCount:
            data.retentionCount ?? data.keepCount ?? data.retention_count ?? data.keep_count ?? 7,
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
        schedule: toCron(scheduleConfig.value.frequency, scheduleConfig.value.backupTime),
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
