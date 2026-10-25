/**
 * 介质同步状态（2026-10-25 / ④ 顶栏同步状态胶囊）
 *
 * ## 为什么
 * 本系统是**离线 + 介质传输**：用户最关心的问题不是"服务器通不通"，而是
 * "我这份数据多久没跟上级/下级对过了"。这个信息原来埋在系统管理里，没人看。
 * 胶囊把"最近一次同步"提到顶栏常驻，并在超过阈值时变色提醒。
 *
 * ## 设计取舍
 * - 只读 `/data-sync/logs` 最近若干条，**不新增后端接口**（离线单机不该为了一个角标加表）；
 * - 时间以 `created_at` 为准，缺字段的脏记录直接跳过（不让一条脏数据把状态算成"从未同步"）；
 * - 阈值：<1 天=正常、<7 天=提醒、≥7 天=过期；阈值常量对外导出，便于测试与后续调整；
 * - 接口失败**不弹错**（顶栏组件常驻，弹错会污染每个页面），只把胶囊置为"未知"态，
 *   抽屉里展示原因 —— 现场断网/后端未起时顶栏不该变成报错机器。
 */
import { computed, ref } from 'vue'

import { getSyncLogs, type SyncLog } from '@/api/dataSync'

/** 超过多少天没同步算"过期"（提醒用户尽快对账）。 */
export const SYNC_STALE_DAYS = 7

export type SyncLevel = 'ok' | 'warn' | 'stale' | 'unknown'

export interface SyncSummary {
  lastAction: string | null
  lastAt: number | null
  relativeLabel: string
  level: SyncLevel
}

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/** 相对时间文案（纯函数，便于测试）。 */
export function formatRelative(now: number, at: number | null): string {
  if (at === null) return '从未同步'
  const diff = Math.max(0, now - at)
  if (diff < MINUTE) return '刚刚'
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)} 分钟前`
  if (diff < DAY) return `${Math.floor(diff / HOUR)} 小时前`
  return `${Math.floor(diff / DAY)} 天前`
}

/** 新鲜度分级（纯函数）。 */
export function computeLevel(
  now: number,
  at: number | null,
  staleDays: number = SYNC_STALE_DAYS
): SyncLevel {
  if (at === null) return 'unknown'
  const days = (now - at) / DAY
  if (days < 1) return 'ok'
  if (days < staleDays) return 'warn'
  return 'stale'
}

/** 取最近一条日志（`created_at` 不可解析的脏记录跳过）。 */
export function pickLatest(logs: SyncLog[]): SyncLog | null {
  let best: SyncLog | null = null
  let bestAt = -Infinity
  for (const log of logs) {
    const at = Date.parse(log?.created_at ?? '')
    if (Number.isNaN(at)) continue
    if (at > bestAt) {
      bestAt = at
      best = log
    }
  }
  return best
}

/** 汇总成顶栏需要的四个字段（纯函数）。 */
export function summarize(logs: SyncLog[], now: number = Date.now()): SyncSummary {
  const latest = pickLatest(logs)
  const lastAt = latest ? Date.parse(latest.created_at) : null
  return {
    lastAction: latest?.action ?? null,
    lastAt,
    relativeLabel: formatRelative(now, lastAt),
    level: computeLevel(now, lastAt),
  }
}

/** 后端 `get()` 已解包，但列表既可能是数组也可能是 `{items|list|data}`，统一一下。 */
function extractLogs(payload: unknown): SyncLog[] {
  if (Array.isArray(payload)) return payload as SyncLog[]
  if (payload && typeof payload === 'object') {
    const box = payload as Record<string, unknown>
    for (const key of ['items', 'list', 'data', 'records']) {
      if (Array.isArray(box[key])) return box[key] as SyncLog[]
    }
  }
  return []
}

export function useSyncStatus(options: { pageSize?: number; now?: () => number } = {}) {
  const pageSize = options.pageSize ?? 5
  const now = options.now ?? Date.now

  const logs = ref<SyncLog[]>([])
  const loading = ref(false)
  const error = ref('')
  const drawerVisible = ref(false)
  const summary = computed(() => summarize(logs.value, now()))

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const payload = await getSyncLogs({ page: 1, page_size: pageSize })
      logs.value = extractLogs(payload)
    } catch (e) {
      // 顶栏常驻组件不弹错：置为未知态，原因放进抽屉
      logs.value = []
      error.value = e instanceof Error ? e.message : '同步日志加载失败'
    } finally {
      loading.value = false
    }
  }

  function openDrawer(): void {
    drawerVisible.value = true
    void refresh()
  }

  function closeDrawer(): void {
    drawerVisible.value = false
  }

  return { logs, loading, error, drawerVisible, summary, refresh, openDrawer, closeDrawer }
}
