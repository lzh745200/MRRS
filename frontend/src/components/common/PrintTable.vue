<template>
  <div v-if="visible" class="print-overlay">
    <div class="print-container">
      <div class="print-header">
        <h2>{{ title }}</h2>
        <div class="print-actions">
          <el-button type="primary" @click="handlePrint">
            <el-icon><Printer /></el-icon>
            打印
          </el-button>
          <el-button @click="handleClose">关闭</el-button>
        </div>
      </div>

      <div ref="printContent" class="print-content">
        <table class="print-table">
          <thead>
            <tr>
              <th v-for="col in columns" :key="col.key">
                {{ col.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in data" :key="index">
              <td v-for="col in columns" :key="col.key">
                {{ getCellValue(item, col.key) }}
              </td>
            </tr>
          </tbody>
        </table>

        <div class="print-footer">
          <p>打印时间: {{ printTime }}</p>
          <p>共 {{ data.length }} 条记录</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { escapeHtml, sanitizeHtml } from '@/utils/sanitize'

interface Column {
  key: string
  label: string
}

interface Props {
  data: any[]
  columns: Column[]
  title: string
  visible: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['close'])

const printContent = ref<HTMLElement>()

const printTime = computed(() => {
  return new Date().toLocaleString('zh-CN')
})

const getCellValue = (item: any, key: string) => {
  const keys = key.split('.')
  let value = item
  for (const k of keys) {
    if (value && typeof value === 'object') {
      value = value[k]
    } else {
      return ''
    }
  }
  return value || ''
}

const handlePrint = () => {
  /* c8 ignore next */ // printContent 由模板 ref 绑定, visible 时恒存在
  if (!printContent.value) return

  const printWindow = window.open('', '_blank')
  if (!printWindow) return

  // Escape title to prevent XSS
  const safeTitle = escapeHtml(props.title)

  const styles = `
    <style>
      body {
        font-family: 'Microsoft YaHei', Arial, sans-serif;
        margin: 20px;
        color: var(--color-black);
      }
      .print-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
      }
      .print-table th,
      .print-table td {
        border: 1px solid var(--color-black);
        padding: 8px 12px;
        text-align: left;
        font-size: 12px;
      }
      .print-table th {
        background-color: var(--color-bg-hover);
        font-weight: bold;
      }
      .print-header {
        text-align: center;
        margin-bottom: 20px;
        border-bottom: 2px solid var(--color-black);
        padding-bottom: 10px;
      }
      .print-header h2 {
        margin: 0;
        font-size: 18px;
      }
      .print-footer {
        text-align: right;
        margin-top: 20px;
        font-size: 12px;
        color: var(--color-text-secondary);
      }
      @media print {
        body { margin: 0; }
        .print-actions { display: none; }
      }
    </style>
  `

  const content = `
    <div class="print-header">
      <h2>${safeTitle}</h2>
    </div>
    ${sanitizeHtml(printContent.value.innerHTML)}
  `

  printWindow.document.write(`
    <html>
      <head>
        <title>${safeTitle}</title>
        ${styles}
      </head>
      <body>
        ${content}
        <script>
          window.onload = function() {
            window.print();
            window.onafterprint = function() {
              window.close();
            };
          };
        ${'<'}/script>
      </body>
    </html>
  `)
  printWindow.document.close()
}

const handleClose = () => {
  emit('close')
}
</script>

<style scoped>
.print-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.print-container {
  background: white;
  width: 90%;
  height: 90%;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.print-header {
  padding: 20px;
  border-bottom: 1px solid var(--color-border-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.print-header h2 {
  margin: 0;
  color: var(--color-text-primary);
}

.print-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.print-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.print-table th,
.print-table td {
  border: 1px solid var(--color-border-light);
  padding: 8px 12px;
  text-align: left;
}

.print-table th {
  background-color: var(--color-bg-hover);
  font-weight: 600;
  color: var(--color-text-primary);
}

.print-table tr:nth-child(even) {
  background-color: #fafafa;
}

.print-footer {
  margin-top: 20px;
  text-align: right;
  color: var(--color-info);
  font-size: 12px;
}

.print-footer p {
  margin: 4px 0;
}
</style>
