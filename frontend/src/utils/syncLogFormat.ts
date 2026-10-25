/**
 * 同步日志展示格式化（2026-10-25 / ④）
 *
 * 抽成独立模块的原因：这些函数原本写在组件模板的插槽里（`formatTime(row.created_at)`），
 * 而 `el-table` 在单测里被 stub 后**插槽不执行** → 函数覆盖率永远到不了 100%（覆盖率黑洞）。
 * 移到 util 后既能被直接单测，也能让组件用 `rows` 计算属性渲染（计算属性会真实求值）。
 */
import type { SyncLog } from '@/api/dataSync'

const ACTION_TEXT: Record<string, string> = {
  import: '导入',
  export: '导出',
  sync: '同步',
  upload: '上传',
  download: '下载',
}

/** 动作码 → 中文（未知码原样返回，便于现场按码排查）。 */
export function actionLabel(action: string | null | undefined): string {
  if (!action) return '未知动作'
  return ACTION_TEXT[action] || action
}

/** ISO 时间 → 本地可读时间；不可解析返回 `—`（不显示 Invalid Date）。 */
export function formatLogTime(raw: string | null | undefined): string {
  const at = Date.parse(raw ?? '')
  return Number.isNaN(at) ? '—' : new Date(at).toLocaleString('zh-CN', { hour12: false })
}

export interface DrawerRow {
  time: string
  action: string
  status: string
  message: string
}

/** 抽屉表格行（组件直接用 `rows` 渲染，避免逻辑散落在模板插槽里）。 */
export function toDrawerRows(logs: SyncLog[]): DrawerRow[] {
  return logs.map((log) => ({
    time: formatLogTime(log?.created_at),
    action: actionLabel(log?.action),
    status: log?.status || '—',
    message: log?.message || '—',
  }))
}
