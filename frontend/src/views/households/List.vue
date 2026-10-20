<template>
  <div class="list-page household-list-page">
    <PageHeader title="一户一档" subtitle="按户建档、风险预警、走访挂户与台账导出">
      <div class="header-actions">
        <el-button class="btn-alerts" @click="openAlerts">风险预警</el-button>
        <el-button class="btn-rollup" @click="openRollup">一键汇总回填</el-button>
        <el-button class="btn-export-xlsx" :loading="exporting" @click="handleExport('xlsx')">
          导出 Excel
        </el-button>
        <el-button class="btn-export-csv" :loading="exporting" @click="handleExport('csv')">
          导出 CSV
        </el-button>
        <el-button type="primary" class="btn-create" @click="openCreate">新建档案</el-button>
      </div>
    </PageHeader>

    <!-- 统计条：建档户数 / 当前页高风险 / 监测户 / 预警命中 -->
    <section class="stat-grid">
      <div v-for="card in statCards" :key="card.key" class="app-stat-card stat-card">
        <div class="stat-value num-cell">{{ card.value }}</div>
        <div class="stat-label">{{ card.label }}</div>
        <div class="stat-trend" :class="card.trendClass">{{ card.trend }}</div>
      </div>
    </section>

    <!-- 筛选区 -->
    <section class="app-card filter-card">
      <div class="filters">
        <el-select
          v-model="query.village_id"
          class="f-village"
          placeholder="帮扶村"
          clearable
          filterable
        >
          <el-option
            v-for="village in villageOptions"
            :key="village.id"
            :label="village.name"
            :value="village.id"
          />
        </el-select>
        <el-select v-model="query.risk_level" class="f-risk" placeholder="风险等级" clearable>
          <el-option
            v-for="option in RISK_LEVEL_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select v-model="query.household_type" class="f-type" placeholder="户类型" clearable>
          <el-option
            v-for="option in HOUSEHOLD_TYPE_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-input
          v-model="query.keyword"
          class="f-keyword"
          placeholder="户主姓名 / 户编号"
          clearable
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" class="btn-search" @click="handleSearch">
          <el-icon><Search /></el-icon>
          查询
        </el-button>
        <el-button class="btn-reset" @click="handleReset">
          <el-icon><Refresh /></el-icon>
          重置
        </el-button>
      </div>
      <p class="list-hint advanced-only">风险预警按户实时计算，可在详情页一键登记为风险记录。</p>
    </section>

    <!-- 台账表格 -->
    <section class="app-card table-card">
      <div class="card-header">
        <span class="card-title">建档台账</span>
        <span class="total-hint">共 {{ total }} 户</span>
      </div>

      <div v-if="loading" class="app-loading">数据加载中…</div>
      <div v-else-if="loadError" class="app-error">
        <span class="error-text">{{ loadError }}</span>
        <el-button type="primary" class="btn-retry" @click="loadData">重试</el-button>
      </div>
      <template v-else>
        <div v-if="items.length === 0" class="app-empty">暂无建档记录</div>
        <template v-else>
          <el-table border :data="items" class="household-table">
            <el-table-column prop="household_name" label="户主" min-width="100" />
            <el-table-column label="户编号" min-width="120">
              <template #default="{ row }">{{ row.household_code || '—' }}</template>
            </el-table-column>
            <el-table-column label="帮扶村" min-width="130">
              <template #default="{ row }">{{ row.village_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="户类型" width="100">
              <template #default="{ row }">
                <el-tag :type="typeTagType(row.household_type)" size="small">
                  {{ householdTypeLabel(row.household_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="风险等级" width="100">
              <template #default="{ row }">
                <el-tag :type="riskTagType(row.risk_level)" size="small">
                  {{ riskLevelLabel(row.risk_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="帮扶责任人" width="120">
              <template #default="{ row }">{{ formatHelperName(row.helper_name) }}</template>
            </el-table-column>
            <el-table-column label="成员数" width="90" align="right">
              <template #default="{ row }">
                <span class="num-cell">{{ row.member_count ?? 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="最近走访" width="120">
              <template #default="{ row }">{{ formatDate(row.last_visit_date) }}</template>
            </el-table-column>
            <el-table-column label="预警" min-width="150">
              <template #default="{ row }">
                <template v-if="alertsOf(row as HouseholdItem).length">
                  <el-tag
                    v-for="alert in alertsOf(row as HouseholdItem)"
                    :key="alert"
                    type="danger"
                    size="small"
                    class="alert-tag"
                  >
                    {{ alert }}
                  </el-tag>
                </template>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  class="btn-view"
                  @click="goDetail(row as HouseholdItem)"
                >
                  详情
                </el-button>
                <el-button
                  link
                  type="primary"
                  class="btn-edit"
                  @click="openEdit(row as HouseholdItem)"
                >
                  编辑
                </el-button>
                <el-dropdown
                  class="row-actions"
                  @command="handleRowCommand($event, row as HouseholdItem)"
                >
                  <el-button link type="danger" class="btn-more">更多</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="delete">删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            class="pager pagination-wrapper"
            background
            layout="total, sizes, prev, pager, next"
            :total="total"
            :current-page="query.page"
            :page-size="query.page_size"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </template>
      </template>
    </section>

    <!-- 新建 / 编辑抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="editingId === null ? '新建一户一档' : '编辑一户一档'"
      size="540px"
    >
      <el-form :model="form" label-width="110px" class="household-form">
        <el-form-item label="帮扶村" required>
          <el-select
            v-model="form.supported_village_id"
            class="form-village"
            filterable
            placeholder="请选择帮扶村"
          >
            <el-option
              v-for="village in villageOptions"
              :key="village.id"
              :label="village.name"
              :value="village.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="户编号">
          <el-input
            v-model="form.household_code"
            class="form-code"
            maxlength="64"
            placeholder="如：SC-001"
          />
        </el-form-item>
        <el-form-item label="户主姓名" required>
          <el-input v-model="form.household_name" class="form-name" maxlength="64" />
        </el-form-item>
        <el-form-item label="详细地址">
          <el-input v-model="form.address" class="form-address" maxlength="255" />
        </el-form-item>
        <el-form-item label="户类型">
          <el-select v-model="form.household_type" class="form-type">
            <el-option
              v-for="option in HOUSEHOLD_TYPE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="风险类型">
          <el-select v-model="form.risk_type" class="form-risk-type">
            <el-option
              v-for="option in RISK_TYPE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级">
          <el-select v-model="form.risk_level" class="form-risk-level">
            <el-option
              v-for="option in RISK_LEVEL_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="帮扶责任人">
          <el-input v-model="form.helper_name" class="form-helper" maxlength="64" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input
            v-model="form.helper_phone"
            class="form-phone"
            maxlength="64"
            placeholder="帮扶责任人电话"
          />
        </el-form-item>
        <el-form-item label="家庭年收入(元)">
          <el-input-number
            v-model="form.annual_income"
            class="form-income"
            :min="0"
            :precision="2"
          />
        </el-form-item>
        <el-form-item label="务工人数">
          <el-input-number
            v-model="form.migrant_workers"
            class="form-migrant"
            :min="0"
            :precision="0"
          />
        </el-form-item>
        <el-form-item label="大病">
          <el-switch v-model="form.has_serious_illness" class="form-illness" />
        </el-form-item>
        <el-form-item label="住房安全">
          <el-switch v-model="form.housing_safe" class="form-housing" />
        </el-form-item>
        <el-form-item label="最近走访">
          <el-date-picker
            v-model="form.last_visit_date"
            class="form-visit-date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
          />
        </el-form-item>
        <el-form-item label="监测备注">
          <el-input
            v-model="form.monitoring_note"
            class="form-note"
            type="textarea"
            :rows="3"
            maxlength="500"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button class="btn-drawer-cancel" @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" class="btn-drawer-save" :loading="saving" @click="handleSave">
          保存
        </el-button>
      </template>
    </el-drawer>

    <!-- 汇总回填 -->
    <el-dialog v-model="rollupVisible" title="一键汇总回填年度人口" width="460px">
      <el-form label-width="100px">
        <el-form-item label="帮扶村" required>
          <el-select
            v-model="rollupForm.village_id"
            class="rollup-village"
            filterable
            placeholder="请选择帮扶村"
          >
            <el-option
              v-for="village in villageOptions"
              :key="village.id"
              :label="village.name"
              :value="village.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="年度">
          <el-input-number v-model="rollupForm.year" class="rollup-year" :min="2000" :max="2100" />
        </el-form-item>
      </el-form>
      <p class="rollup-hint">按该村建档户数 / 家庭成员数汇总，回填当年村年度人口数据。</p>
      <template #footer>
        <el-button class="btn-rollup-cancel" @click="rollupVisible = false">取消</el-button>
        <el-button
          type="primary"
          class="btn-rollup-confirm"
          :loading="rollupLoading"
          @click="handleRollup"
        >
          确定回填
        </el-button>
      </template>
    </el-dialog>

    <!-- 风险预警抽屉 -->
    <el-drawer v-model="alertsVisible" title="风险预警" size="540px">
      <div class="alerts-toolbar">
        <el-select
          v-model="alertLevel"
          class="alert-level"
          placeholder="风险等级"
          clearable
          @change="loadAlerts"
        >
          <el-option
            v-for="option in RISK_LEVEL_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-button class="btn-alerts-refresh" @click="loadAlerts">刷新</el-button>
      </div>

      <div v-if="alertsLoading" class="app-loading">预警加载中…</div>
      <div v-else-if="alerts.length === 0" class="app-empty">暂无风险预警</div>
      <ul v-else class="alert-list">
        <li
          v-for="alert in alerts"
          :key="`${alert.household_id}-${alertText(alert)}`"
          class="alert-item"
        >
          <div class="alert-main">
            <span class="alert-name">{{ alert.household_name || '—' }}</span>
            <span class="alert-village">{{ alert.village_name || '—' }}</span>
            <el-tag :type="riskTagType(alert.risk_level || 'low')" size="small">
              {{ riskLevelLabel(alert.risk_level) }}
            </el-tag>
          </div>
          <div class="alert-reason">{{ alertText(alert) }}</div>
          <el-button link type="primary" class="btn-alert-view" @click="goDetailFromAlert(alert)">
            查看档案
          </el-button>
        </li>
      </ul>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useDesensitize } from '@/composables/useDesensitize'
import { getSupportedVillages } from '@/api/supportedVillage'
import {
  createHousehold,
  deleteHousehold,
  exportHouseholds,
  getHouseholdAlerts,
  getHouseholds,
  rollupHouseholds,
  updateHousehold,
  type HouseholdAlert,
  type HouseholdExportQuery,
  type HouseholdItem,
  type HouseholdListQuery,
  type HouseholdPayload,
  type HouseholdRiskLevel,
  type HouseholdRiskType,
  type HouseholdRollupResult,
  type HouseholdType,
} from '@/api/households'

import PageHeader from '@/components/common/PageHeader.vue'
import { Refresh, Search } from '@element-plus/icons-vue'
/** 户类型选项 */
const HOUSEHOLD_TYPE_OPTIONS: { value: HouseholdType; label: string }[] = [
  { value: 'general', label: '一般户' },
  { value: 'poverty', label: '脱贫户' },
  { value: 'monitor', label: '监测户' },
]

/** 风险类型选项 */
const RISK_TYPE_OPTIONS: { value: HouseholdRiskType; label: string }[] = [
  { value: 'none', label: '无' },
  { value: 'income_drop', label: '收入骤减' },
  { value: 'illness', label: '大病' },
  { value: 'housing', label: '住房' },
  { value: 'sudden', label: '突发困难' },
  { value: 'multiple', label: '多重风险' },
]

/** 风险等级选项 */
const RISK_LEVEL_OPTIONS: { value: HouseholdRiskLevel; label: string }[] = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
]

/** 汇总回填字段中文名（写回摘要展示） */
const ROLLUP_FIELD_LABELS: Record<string, string> = {
  total_households: '总户数',
  total_population: '总人口',
  poverty_households: '脱贫户数',
  monitor_households: '监测户数',
}

const route = useRoute()
const { pushSafe } = useRouterSafe()
const { ds } = useDesensitize()

const loading = ref(false)
const loadError = ref('')
const exporting = ref(false)
const saving = ref(false)
const items = ref<HouseholdItem[]>([])
const total = ref(0)
const villageOptions = ref<{ id: number; name: string }[]>([])

const query = reactive<{
  page: number
  page_size: number
  village_id: number | undefined
  risk_level: HouseholdRiskLevel | ''
  household_type: HouseholdType | ''
  keyword: string
}>({
  page: 1,
  page_size: 10,
  village_id: undefined,
  risk_level: '',
  household_type: '',
  keyword: '',
})

/** 统计条：总户数 + 当前页风险分布（实时派生，不额外请求） */
const statCards = computed(() => {
  const current = items.value ?? []
  const highRisk = current.filter((row) => row.risk_level === 'high').length
  const monitor = current.filter((row) => row.household_type === 'monitor').length
  const alertHits = current.filter((row) => (row.risk_alerts ?? []).length > 0).length
  return [
    {
      key: 'total',
      label: '建档户数',
      value: total.value,
      trend: '累计',
      trendClass: 'stat-trend--flat',
    },
    {
      key: 'high',
      label: '高风险户',
      value: highRisk,
      trend: '当前页',
      trendClass: 'stat-trend--up',
    },
    {
      key: 'monitor',
      label: '监测户',
      value: monitor,
      trend: '当前页',
      trendClass: 'stat-trend--flat',
    },
    {
      key: 'alerts',
      label: '预警命中',
      value: alertHits,
      trend: '当前页',
      trendClass: 'stat-trend--down',
    },
  ]
})

// ── 新建 / 编辑 ──
const drawerVisible = ref(false)
const editingId = ref<number | null>(null)

function emptyForm(): HouseholdPayload {
  return {
    supported_village_id: null,
    household_code: '',
    household_name: '',
    address: '',
    household_type: 'general',
    risk_type: 'none',
    risk_level: 'low',
    helper_name: '',
    helper_phone: '',
    annual_income: undefined,
    migrant_workers: undefined,
    has_serious_illness: false,
    housing_safe: true,
    last_visit_date: '',
    monitoring_note: '',
  }
}

const form = reactive<HouseholdPayload>(emptyForm())

// ── 汇总回填 ──
const rollupVisible = ref(false)
const rollupLoading = ref(false)
const rollupForm = reactive<{ village_id: number | undefined; year: number }>({
  village_id: undefined,
  year: new Date().getFullYear(),
})

// ── 风险预警 ──
const alertsVisible = ref(false)
const alertsLoading = ref(false)
const alerts = ref<HouseholdAlert[]>([])
const alertLevel = ref<HouseholdRiskLevel | ''>('')

// ── 展示映射 ──
function householdTypeLabel(value?: string | null): string {
  const found = HOUSEHOLD_TYPE_OPTIONS.find((option) => option.value === value)
  return found ? found.label : value || '—'
}

function typeTagType(value?: string | null): 'success' | 'warning' | 'danger' {
  if (value === 'poverty') return 'warning'
  if (value === 'monitor') return 'danger'
  return 'success'
}

function riskLevelLabel(value?: string | null): string {
  const found = RISK_LEVEL_OPTIONS.find((option) => option.value === value)
  return found ? found.label : value || '—'
}

function riskTagType(value?: string | null): 'info' | 'warning' | 'danger' {
  if (value === 'high') return 'danger'
  if (value === 'medium') return 'warning'
  return 'info'
}

function formatDate(value?: string | null): string {
  return value || '—'
}

function formatHelperName(value?: string | null): string {
  return value ? ds(value, 'name') : '—'
}

function alertsOf(row: HouseholdItem): string[] {
  return row.risk_alerts ?? []
}

function alertText(alert: HouseholdAlert): string {
  if (alert.alerts && alert.alerts.length > 0) return alert.alerts.join('；')
  return alert.reason || '规则命中'
}

// ── 数据加载 ──
async function loadVillages(): Promise<void> {
  try {
    const res = await getSupportedVillages({ page: 1, page_size: 200 })
    const list = Array.isArray(res) ? res : (res?.items ?? [])
    villageOptions.value = list.map((row: any) => ({
      id: row.id,
      name: row.village_name ?? row.name ?? `村${row.id}`,
    }))
  } catch {
    villageOptions.value = []
  }
}

async function loadData(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    const params: HouseholdListQuery = {
      page: query.page,
      page_size: query.page_size,
      village_id: query.village_id,
      risk_level: query.risk_level,
      household_type: query.household_type,
      keyword: query.keyword.trim() || undefined,
    }
    const res = await getHouseholds(params)
    items.value = res.items ?? []
    total.value = res.total ?? 0
  } catch {
    items.value = []
    total.value = 0
    loadError.value = '建档台账加载失败，请稍后重试'
    ElMessage.error('加载一户一档列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  query.page = 1
  void loadData()
}

function handleReset(): void {
  query.village_id = undefined
  query.risk_level = ''
  query.household_type = ''
  query.keyword = ''
  handleSearch()
}

function handlePageChange(page: number): void {
  query.page = page
  void loadData()
}

function handleSizeChange(size: number): void {
  query.page_size = size
  query.page = 1
  void loadData()
}

// ── 新建 / 编辑 / 删除 ──
function openCreate(): void {
  editingId.value = null
  Object.assign(form, emptyForm())
  drawerVisible.value = true
}

function openEdit(row: HouseholdItem): void {
  editingId.value = row.id
  Object.assign(form, {
    supported_village_id: row.supported_village_id,
    household_code: row.household_code ?? '',
    household_name: row.household_name,
    address: row.address ?? '',
    household_type: row.household_type,
    risk_type: row.risk_type,
    risk_level: row.risk_level,
    helper_name: row.helper_name ?? '',
    helper_phone: row.helper_phone ?? '',
    annual_income: row.annual_income ?? undefined,
    migrant_workers: row.migrant_workers ?? undefined,
    has_serious_illness: row.has_serious_illness === true,
    housing_safe: row.housing_safe !== false,
    last_visit_date: row.last_visit_date ?? '',
    monitoring_note: row.monitoring_note ?? '',
  })
  drawerVisible.value = true
}

async function handleSave(): Promise<void> {
  if (!form.supported_village_id) {
    ElMessage.warning('请选择帮扶村')
    return
  }
  if (!form.household_name || !String(form.household_name).trim()) {
    ElMessage.warning('请输入户主姓名')
    return
  }
  saving.value = true
  try {
    if (editingId.value === null) {
      await createHousehold(form)
      ElMessage.success('建档成功')
      query.page = 1
    } else {
      await updateHousehold(editingId.value, form)
      ElMessage.success('档案已更新')
    }
    drawerVisible.value = false
    await loadData()
  } catch {
    ElMessage.error(editingId.value === null ? '建档失败' : '更新失败')
  } finally {
    saving.value = false
  }
}

/** 行操作下拉（当前仅删除为次要操作） */
function handleRowCommand(command: string, row: HouseholdItem): void {
  if (command === 'delete') void handleDelete(row)
}

async function handleDelete(row: HouseholdItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除「${row.household_name}」的一户一档吗？`, '提示', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteHousehold(row.id)
    ElMessage.success('删除成功')
    if (items.value.length === 1 && query.page > 1) query.page -= 1
    await loadData()
  } catch {
    ElMessage.error('删除失败')
  }
}

function goDetail(row: HouseholdItem): void {
  pushSafe(`/households/${row.id}`)
}

function goDetailFromAlert(alert: HouseholdAlert): void {
  pushSafe(`/households/${alert.household_id}`)
}

// ── 导出 ──
async function handleExport(format: HouseholdExportQuery['format']): Promise<void> {
  exporting.value = true
  try {
    await exportHouseholds({
      format,
      village_id: query.village_id,
      risk_level: query.risk_level,
    })
    ElMessage.success(`台账 ${format === 'xlsx' ? 'Excel' : 'CSV'} 导出已开始`)
  } catch {
    ElMessage.error('台账导出失败')
  } finally {
    exporting.value = false
  }
}

// ── 汇总回填 ──
function openRollup(): void {
  rollupForm.village_id = query.village_id
  rollupForm.year = new Date().getFullYear()
  rollupVisible.value = true
}

/** 汇总回填结果 → 可读摘要（message / written / 已知字段 / 兜底） */
function formatRollupResult(result: HouseholdRollupResult): string {
  if (result.message) return result.message
  if (result.written && Object.keys(result.written).length > 0) {
    const parts = Object.entries(result.written).map(
      ([key, value]) => `${ROLLUP_FIELD_LABELS[key] ?? key} ${value ?? '—'}`
    )
    return `已回填：${parts.join('、')}`
  }
  const known: string[] = []
  if (result.total_households !== undefined) known.push(`总户数 ${result.total_households}`)
  if (result.total_population !== undefined) known.push(`总人口 ${result.total_population}`)
  if (result.poverty_households !== undefined) known.push(`脱贫户数 ${result.poverty_households}`)
  if (result.monitor_households !== undefined) known.push(`监测户数 ${result.monitor_households}`)
  return known.length > 0 ? `已回填：${known.join('、')}` : '汇总回填完成'
}

async function handleRollup(): Promise<void> {
  if (!rollupForm.village_id) {
    ElMessage.warning('请选择帮扶村')
    return
  }
  rollupLoading.value = true
  try {
    const result = await rollupHouseholds({
      village_id: rollupForm.village_id,
      year: rollupForm.year,
    })
    ElMessage.success(formatRollupResult(result))
    rollupVisible.value = false
  } catch {
    ElMessage.error('汇总回填失败')
  } finally {
    rollupLoading.value = false
  }
}

// ── 风险预警 ──
function openAlerts(): void {
  alertsVisible.value = true
  void loadAlerts()
}

async function loadAlerts(): Promise<void> {
  alertsLoading.value = true
  try {
    const res = await getHouseholdAlerts({ level: alertLevel.value })
    alerts.value = Array.isArray(res) ? res : (res?.items ?? [])
  } catch {
    alerts.value = []
    ElMessage.error('加载风险预警失败')
  } finally {
    alertsLoading.value = false
  }
}

/** 从「帮扶村管理 → 年度数据」页跳转时携带 village_id 预筛选（v1.15.15 入口迁移） */
function prefillFromQuery(): void {
  const villageId = Number(route.query.village_id)
  if (Number.isInteger(villageId) && villageId > 0) {
    query.village_id = villageId
  }
}

onMounted(() => {
  prefillFromQuery()
  void loadVillages()
  void loadData()
})
</script>

<style lang="scss" scoped>
/* W2：结构/间距补充；颜色与卡片视觉由 W1 全局类（.list-page/.app-card/.app-stat-card/
   .app-empty/.app-loading/.app-error/num-cell 等）统一提供，本文件不新增色值。 */
.household-list-page {
  padding: var(--spacing-lg, 20px);
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--spacing-md, 12px);
  margin-bottom: var(--spacing-lg, 16px);
}
.stat-grid .stat-card {
  padding: var(--spacing-lg, 16px);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md, 12px);
}
.filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-sm, 8px);
}
.list-hint {
  margin: var(--spacing-sm, 8px) 0 0;
}
.f-village {
  width: 180px;
}
.f-risk,
.f-type {
  width: 130px;
}
.f-keyword {
  width: 200px;
}
.alert-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}
.pager {
  margin-top: var(--spacing-md, 12px);
  display: flex;
  justify-content: flex-end;
}
.rollup-hint {
  margin: 4px 0 0;
}
.alerts-toolbar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 8px);
  margin-bottom: var(--spacing-md, 12px);
}
.alert-level {
  width: 160px;
}
.alert-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm, 8px);
}
.alert-main {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 8px);
}
.alert-reason {
  margin: 6px 0;
}
@media (max-width: 1200px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
