<template>
  <div class="anomaly-container">
    <el-page-header title="返回" @back="pushSafe('/funds')">
      <template #content><span class="page-title">经费异常监控</span></template>
    </el-page-header>

    <el-card class="mt-4" shadow="never">
      <div class="toolbar">
        <div class="filters">
          <el-select
            v-model="filters.severity"
            placeholder="严重程度"
            clearable
            size="default"
            style="width: 120px"
            @change="loadData"
          >
            <el-option label="提示" value="info" />
            <el-option label="警告" value="warning" />
            <el-option label="严重" value="danger" />
          </el-select>
          <el-select
            v-model="filters.anomaly_type"
            placeholder="异常类型"
            clearable
            size="default"
            style="width: 140px"
            @change="loadData"
          >
            <el-option label="超支" value="overspend" />
            <el-option label="偏差" value="deviation" />
            <el-option label="资金闲置" value="idle" />
            <el-option label="重复支付" value="duplicate" />
            <el-option label="缺失凭证" value="missing_voucher" />
          </el-select>
          <el-select
            v-model="filters.resolved"
            placeholder="处理状态"
            clearable
            size="default"
            style="width: 120px"
            @change="loadData"
          >
            <el-option label="未处理" :value="0" />
            <el-option label="已处理" :value="1" />
          </el-select>
        </div>
      </div>

      <el-table v-loading="loading" :data="anomalies" size="default" class="mt-3">
        <el-table-column prop="anomaly_type_label" label="异常类型" width="120" />
        <el-table-column label="严重程度" width="100">
          <template #default="{ row }">
            <el-tag
              :type="
                row.severity === 'danger'
                  ? 'danger'
                  : row.severity === 'warning'
                    ? 'warning'
                    : 'info'
              "
              size="small"
            >
              {{ row.severity_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="description"
          label="异常描述"
          min-width="300"
          show-overflow-tooltip
        />
        <el-table-column prop="detected_at" label="检测时间" width="160">
          <template #default="{ row }">{{
            row.detected_at?.slice(0, 19).replace('T', ' ')
          }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.resolved ? 'success' : 'danger'" size="small">
              {{ row.resolved ? '已处理' : '未处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resolved_by" label="处理人" width="100" />
        <el-table-column prop="resolution" label="处理说明" width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.resolved" size="small" type="primary" @click="openResolve(row)"
              >处理</el-button
            >
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        class="mt-3"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        @current-change="loadData"
      />
    </el-card>

    <!-- 处理对话框 -->
    <el-dialog v-model="resolveDialogVisible" title="处理异常" :width="DIALOG_SM">
      <p class="anomaly-desc">{{ currentAnomaly?.description }}</p>
      <el-input v-model="resolution" type="textarea" :rows="3" placeholder="请输入处理说明" />
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleResolve">确认处理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fundLifecycleApi } from '@/api/fundLifecycle'
import { safeRouteParam, useRouterSafe } from '@/composables/useRouterSafe'

const { pushSafe } = useRouterSafe()
const route = useRoute()
const projectId = route.query.project_id ? safeRouteParam(route.query.project_id) : undefined

const loading = ref(false)
const anomalies = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filters = reactive({
  severity: '',
  anomaly_type: '',
  resolved: undefined as number | undefined,
})
const resolveDialogVisible = ref(false)
const currentAnomaly = ref<any>(null)
const resolution = ref('')

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize,
    }
    if (projectId) params.project_id = projectId
    if (filters.severity) params.severity = filters.severity
    if (filters.anomaly_type) params.anomaly_type = filters.anomaly_type
    if (filters.resolved !== undefined) params.resolved = filters.resolved === 1
    const data = await fundLifecycleApi.listAnomalies(params)
    anomalies.value = data.items || []
    total.value = data.total || 0
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function openResolve(row: any) {
  currentAnomaly.value = row
  resolution.value = ''
  resolveDialogVisible.value = true
}

async function handleResolve() {
  if (!resolution.value.trim()) {
    ElMessage.warning('请输入处理说明')
    return
  }
  loading.value = true
  try {
    await fundLifecycleApi.resolveAnomaly(currentAnomaly.value.id, resolution.value)
    ElMessage.success('已标记为已处理')
    resolveDialogVisible.value = false
    page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '处理失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.anomaly-container {
  padding: 20px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filters {
  display: flex;
  gap: 8px;
}
.mt-3 {
  margin-top: 12px;
}
.mt-4 {
  margin-top: 16px;
}
.anomaly-desc {
  margin-bottom: 12px;
  color: var(--color-text-regular);
}
.page-title {
  font-size: 18px;
  font-weight: 600;
}
</style>
