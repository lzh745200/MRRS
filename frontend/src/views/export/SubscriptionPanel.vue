<template>
  <el-card class="subscription-management">
    <div class="history-header">
      <h3 class="section-title">订阅管理</h3>
      <div>
        <el-button text type="primary" @click="loadSubscriptions">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="openSubscriptionDialog">
          <el-icon><Plus /></el-icon>
          新建订阅
        </el-button>
      </div>
    </div>
    <p class="section-desc">
      到期自动生成报表并保存到报表输出目录，站内消息通知；生成失败会逐条留痕，不影响其余订阅。
    </p>
    <el-table v-loading="loadingSubs" :data="subscriptions" stripe>
      <el-table-column prop="name" label="订阅名称" min-width="150" />
      <el-table-column label="频率" width="80">
        <template #default="{ row }">{{ freqLabel(row.frequency) }}</template>
      </el-table-column>
      <el-table-column label="发送时间" min-width="130">
        <template #default="{ row }">{{ freqDetail(row) }}</template>
      </el-table-column>
      <el-table-column label="上次生成" width="160">
        <template #default="{ row }">
          <span>{{
            row.last_sent_at ? String(row.last_sent_at).replace('T', ' ').slice(0, 19) : '从未'
          }}</span>
        </template>
      </el-table-column>
      <el-table-column label="下次生成" width="160">
        <template #default="{ row }">
          <span>{{
            row.next_send_at ? String(row.next_send_at).replace('T', ' ').slice(0, 19) : '—'
          }}</span>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="70">
        <template #default="{ row }">
          <el-switch :model-value="row.is_active" @change="handleToggleSub(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            type="primary"
            :disabled="!row.is_active"
            :loading="generatingId === row.id"
            @click="handleGenerateNow(row)"
          >
            立即生成
          </el-button>
          <el-button size="small" type="danger" @click="handleDeleteSub(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="subDialogVisible" title="新建报表订阅" width="520px">
      <el-form :model="subForm" label-width="90px">
        <el-form-item label="订阅名称" required>
          <el-input v-model="subForm.name" placeholder="如：每月帮扶村汇总" maxlength="100" />
        </el-form-item>
        <el-form-item label="报表类型" required>
          <el-select v-model="subForm.report_type" style="width: 100%">
            <el-option
              v-for="t in reportTypeOptions"
              :key="t.type"
              :label="t.name"
              :value="t.type"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="频率" required>
          <el-select v-model="subForm.frequency" style="width: 100%" @change="handleFreqChange">
            <el-option label="每天" value="daily" />
            <el-option label="每周" value="weekly" />
            <el-option label="每月" value="monthly" />
            <el-option label="每季度" value="quarterly" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="subForm.frequency === 'weekly'" label="星期">
          <el-select v-model="subForm.send_day" style="width: 100%">
            <el-option
              v-for="(label, idx) in ['周一', '周二', '周三', '周四', '周五', '周六', '周日']"
              :key="idx"
              :label="label"
              :value="idx + 1"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="subForm.frequency === 'monthly' || subForm.frequency === 'quarterly'"
          label="日期"
        >
          <el-select v-model="subForm.send_day" style="width: 100%">
            <el-option v-for="d in 31" :key="d" :label="`${d} 号`" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="发送时间">
          <el-time-select
            v-model="subForm.send_time"
            start="00:00"
            step="00:30"
            end="23:30"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="文件格式">
          <el-select v-model="subForm.format" style="width: 100%">
            <el-option label="Excel（.xlsx）" value="xlsx" />
            <el-option label="PDF" value="pdf" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingSub" @click="handleCreateSub"
          >创建订阅</el-button
        >
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logger } from '@/utils/logger'
import {
  listSubscriptions,
  createSubscription,
  toggleSubscription,
  deleteSubscription,
  generateSubscriptionNow,
} from '@/api/reportSubscription'

// 报表类型下拉与「报表导出中心」主表单保持同一组类型（避免第二份真源）
const reportTypeOptions = [
  { type: 'comprehensive', name: '综合数据报表' },
  { type: 'village_summary', name: '帮扶村汇总报表' },
  { type: 'fund_analysis', name: '资金使用分析报表' },
  { type: 'project_progress', name: '项目进度报表' },
  { type: 'school_statistics', name: '学校援建统计报表' },
  { type: 'annual_summary', name: '年度工作总结报表' },
]

const subscriptions = ref<any[]>([])
const loadingSubs = ref(false)
const generatingId = ref<number | null>(null)
const creatingSub = ref(false)
const subDialogVisible = ref(false)

const subForm = reactive({
  name: '',
  report_type: 'comprehensive',
  frequency: 'monthly' as 'daily' | 'weekly' | 'monthly' | 'quarterly',
  send_day: 1 as number | null,
  send_time: '08:00',
  format: 'xlsx',
})

const FREQ_LABELS: Record<string, string> = {
  daily: '每天',
  weekly: '每周',
  monthly: '每月',
  quarterly: '每季度',
}
const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

function freqLabel(f: string) {
  return FREQ_LABELS[f] || f
}

function freqDetail(row: any): string {
  const time = row.send_time || '08:00'
  if (row.frequency === 'daily') return `每天 ${time}`
  if (row.frequency === 'weekly') return `${WEEKDAY_LABELS[(row.send_day || 1) - 1]} ${time}`
  if (row.frequency === 'monthly') return `每月 ${row.send_day || 1} 号 ${time}`
  return `每季度 ${row.send_day || 1} 号 ${time}`
}

function openSubscriptionDialog() {
  subForm.name = ''
  subForm.report_type = 'comprehensive'
  subForm.frequency = 'monthly'
  subForm.send_day = 1
  subForm.send_time = '08:00'
  subForm.format = 'xlsx'
  subDialogVisible.value = true
}

function handleFreqChange() {
  // 切频次时重置 send_day 到该频次的默认档（weekly=周一1；monthly/quarterly=1 号）
  subForm.send_day = 1
}

async function loadSubscriptions() {
  loadingSubs.value = true
  try {
    const res = await listSubscriptions({ page: 1, page_size: 50 })
    const body = res?.data ?? res
    subscriptions.value = body?.items ?? []
  } catch (err: any) {
    logger.error('[SubscriptionPanel] 加载订阅列表失败', err)
    ElMessage.error(err?.userMessage || '加载订阅列表失败')
  } finally {
    loadingSubs.value = false
  }
}

async function handleCreateSub() {
  if (!subForm.name.trim()) {
    ElMessage.warning('请填写订阅名称')
    return
  }
  creatingSub.value = true
  try {
    await createSubscription({
      name: subForm.name.trim(),
      report_type: subForm.report_type,
      format: subForm.format,
      frequency: subForm.frequency,
      send_day: subForm.frequency === 'daily' ? null : subForm.send_day,
      send_time: subForm.send_time,
      output_format: subForm.format,
    })
    ElMessage.success('订阅创建成功，到期将自动生成并站内通知')
    subDialogVisible.value = false
    await loadSubscriptions()
  } catch (err: any) {
    ElMessage.error(err?.userMessage || err?.response?.data?.detail || '创建订阅失败')
  } finally {
    creatingSub.value = false
  }
}

async function handleToggleSub(row: any) {
  try {
    await toggleSubscription(row.id)
    ElMessage.success(row.is_active ? '订阅已禁用' : '订阅已启用')
    await loadSubscriptions()
  } catch (err: any) {
    ElMessage.error(err?.userMessage || '切换订阅状态失败')
  }
}

async function handleGenerateNow(row: any) {
  generatingId.value = row.id
  try {
    await generateSubscriptionNow(row.id)
    ElMessage.success(`「${row.name}」已生成，文件信息见站内消息`)
    await loadSubscriptions()
  } catch (err: any) {
    ElMessage.error(err?.userMessage || err?.response?.data?.detail || '生成失败')
  } finally {
    generatingId.value = null
  }
}

async function handleDeleteSub(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除订阅「${row.name}」？删除后不再生成报表。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteSubscription(row.id)
    ElMessage.success('订阅已删除')
    await loadSubscriptions()
  } catch (err: any) {
    ElMessage.error(err?.userMessage || '删除订阅失败')
  }
}

onMounted(() => {
  loadSubscriptions()
})
</script>

<style scoped lang="scss">
.subscription-management {
  margin-bottom: 20px;

  .section-desc {
    margin: 0 0 12px 0;
    color: var(--color-text-secondary);
    font-size: 14px;
  }

  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;

    > div {
      display: flex;
      gap: 8px;
    }
  }
}
</style>
