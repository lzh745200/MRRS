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
 *  xlsx 体积较大，改为按需动态导入，避免进入首屏静态依赖图。
 *  注：社区版 SheetJS 不支持写入单元格填充/字体，仅写入列宽（!cols）等结构属性。
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
  // 列宽（社区版可写入结构属性，提升打印/阅读体验）
  // 注：rows 由上面 `keys.map(...)` 构造，每行长度恒等于 headerRow 长度且元素均为字符串，
  // 故此处不需要 `?? ''` 兜底——那是个不可达分支（覆盖率门禁会把它算成未覆盖分支）。
  ws['!cols'] = headerRow.map((h, i) => {
    const maxLen = Math.max(
      String(h).length,
      ...rows.slice(0, 100).map((r) => String(r[i]).length),
      8
    )
    return { wch: Math.min(maxLen + 2, 40) }
  })

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

/** 导出为 PDF（简易实现：打开 A4 打印页面，含标题/生成时间/表格边框） */
function exportToPDF(
  title: string,
  data: Record<string, unknown>[],
  headers?: Record<string, string>
) {
  if (!data.length) return
  const keys = Object.keys(headers || data[0])
  const headerRow = keys.map((k) => headers?.[k] || k)
  const rows = data.map((row) => keys.map((k) => escapeHtml(String(row[k] ?? ''))))
  const style = `
    @page { size: A4 landscape; margin: 15mm; }
    body { font-family: "SimSun","Microsoft YaHei",sans-serif; color:#1e293b; }
    h1 { text-align:center; font-size:18pt; margin:0 0 4pt; }
    .meta { text-align:center; font-size:9pt; color:#64748b; margin-bottom:10pt; }
    table { border-collapse:collapse; width:100%; }
    th,td { border:1px solid #cbd5e1; padding:4pt 6pt; font-size:9pt; }
    th { background:#1b4332; color:#fff; font-weight:bold; text-align:center; }
    tbody tr:nth-child(even) td { background:#e8f0eb; }
  `
  const thead = `<tr>${headerRow.map((h) => `<th>${escapeHtml(h)}</th>`).join('')}</tr>`
  const tbody = rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')
  const html =
    `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>` +
    `<style>${style}</style></head><body>` +
    `<h1>${escapeHtml(title)}</h1>` +
    `<div class="meta">帮扶管理信息系统 · 生成时间：${new Date().toLocaleString('zh-CN')}</div>` +
    `<table><thead>${thead}</thead><tbody>${tbody}</tbody></table></body></html>`
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
