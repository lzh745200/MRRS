<template>
  <div class="health-check-page">
    <!-- 头部：体检单 -->
    <el-card class="header-card" shadow="never">
      <div class="header-inner">
        <div class="header-left">
          <div class="title-row">
            <span class="title-badge">
              <el-icon :size="22"><FirstAidKit /></el-icon>
            </span>
            <h2 class="page-title">系统体检</h2>
          </div>
          <p class="page-desc">
            一键检测数据库连接、磁盘空间、内存使用、备份状态、运行环境与安全配置，共 6
            项核心指标，快速掌握系统健康状态。
          </p>
          <div class="last-check">
            <el-icon :size="14"><Timer /></el-icon>
            <span>上次体检时间：{{ lastCheckTime || '尚未进行体检' }}</span>
          </div>
        </div>
        <div class="header-right">
          <el-button
            type="primary"
            size="large"
            class="start-btn"
            :loading="checking"
            :icon="FirstAidKit"
            @click="runCheck"
          >
            {{ checking ? '体检中…' : '开始体检' }}
          </el-button>
        </div>
      </div>
      <!-- 心电图装饰线 -->
      <div class="ecg-monitor" aria-hidden="true">
        <svg viewBox="0 0 260 60" preserveAspectRatio="none">
          <polyline
            class="ecg-line ecg-line--ghost"
            points="0,30 70,30 90,30 100,12 112,48 122,30 150,30 165,30 172,20 180,40 188,30 260,30"
          />
          <polyline
            class="ecg-line"
            points="0,30 70,30 90,30 100,12 112,48 122,30 150,30 165,30 172,20 180,40 188,30 260,30"
          />
        </svg>
      </div>
    </el-card>

    <!-- 空状态：尚未体检 -->
    <el-result
      v-if="!hasChecked"
      class="empty-result"
      icon="info"
      title="尚未进行系统体检"
      sub-title="点击「开始体检」按钮，系统将自动检测 6 个关键项目并生成健康评分"
    >
      <template #extra>
        <el-button type="primary" size="large" :icon="FirstAidKit" @click="runCheck">
          开始体检
        </el-button>
      </template>
    </el-result>

    <!-- 体检结果区 -->
    <template v-else>
      <!-- 总体评分 -->
      <el-card class="score-card reveal" shadow="never">
        <el-row :gutter="20" align="middle">
          <el-col :xs="24" :sm="7" :md="6">
            <div class="score-progress">
              <el-progress
                type="circle"
                :percentage="scorePercent"
                :color="scoreColor"
                :width="150"
                :stroke-width="11"
              >
                <template #default>
                  <div class="score-circle-text">
                    <span class="score-num">{{ passedCount }}<i>/6</i></span>
                    <span class="score-label">项通过</span>
                  </div>
                </template>
              </el-progress>
            </div>
          </el-col>
          <el-col :xs="24" :sm="17" :md="18">
            <div class="score-info">
              <div class="score-title">总体评分</div>
              <div class="score-tags">
                <el-tag type="success" effect="light">✅ 正常 {{ statusCounts.success }}</el-tag>
                <el-tag type="warning" effect="light">⚠️ 关注 {{ statusCounts.warning }}</el-tag>
                <el-tag type="danger" effect="light">❌ 异常 {{ statusCounts.error }}</el-tag>
                <el-tag v-if="pendingCount > 0" type="info" effect="light">
                  ⏳ 检测中 {{ pendingCount }}
                </el-tag>
              </div>
              <div class="score-verdict" :class="verdict.cls">{{ verdict.text }}</div>
            </div>
          </el-col>
        </el-row>
        <div class="score-actions">
          <el-button
            type="primary"
            plain
            :icon="Download"
            :disabled="checking || !hasChecked"
            @click="exportReport"
          >
            导出体检报告
          </el-button>
        </div>
      </el-card>

      <!-- 6 项检查明细 -->
      <el-row :gutter="20" class="check-grid">
        <el-col
          v-for="(item, index) in items"
          :key="item.key"
          :xs="24"
          :sm="12"
          :lg="8"
          class="check-col reveal"
          :style="{ animationDelay: `${index * 70}ms` }"
        >
          <el-card class="check-card" :class="`status-${item.status}`" shadow="never">
            <div class="check-top">
              <span class="check-icon">
                <el-icon v-if="item.status === 'running'" class="is-loading" :size="20">
                  <Loading />
                </el-icon>
                <template v-else>{{ STATUS_ICON[item.status] }}</template>
              </span>
              <div class="check-heading">
                <div class="check-title">{{ item.title }}</div>
                <div class="check-desc">{{ item.desc }}</div>
              </div>
            </div>
            <div class="check-detail" :class="`detail-${item.status}`">{{ item.detail }}</div>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { FirstAidKit, Timer, Download, Loading } from '@element-plus/icons-vue'
import { get } from '@/api/request'
import { chartColor } from '@/utils/chartColors'

// ── 类型定义 ──

type CheckStatus = 'pending' | 'running' | 'success' | 'warning' | 'error'

interface CheckItem {
  key: string
  title: string
  desc: string
  status: CheckStatus
  detail: string
}

const STATUS_ICON: Record<CheckStatus, string> = {
  pending: '⏳',
  running: '⏳',
  success: '✅',
  warning: '⚠️',
  error: '❌',
}

const LAST_CHECK_KEY = 'system-healthcheck:last-check'
/** 备份有效期：超过该天数视为过期（⚠️） */
const BACKUP_STALE_DAYS = 7

// ── 状态 ──

const checking = ref(false)
const hasChecked = ref(false)
const lastCheckTime = ref<string>(loadLastCheck())

const items = reactive<CheckItem[]>([
  {
    key: 'database',
    title: '数据库连接',
    desc: '检测后端服务与数据库是否可正常访问',
    status: 'pending',
    detail: '等待检测',
  },
  {
    key: 'disk',
    title: '磁盘空间',
    desc: '检测系统磁盘使用率，超过 80% 需要关注',
    status: 'pending',
    detail: '等待检测',
  },
  {
    key: 'memory',
    title: '内存使用',
    desc: '检测服务器内存占用情况',
    status: 'pending',
    detail: '等待检测',
  },
  {
    key: 'backup',
    title: '备份状态',
    desc: `检测最近一次数据备份是否及时（${BACKUP_STALE_DAYS} 天内）`,
    status: 'pending',
    detail: '等待检测',
  },
  {
    key: 'env',
    title: '运行环境',
    desc: '检测 Python / Node 版本及依赖包完整性',
    status: 'pending',
    detail: '等待检测',
  },
  {
    key: 'security',
    title: '安全配置',
    desc: '检测数据加密状态与安全响应头等配置',
    status: 'pending',
    detail: '等待检测',
  },
])

/** 磁盘/内存共用同一次快照请求，避免重复调用 */
let snapshotPromise: Promise<any> | null = null

// ── 计算属性 ──

const statusCounts = computed(() => ({
  success: items.filter((i) => i.status === 'success').length,
  warning: items.filter((i) => i.status === 'warning').length,
  error: items.filter((i) => i.status === 'error').length,
}))

const pendingCount = computed(
  () => items.filter((i) => i.status === 'pending' || i.status === 'running').length
)

/** 通过项 = 正常 + 需关注（⚠️ 算通过但附带提示） */
const passedCount = computed(() => statusCounts.value.success + statusCounts.value.warning)

const scorePercent = computed(() => Math.round((passedCount.value / items.length) * 100))

const scoreColor = computed(() => {
  if (checking.value) return '#2d6a4f'
  const p = scorePercent.value
  if (p >= 80) return chartColor('success')
  if (p >= 50) return chartColor('warning')
  return chartColor('danger')
})

const verdict = computed<{ text: string; cls: string }>(() => {
  if (checking.value) return { text: '体检进行中，请稍候…', cls: 'verdict-running' }
  const { warning, error } = statusCounts.value
  if (error === 0 && warning === 0)
    return { text: '系统状态良好，各项指标正常', cls: 'verdict-good' }
  if (error === 0) return { text: `基本正常，${warning} 项指标需关注`, cls: 'verdict-warn' }
  if (passedCount.value >= 4)
    return { text: `部分异常，建议尽快处理 ${error} 个异常项`, cls: 'verdict-warn' }
  return { text: '存在严重问题，请立即排查异常项目', cls: 'verdict-bad' }
})

// ── 工具函数 ──

function pad(n: number): string {
  return n.toString().padStart(2, '0')
}

function formatDateTime(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function formatUptime(sec?: number): string {
  if (!sec || sec <= 0) return '未知'
  const days = Math.floor(sec / 86400)
  const hours = Math.floor((sec % 86400) / 3600)
  const mins = Math.floor((sec % 3600) / 60)
  if (days > 0) return `${days} 天 ${hours} 小时`
  if (hours > 0) return `${hours} 小时 ${mins} 分钟`
  return `${mins} 分钟`
}

/**
 * 统一解包后端响应。
 * 后端存在两种格式：{code, data: payload} 包装 与 直接返回 payload，
 * 响应拦截器会将内层字段展开到顶层但保留 data 键，此处做防御性解包。
 */
function unwrap(res: any): any {
  return res?.data?.data ?? res?.data ?? res ?? {}
}

function markFailed(item: CheckItem, err: any): void {
  item.status = 'error'
  const msg =
    err?.response?.data?.detail || err?.response?.data?.message || err?.message || '未知错误'
  item.detail = `检测失败：${msg}`
}

function loadLastCheck(): string {
  try {
    return localStorage.getItem(LAST_CHECK_KEY) || ''
  } catch {
    return ''
  }
}

function persistLastCheck(value: string): void {
  try {
    localStorage.setItem(LAST_CHECK_KEY, value)
  } catch {
    // 存储不可用时静默忽略
  }
}

// ── 各项检查 ──

async function checkDatabase(item: CheckItem): Promise<void> {
  item.status = 'running'
  try {
    const data = unwrap(await get('/health'))
    item.status = 'success'
    item.detail = `已连接 · 服务正常，已运行 ${formatUptime(data.uptime_seconds)}`
  } catch (err: any) {
    markFailed(item, err)
  }
}

function fetchSnapshot(): Promise<any> {
  if (!snapshotPromise) {
    snapshotPromise = (async () => {
      const res = await get('/system/monitor/snapshot')
      return unwrap(res)
    })()
  }
  return snapshotPromise
}

async function checkDisk(item: CheckItem): Promise<void> {
  item.status = 'running'
  try {
    const s = await fetchSnapshot()
    const usage = Number(s.disk_usage ?? 0)
    item.detail = `使用率 ${usage.toFixed(1)}%（${s.disk_used_gb ?? '-'} GB / ${s.disk_total_gb ?? '-'} GB）`
    item.status = usage > 90 ? 'error' : usage >= 80 ? 'warning' : 'success'
  } catch (err: any) {
    markFailed(item, err)
  }
}

async function checkMemory(item: CheckItem): Promise<void> {
  item.status = 'running'
  try {
    const s = await fetchSnapshot()
    const usage = Number(s.memory_usage ?? 0)
    item.detail = `使用率 ${usage.toFixed(1)}%（${Math.round(Number(s.memory_used_mb ?? 0))} MB / ${Math.round(Number(s.memory_total_mb ?? 0))} MB）`
    item.status = usage > 90 ? 'error' : usage >= 80 ? 'warning' : 'success'
  } catch (err: any) {
    markFailed(item, err)
  }
}

async function checkBackup(item: CheckItem): Promise<void> {
  item.status = 'running'
  try {
    const data = unwrap(await get('/system/backup/stats'))
    const last = data.lastBackup ?? data.last_backup ?? null
    const total = Number(data.totalBackups ?? data.total_backups ?? 0)
    if (!last || total === 0) {
      item.status = 'error'
      item.detail = '从未执行过备份，数据安全存在风险'
      return
    }
    const timeStr = formatDateTime(new Date(last))
    const days = (Date.now() - new Date(last).getTime()) / 86400000
    if (days > BACKUP_STALE_DAYS) {
      item.status = 'warning'
      item.detail = `上次备份：${timeStr}（已超过 ${BACKUP_STALE_DAYS} 天），共 ${total} 份备份`
    } else {
      item.status = 'success'
      item.detail = `上次备份：${timeStr}（${Math.max(0, Math.floor(days))} 天前），共 ${total} 份备份`
    }
  } catch (err: any) {
    markFailed(item, err)
  }
}

async function checkEnv(item: CheckItem): Promise<void> {
  item.status = 'running'
  try {
    const data = unwrap(await get('/env/check'))
    const sys = data.system ?? {}
    const python = String(sys.python_version || '').split(' ')[0] || '未检测'
    const node = String(sys.node_version || data.node_version || '') || '未检测'
    const missing: string[] = Array.isArray(data.missing_packages) ? data.missing_packages : []
    item.detail =
      `Python ${python} · Node ${node} · ` +
      (missing.length > 0 ? `缺失依赖 ${missing.length} 个：${missing.join('、')}` : '依赖完整')
    item.status = missing.length > 0 ? 'warning' : 'success'
  } catch (err: any) {
    markFailed(item, err)
  }
}

async function checkSecurity(item: CheckItem): Promise<void> {
  item.status = 'running'
  try {
    const data = unwrap(await get('/system/health'))
    const parts: string[] = []
    const encryption = data.encryption_enabled
    if (typeof encryption === 'boolean') {
      parts.push(`数据加密：${encryption ? '已启用' : '未启用'}`)
    }
    if (data.security_headers) {
      parts.push('安全响应头：已配置')
    }
    if (parts.length === 0) {
      parts.push(`安全状态：${data.status || 'healthy'}`)
    }
    parts.push(`服务已运行 ${formatUptime(data.uptime_seconds)}`)
    item.detail = parts.join(' · ')
    item.status = typeof encryption === 'boolean' && !encryption ? 'warning' : 'success'
  } catch (err: any) {
    markFailed(item, err)
  }
}

// ── 执行体检 ──

async function runCheck(): Promise<void> {
  if (checking.value) return
  checking.value = true
  hasChecked.value = true
  snapshotPromise = null
  items.forEach((item) => {
    item.status = 'pending'
    item.detail = '等待检测'
  })

  const runners: Array<(item: CheckItem) => Promise<void>> = [
    checkDatabase,
    checkDisk,
    checkMemory,
    checkBackup,
    checkEnv,
    checkSecurity,
  ]
  await Promise.allSettled(runners.map((fn, index) => fn(items[index])))

  checking.value = false
  lastCheckTime.value = formatDateTime(new Date())
  persistLastCheck(lastCheckTime.value)

  const { warning, error } = statusCounts.value
  if (error > 0) {
    ElMessage.warning(`体检完成：${passedCount.value}/6 项通过，${error} 项异常，请尽快处理`)
  } else if (warning > 0) {
    ElMessage.success(`体检完成：${passedCount.value}/6 项通过，${warning} 项需关注`)
  } else {
    ElMessage.success('体检完成：6/6 项全部通过，系统状态良好')
  }
}

// ── 导出体检报告 ──

function exportReport(): void {
  const now = new Date()
  const line = '═'.repeat(42)
  const thin = '─'.repeat(42)
  const lines: string[] = [
    line,
    '              系统体检报告',
    line,
    `体检时间：${formatDateTime(now)}`,
    `总体评分：${passedCount.value}/6 项通过（${scorePercent.value}%）`,
    `状态分布：✅ 正常 ${statusCounts.value.success} 项 · ⚠️ 关注 ${statusCounts.value.warning} 项 · ❌ 异常 ${statusCounts.value.error} 项`,
    thin,
  ]
  for (const item of items) {
    lines.push(`${STATUS_ICON[item.status]} ${item.title}`)
    lines.push(`   说明：${item.desc}`)
    lines.push(`   结果：${item.detail}`)
    lines.push('')
  }
  lines.push(thin)
  lines.push(`结论：${verdict.value.text}`)
  lines.push(line)

  const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `系统体检报告-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.txt`
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  // 延迟移除节点并释放对象 URL，避免内存泄漏
  setTimeout(() => {
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, 100)
  ElMessage.success('体检报告已导出')
}
</script>

<style scoped>
.health-check-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

/* ── 头部体检单 ── */
.header-card {
  position: relative;
  overflow: hidden;
  border: none;
  background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 70%, #40916c 100%);
}
.header-card :deep(.el-card__body) {
  position: relative;
  z-index: 1;
  padding: 28px 32px;
}
.header-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}
.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title-badge {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #1b4332;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
}
.page-title {
  font-size: 26px;
  font-weight: 700;
  color: #ffffff;
  margin: 0;
  letter-spacing: 2px;
}
.page-desc {
  font-size: 14px;
  color: #d8f3dc;
  margin: 12px 0 0;
  max-width: 620px;
  line-height: 1.7;
}
.last-check {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 14px;
  font-size: 13px;
  color: #b7e4c7;
}
.start-btn {
  min-width: 160px;
  height: 48px;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 4px;
  background: #ffffff;
  border-color: #ffffff;
  color: #1b4332;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.start-btn:hover,
.start-btn:focus {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28);
  background: #d8f3dc;
  border-color: #d8f3dc;
  color: #1b4332;
}

/* 心电图装饰线 */
.ecg-monitor {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 4px;
  height: 60px;
  opacity: 0.55;
  pointer-events: none;
}
.ecg-monitor svg {
  width: 100%;
  height: 100%;
}
.ecg-line {
  fill: none;
  stroke: #95d5b2;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-dasharray: 340;
  stroke-dashoffset: 340;
  animation: ecg-run 2.8s linear infinite;
}
.ecg-line--ghost {
  stroke: rgba(255, 255, 255, 0.14);
  stroke-dasharray: none;
  stroke-dashoffset: 0;
  animation: none;
}
@keyframes ecg-run {
  0% {
    stroke-dashoffset: 340;
  }
  55% {
    stroke-dashoffset: 0;
  }
  100% {
    stroke-dashoffset: -340;
  }
}

/* ── 空状态 ── */
.empty-result {
  background: #ffffff;
  border-radius: 8px;
  padding: 24px 0;
}

/* ── 总体评分卡 ── */
.score-card {
  border: none;
  border-radius: 8px;
}
.score-progress {
  display: flex;
  justify-content: center;
  padding: 4px 0;
}
.score-circle-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.2;
}
.score-num {
  font-size: 34px;
  font-weight: 700;
  color: #1b4332;
}
.score-num i {
  font-style: normal;
  font-size: 16px;
  font-weight: 500;
  color: var(--color-info);
}
.score-label {
  font-size: 13px;
  color: var(--color-info);
  margin-top: 2px;
}
.score-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.score-title {
  font-size: 18px;
  font-weight: 600;
  color: #1b4332;
}
.score-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.score-verdict {
  font-size: 15px;
  font-weight: 600;
}
.verdict-good {
  color: var(--color-success);
}
.verdict-warn {
  color: var(--color-warning);
}
.verdict-bad {
  color: var(--color-danger);
}
.verdict-running {
  color: #2d6a4f;
}
.score-actions {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed #e4e7ed;
  text-align: right;
}

/* ── 检查项卡片 ── */
.check-grid {
  row-gap: 20px;
}
.check-card {
  height: 100%;
  border: none;
  border-left: 4px solid #dcdfe6;
  border-radius: 8px;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.check-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 22px rgba(27, 67, 50, 0.12);
}
.check-card.status-success {
  border-left-color: var(--color-success);
}
.check-card.status-warning {
  border-left-color: var(--color-warning);
}
.check-card.status-error {
  border-left-color: var(--color-danger);
}
.check-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.check-icon {
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  background: #f5f7fa;
  color: var(--color-info);
}
.status-success .check-icon {
  background: var(--color-success-lightest);
}
.status-warning .check-icon {
  background: var(--color-warning-lightest);
}
.status-error .check-icon {
  background: var(--color-danger-lightest);
}
.check-heading {
  min-width: 0;
}
.check-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.check-desc {
  font-size: 12px;
  color: var(--color-info);
  margin-top: 4px;
  line-height: 1.5;
}
.check-detail {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #e4e7ed;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
  word-break: break-all;
}
.detail-success {
  color: #529b2e;
}
.detail-warning {
  color: #b88230;
}
.detail-error {
  color: #c45656;
}
.detail-pending,
.detail-running {
  color: var(--color-info);
}

/* ── 入场动画 ── */
.reveal {
  animation: fadeInUp 0.45s ease both;
}
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
