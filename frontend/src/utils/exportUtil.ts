/**
 * 导出工具模块
 * 支持 Excel/CSV/PDF 导出
 */

import { downloadBlob } from '@/api/request'

/** RFC 4180 兼容 CSV 转义 */
function escapeCSVField(val: unknown): string {
  const str = String(val ?? '')
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

/** 导出数据为 CSV */
function exportToCSV(
  data: Record<string, unknown>[],
  filename: string,
  headers?: Record<string, string>
) {
  if (!data.length) return

  const keys = Object.keys(headers || data[0])
  const headerRow = keys.map((k) => escapeCSVField(headers?.[k] || k)).join(',')
  const rows = data.map((row) => keys.map((k) => escapeCSVField(row[k])).join(','))

  const csv = [headerRow, ...rows].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  downloadBlob(blob, `${filename}.csv`)
}

/** 导出为 Excel（使用 xlsx 库生成真实 .xlsx 文件）
 *  xlsx 体积较大，改为按需动态导入，避免进入首屏静态依赖图
 */
async function exportToExcel(
  data: Record<string, unknown>[],
  filename: string,
  headers?: Record<string, string>
) {
  if (!data.length) return

  const XLSX = await import('@e965/xlsx')
  const keys = Object.keys(headers || data[0])
  const headerRow = keys.map((k) => headers?.[k] || k)
  const rows = data.map((row) => keys.map((k) => String(row[k] ?? '')))

  const ws = XLSX.utils.aoa_to_sheet([headerRow, ...rows])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '数据')
  const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' })
  const blob = new Blob([wbout], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  downloadBlob(blob, `${filename}.xlsx`)
}

/** HTML 实体编码（防 XSS） */
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

/** 导出为 PDF（简易实现：生成打印页面） */
function exportToPDF(
  title: string,
  data: Record<string, unknown>[],
  headers?: Record<string, string>
) {
  if (!data.length) return
  const keys = Object.keys(headers || data[0])
  const headerRow = keys.map((k) => headers?.[k] || k)
  const rows = data.map((row) => keys.map((k) => escapeHtml(String(row[k] ?? ''))))
  const html = `<html><head><title>${escapeHtml(title)}</title><style>table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background:#f2f2f2}</style></head><body><h1>${escapeHtml(title)}</h1><table><tr>${headerRow.map((h) => `<th>${escapeHtml(h)}</th>`).join('')}</tr>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')}</table></body></html>`
  const w = window.open('', '_blank')
  if (w) {
    w.document.write(html)
    w.document.close()
    w.print()
  }
}

/** 导出工具对象 */
export const exportUtil = {
  exportToCSV,
  exportToExcel,
  exportToPDF,
  escapeCSVField,
}

export default exportUtil
