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
 *
 * 2026-09-30 深审修复（cron 静默失真）：
 * - 分钟/小时字段不是纯数字（步长表达式，如"每 5 分钟"）时不再 padStart 拼出
 *   "02:05/5" 这类假时间；标记 unsupported，用户未改动时**原样回写**原 cron。
 * - 保留并回写 dom/dow 原值：`0 2 15 * *` / `0 2 * * 3` 不再被静默改写成 1 号/周一。
 * - backupTime 非法（25:99、abc:xyz、02:99）时 fail-closed：提示且**不下发**请求。
 */
type Frequency = 'daily' | 'weekly' | 'monthly'

interface ParsedCron {
  frequency: Frequency
  backupTime: string
  /** 原始 cron 的"日"字段（monthly 维度），保存时回写 */
  monthDay?: string
  /** 原始 cron 的"星期"字段（weekly 维度），保存时回写 */
  weekday?: string
  /** cron 使用了界面无法表达的字段（步长/区间表达式）：保存时原样回写 */
  unsupported: boolean
  /** 原始 cron（unsupported 时原样回写，绝不静默改写用户计划） */
  raw?: string
}

/** 解析 cron 时刻字段为 [min,max] 内整数；非纯数字（步长/区间/空）→ null */
function toClockNumber(field: string | undefined, min: number, max: number): number | null {
  if (!field || !/^\d{1,2}$/.test(field)) return null
  const n = Number(field)
  return n >= min && n <= max ? n : null
}

function parseCron(schedule?: string | null): ParsedCron {
  const fallback: ParsedCron = { frequency: 'daily', backupTime: '02:00', unsupported: false }
  if (!schedule || typeof schedule !== 'string') return fallback
  const raw = schedule.trim()
  const parts = raw.split(/\s+/)
  if (parts.length < 2) return fallback
  const [min, hour, dom, , dow] = parts
  const minute = toClockNumber(min, 0, 59)
  const hourNum = toClockNumber(hour, 0, 23)
  if (minute === null || hourNum === null) {
    // 界面无法表达该 cron：展示默认值但标记 unsupported，保存时原样回写
    return { ...fallback, unsupported: true, raw }
  }
  let frequency: Frequency = 'daily'
  if (dom && dom !== '*' && (!dow || dow === '*')) frequency = 'monthly'
  else if (dow && dow !== '*' && (!dom || dom === '*')) frequency = 'weekly'
  return {
    frequency,
    backupTime: `${String(hourNum).padStart(2, '0')}:${String(minute).padStart(2, '0')}`,
    monthDay: dom,
    weekday: dow,
    unsupported: false,
    raw,
  }
}

/** 校验并归一化备份时刻 → "HH:mm"；非法返回 null（fail-closed，不拼非法 cron） */
function normalizeBackupTime(value: string): string | null {
  // 空值沿用历史兜底 02:00（见 useBackupSchedule.test.ts「backupTime 为空串」）
  const raw = (value || '02:00').trim()
  const [h, m = '0'] = raw.split(':')
  const hour = toClockNumber(h, 0, 23)
  const minute = toClockNumber(m, 0, 59)
  if (hour === null || minute === null) return null
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

function toCron(
  frequency: Frequency,
  backupTime: string,
  preserve?: Pick<ParsedCron, 'monthDay' | 'weekday'>
): string {
  // 小时位不给解构默认值：String.prototype.split 恒返回至少 1 个元素且元素必为
  // 字符串，故下标 0 永不为 undefined，原来的 `h = '2'` 是不可达死代码（任务#28 删除）。
  // 分钟位的 `m = '0'` 必须保留：backupTime 形如 '3'（无冒号）时 split 只得 ['3']，
  // m 为 undefined，该默认值真实生效（见 useBackupSchedule.test.ts「backupTime 无冒号」）。
  const [h, m = '0'] = (backupTime || '02:00').split(':')
  const hour = String(h).padStart(2, '0')
  const minute = String(m).padStart(2, '0')
  if (frequency === 'weekly') {
    // 保留后端原星期字段（非 * 时）；否则默认周一
    const dow = preserve?.weekday && preserve.weekday !== '*' ? preserve.weekday : '1'
    return `${minute} ${hour} * * ${dow}`
  }
  if (frequency === 'monthly') {
    const dom = preserve?.monthDay && preserve.monthDay !== '*' ? preserve.monthDay : '1'
    return `${minute} ${hour} ${dom} * *`
  }
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

  /** 最近一次 loadScheduleConfig 解析出的 cron 细节（保存时用于保留原字段/原样回写） */
  let lastParsed: ParsedCron | null = null

  async function loadScheduleConfig() {
    try {
      const res = await get('/system/backup/schedule')
      const data = res.data?.data ?? res.data ?? res
      if (data) {
        const parsed = parseCron(data.schedule)
        lastParsed = parsed
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

  /** 生成要下发的 cron：界面表达不了的原始 cron 且用户未改动 → 原样回写 */
  function resolveScheduleExpression(cfg: ScheduleConfig, backupTime: string): string {
    if (
      lastParsed?.unsupported &&
      lastParsed.raw &&
      lastParsed.frequency === cfg.frequency &&
      lastParsed.backupTime === backupTime
    ) {
      return lastParsed.raw
    }
    return toCron(cfg.frequency, backupTime, lastParsed ?? undefined)
  }

  async function saveSchedule() {
    const cfg = scheduleConfig.value
    const backupTime = normalizeBackupTime(cfg.backupTime)
    if (backupTime === null) {
      // 非法时刻绝不下发：原实现会把 '25:99' 拼成 '99 25 * * *' 存进后端调度
      ElMessage.error('备份时间格式不正确，请输入 HH:mm（小时 00-23，分钟 00-59）')
      return
    }
    savingSchedule.value = true
    try {
      await put('/system/backup/schedule', {
        enabled: cfg.enabled,
        schedule: resolveScheduleExpression(cfg, backupTime),
        keep_count: cfg.retentionCount,
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
