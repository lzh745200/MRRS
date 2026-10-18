<template>
  <el-dialog
    v-model="visible"
    append-to-body
    :title="dialogTitle"
    :width="DIALOG_MD"
    class="report-output-dialog"
    @closed="onClosed"
  >
    <div class="report-output">
      <p class="report-output-meta">
        模板：<strong>{{ template?.name || '-' }}</strong>
        <span class="report-output-module">{{ moduleLabel }}</span>
      </p>

      <el-form label-width="90px" class="report-output-form">
        <el-form-item label="报表年度">
          <el-input v-model.number="year" type="number" placeholder="如 2025" class="year-input" />
        </el-form-item>
        <el-form-item v-if="mode === 'export'" label="导出格式">
          <el-select v-model="format" class="format-select">
            <el-option label="Excel（.xlsx）" value="xlsx" />
            <el-option label="CSV（.csv）" value="csv" />
            <el-option label="Word（.docx）" value="docx" />
            <el-option label="PDF（.pdf）" value="pdf" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- 导出模式 -->
      <div v-if="mode === 'export'" class="report-output-actions">
        <el-button type="primary" :loading="exporting" @click="handleExport">导出报表</el-button>
        <span class="report-output-tip">按模板已勾选字段组合生成文件；导出为服务端组装数据。</span>
      </div>

      <!-- 打印预览模式 -->
      <div v-else class="report-print-area">
        <div class="report-output-actions">
          <el-button :loading="printLoading" @click="loadPrintData">重新加载预览</el-button>
          <el-button type="primary" @click="handlePrint">打印</el-button>
          <span class="report-output-tip"
            >打印内容仅包含下方预览表格（浏览器打印对话框选择目标打印机）。</span
          >
        </div>

        <div v-if="printLoading" class="report-output-empty">预览数据加载中…</div>
        <table v-else-if="printRows.length" class="report-print-table">
          <thead>
            <tr>
              <th v-for="col in printColumns" :key="col">{{ columnLabel(col) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in printRows" :key="idx">
              <td v-for="col in printColumns" :key="col">{{ cellText(row, col) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="report-output-empty">暂无可打印数据（可调整年度后重新加载）</p>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 报表导出 / 打印预览对话框（W22 报表模板增强）
 *
 * - export 模式：选择年度 + 格式（Excel/CSV/Word/PDF）→ 调后端
 *   `POST /report-templates/{id}/export?format=&year=` 下载文件
 * - print 模式：调 `GET /report-templates/{id}/print-data?year` 取 JSON 预览，
 *   浏览器 `window.print()` 打印（配合全局 @media print 只保留预览表格）
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { get, apiRequest } from '@/api/request'
import { DIALOG_MD } from '@/config/dialog'

type OutputMode = 'export' | 'print'
type ExportFormat = 'xlsx' | 'csv' | 'docx' | 'pdf'

interface OutputTemplate {
  id?: number
  name?: string
  module?: string
}

interface PrintData {
  columns?: unknown
  rows?: unknown
  items?: unknown
  data?: unknown
}

const props = defineProps<{
  mode: OutputMode
  template: OutputTemplate | null
}>()

const visible = defineModel<boolean>({ default: false })

const currentYear = new Date().getFullYear()
const year = ref<number>(currentYear)
const format = ref<ExportFormat>('xlsx')
const exporting = ref(false)
const printLoading = ref(false)
const printData = ref<PrintData | null>(null)

const dialogTitle = computed(() => (props.mode === 'export' ? '导出报表数据' : '报表打印预览'))
const moduleLabel = computed(() => {
  const map: Record<string, string> = {
    village: '帮扶村',
    school: '帮扶学校',
    fund: '经费管理',
    project: '帮扶项目',
    rural_work: '乡村工作',
    comprehensive: '综合报表',
  }
  return (props.template?.module && map[props.template.module]) || props.template?.module || '-'
})

/** 预览列：优先后端 columns（字符串或 {key,label}），否则取首行字段 */
const printColumns = computed<string[]>(() => {
  const data = printData.value
  if (!data) return []
  const rawColumns = Array.isArray(data.columns) ? data.columns : []
  if (rawColumns.length) {
    return rawColumns.map((col: any) => (typeof col === 'string' ? col : String(col.key ?? col)))
  }
  const rows = printRows.value
  return rows.length ? Object.keys(rows[0]) : []
})

const printRows = computed<Array<Record<string, any>>>(() => {
  const data = printData.value
  if (!data) return []
  const candidate = [data.rows, data.items, data.data].find((value) => Array.isArray(value))
  return (candidate as Array<Record<string, any>> | undefined) ?? []
})

/** 列中文名（后端 columns 传 {key,label} 时使用 label） */
function columnLabel(key: string): string {
  const data = printData.value
  const rawColumns = data && Array.isArray(data.columns) ? data.columns : []
  const matched: any = rawColumns.find(
    (col: any) => col && typeof col === 'object' && col.key === key
  )
  return matched ? String(matched.label ?? key) : key
}

/** 单元格文本（空值显示 -） */
function cellText(row: Record<string, any>, col: string): string {
  const value = row?.[col]
  return value === null || value === undefined || value === '' ? '-' : String(value)
}

/** 打开时重置年度/格式/预览数据；打印模式自动拉取预览（immediate 覆盖挂载时即打开的场景） */
watch(
  visible,
  (open) => {
    if (open) {
      year.value = currentYear
      format.value = 'xlsx'
      printData.value = null
      if (props.mode === 'print') void loadPrintData()
    }
  },
  { immediate: true }
)

function onClosed(): void {
  printData.value = null
}

/** 浏览器下载 Blob（服务端导出文件） */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

/** 后端导出：POST 按模板字段组合生成文件并下载 */
async function handleExport(): Promise<void> {
  const id = props.template?.id
  if (!id) {
    ElMessage.warning('模板信息缺失，无法导出')
    return
  }
  if (!year.value) {
    ElMessage.warning('请输入报表年度')
    return
  }
  exporting.value = true
  try {
    const ext = format.value
    const blob: any = await apiRequest({
      method: 'POST',
      url: `/report-templates/${id}/export`,
      params: { format: ext, year: Number(year.value) },
      responseType: 'blob',
    })
    const filename = `${props.template?.name || '报表'}_${year.value}.${ext}`
    downloadBlob(blob instanceof Blob ? blob : new Blob([blob]), filename)
    ElMessage.success(`已导出 ${filename}`)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

/** 规整打印预览响应（兼容 {data} 信封与 rows/items/data 三种行字段） */
function normalizePrintData(res: any): PrintData {
  const data = res?.data ?? res ?? {}
  return data as PrintData
}

/** 拉取打印预览数据 */
async function loadPrintData(): Promise<void> {
  const id = props.template?.id
  if (!id) {
    ElMessage.warning('模板信息缺失，无法预览')
    return
  }
  printLoading.value = true
  try {
    const res = await get(`/report-templates/${id}/print-data`, { year: Number(year.value) })
    printData.value = normalizePrintData(res)
  } catch (error: any) {
    printData.value = null
    ElMessage.error(error?.response?.data?.detail || '预览数据加载失败')
  } finally {
    printLoading.value = false
  }
}

/** 浏览器打印（打印样式见文件末尾非 scoped @media print） */
function handlePrint(): void {
  if (printRows.value.length === 0) {
    ElMessage.warning('暂无可打印数据')
    return
  }
  window.print()
}
</script>

<style scoped>
.report-output {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.report-output-meta {
  margin: 0;
  font-size: 14px;
  color: var(--color-text-regular);
}

.report-output-module {
  margin-left: 8px;
  font-size: 12px;
  color: var(--color-text-placeholder);
}

.report-output-form {
  max-width: 420px;
}

.year-input {
  width: 180px;
}

.format-select {
  width: 220px;
}

.report-output-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.report-output-tip {
  font-size: 12px;
  color: var(--color-text-placeholder);
}

.report-output-empty {
  padding: 24px 0;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-placeholder);
}

.report-print-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.report-print-table th,
.report-print-table td {
  padding: 7px 10px;
  border: 1px solid var(--color-border-light);
  text-align: left;
  color: var(--color-text-regular);
}

.report-print-table th {
  background: var(--color-border-extra-light);
  color: var(--color-text-secondary);
  font-weight: 600;
}
</style>

<!-- 打印样式：仅保留预览表格（其余内容隐藏），供 window.print() 使用 -->
<style>
@media print {
  body * {
    visibility: hidden;
  }

  .report-print-area,
  .report-print-area * {
    visibility: visible;
  }

  .report-print-area {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
  }

  .report-print-area .report-output-actions {
    display: none;
  }
}
</style>
