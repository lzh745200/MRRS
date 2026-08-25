<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="80%"
    :before-close="handleClose"
    @update:model-value="handleUpdateVisible"
  >
    <div ref="printContent" class="print-content">
      <div class="print-header">
        <h2>{{ title }}</h2>
        <div class="print-info">
          <p>打印时间: {{ printTime }}</p>
          <p>打印人: {{ printer }}</p>
        </div>
      </div>

      <el-table :data="data" border style="width: 100%" :show-header="true">
        <el-table-column
          v-for="column in columns"
          :key="column.key"
          :prop="column.key"
          :label="column.label"
          min-width="120"
        />
      </el-table>
    </div>

    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
      <el-button type="primary" @click="handlePrint">打印</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
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
const emit = defineEmits(['close', 'update:visible'])

const authStore = useAuthStore()
const printContent = ref<HTMLElement>()

const printTime = computed(() => {
  return new Date().toLocaleString('zh-CN')
})

const printer = computed(() => {
  return authStore.user?.username || '未知用户'
})

const handleUpdateVisible = (value: boolean) => {
  emit('update:visible', value)
  if (!value) {
    emit('close')
  }
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

const handlePrint = () => {
  if (!printContent.value) return

  // 使用隐藏 iframe 打印，兼容 Electron（window.open 被 setWindowOpenHandler 拦截返回 deny）
  const iframe = document.createElement('iframe')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  iframe.style.visibility = 'hidden'
  document.body.appendChild(iframe)

  // Escape title to prevent XSS
  const safeTitle = escapeHtml(props.title)

  const styles = `
    <style>
      body {
        font-family: 'Microsoft YaHei', Arial, sans-serif;
        margin: 20px;
        color: #000;
        font-size: 12px;
      }
      .print-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
      }
      .print-table th,
      .print-table td {
        border: 1px solid #000;
        padding: 6px 8px;
        text-align: left;
      }
      .print-table th {
        background-color: var(--color-bg-hover);
        font-weight: bold;
      }
      .print-header {
        text-align: center;
        margin-bottom: 20px;
        border-bottom: 2px solid #000;
        padding-bottom: 10px;
      }
      .print-header h2 {
        margin: 0 0 10px;
        font-size: 18px;
      }
      .print-info {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        color: var(--color-text-secondary);
      }
      @media print {
        body { margin: 0; }
        .no-print { display: none; }
      }
    </style>
  `

  const tableHtml = sanitizeHtml(printContent.value.innerHTML)

  const doc = iframe.contentWindow?.document || iframe.contentDocument
  if (!doc) {
    document.body.removeChild(iframe)
    return
  }

  doc.open()
  doc.write(`
    <html>
      <head>
        <title>${safeTitle}</title>
        ${styles}
      </head>
      <body>
        ${tableHtml}
      </body>
    </html>
  `)
  doc.close()

  // 等待 iframe 内容渲染后调用打印
  const win = iframe.contentWindow
  if (!win) {
    document.body.removeChild(iframe)
    return
  }

  const cleanup = () => {
    if (iframe.parentNode) document.body.removeChild(iframe)
  }

  // onafterprint 在打印对话框关闭后触发（包括取消）
  win.onafterprint = cleanup

  // 延迟调用 print 确保 DOM 已渲染
  setTimeout(() => {
    try {
      win.focus()
      win.print()
    } catch {
      cleanup()
    }
    // 兜底：5秒后自动清理（防止 onafterprint 不触发）
    setTimeout(cleanup, 5000)
  }, 100)
}
</script>

<style scoped>
.print-content {
  max-height: 60vh;
  overflow-y: auto;
}

.print-header {
  text-align: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e8e8e8;
}

.print-header h2 {
  margin: 0 0 8px;
  color: var(--color-text-primary);
}

.print-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-text-regular);
}

.print-info p {
  margin: 0;
}
</style>
