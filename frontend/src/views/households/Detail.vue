<template>
  <div class="household-detail-page">
    <div class="page-header">
      <div class="header-left">
        <el-button class="btn-back" @click="goBack">返回列表</el-button>
        <h2 class="page-title">一户一档详情</h2>
      </div>
      <div class="header-actions">
        <el-button class="btn-refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div v-if="loadError" class="load-error">
      <span class="error-text">{{ loadError }}</span>
      <el-button type="primary" class="btn-retry" @click="load">重试</el-button>
    </div>
    <div v-else-if="!household && loading" class="muted loading-tip">加载中…</div>

    <template v-else-if="household">
      <!-- 档案头 -->
      <el-card class="profile-card">
        <template #header>
          <div class="card-header">
            <span class="household-name">{{ household.household_name }}</span>
            <div class="badges">
              <el-tag :type="typeTagType(household.household_type)">
                {{ householdTypeLabel(household.household_type) }}
              </el-tag>
              <el-tag :type="riskTagType(household.risk_level)">
                {{ riskLevelLabel(household.risk_level) }}
              </el-tag>
            </div>
          </div>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="户编号">
            {{ household.household_code || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="帮扶村">
            {{ household.village_name || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="帮扶责任人">
            {{ household.helper_name || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ maskedPhone() }}</el-descriptions-item>
          <el-descriptions-item label="详细地址" :span="2">
            {{ household.address || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="最近走访">
            {{ formatDate(household.last_visit_date) }}
          </el-descriptions-item>
          <el-descriptions-item label="风险类型">
            {{ riskTypeLabel(household.risk_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="监测备注" :span="2">
            {{ household.monitoring_note || '—' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 监测指标卡 -->
      <el-card class="indicator-card">
        <template #header>
          <div class="card-header"><span>监测指标</span></div>
        </template>
        <div class="indicator-grid">
          <div class="indicator-item">
            <div class="indicator-value">{{ formatMoney(household.annual_income) }}</div>
            <div class="indicator-label">家庭年收入(元)</div>
          </div>
          <div class="indicator-item">
            <div class="indicator-value">{{ household.migrant_workers ?? 0 }}</div>
            <div class="indicator-label">务工人数</div>
          </div>
          <div class="indicator-item">
            <div class="indicator-value">{{ yesNo(household.has_serious_illness) }}</div>
            <div class="indicator-label">大病</div>
          </div>
          <div class="indicator-item">
            <div class="indicator-value">{{ yesNo(household.housing_safe) }}</div>
            <div class="indicator-label">住房安全</div>
          </div>
        </div>
      </el-card>

      <!-- 预警提示 -->
      <el-card class="alert-card">
        <template #header>
          <div class="card-header"><span>预警提示</span></div>
        </template>
        <template v-if="riskAlerts.length > 0">
          <el-alert
            v-for="alert in riskAlerts"
            :key="alert"
            class="risk-alert"
            type="warning"
            :closable="false"
            show-icon
            :title="alert"
          />
        </template>
        <div v-else class="muted">暂无预警命中</div>
      </el-card>

      <!-- 风险记录时间线 -->
      <el-card class="risk-card">
        <template #header>
          <div class="card-header">
            <span>风险记录</span>
            <el-button
              type="primary"
              plain
              size="small"
              class="btn-add-risk"
              @click="openRiskDialog"
            >
              登记风险
            </el-button>
          </div>
        </template>
        <el-timeline v-if="riskRecords.length > 0" class="risk-timeline">
          <el-timeline-item
            v-for="record in riskRecords"
            :key="record.id"
            :timestamp="formatDate(record.detected_at)"
            placement="top"
          >
            <div class="risk-item">
              <div class="risk-head">
                <el-tag :type="riskTagType(record.risk_level)" size="small">
                  {{ riskLevelLabel(record.risk_level) }}
                </el-tag>
                <span class="risk-type">{{ riskTypeLabel(record.risk_type) }}</span>
                <el-tag :type="record.status === 'open' ? 'warning' : 'info'" size="small">
                  {{ record.status === 'open' ? '跟进中' : '已关闭' }}
                </el-tag>
              </div>
              <div class="risk-reason">{{ record.reason || '—' }}</div>
              <div v-if="record.closed_note" class="risk-closed-note">
                关闭说明：{{ record.closed_note }}
              </div>
              <el-button
                v-if="record.status === 'open'"
                link
                type="primary"
                class="btn-close-risk"
                @click="closeRisk(record)"
              >
                关闭处理
              </el-button>
            </div>
          </el-timeline-item>
        </el-timeline>
        <div v-else class="muted">暂无风险记录</div>
      </el-card>

      <!-- 家庭成员 -->
      <el-card class="member-card">
        <template #header>
          <div class="card-header">
            <span>家庭成员</span>
            <el-button
              type="primary"
              plain
              size="small"
              class="btn-add-member"
              @click="openAddMember"
            >
              新增成员
            </el-button>
          </div>
        </template>
        <el-table v-if="members.length > 0" :data="members" class="member-table">
          <el-table-column prop="name" label="姓名" min-width="100" />
          <el-table-column label="与户主关系" width="110">
            <template #default="{ row }">{{ row.relation || '—' }}</template>
          </el-table-column>
          <el-table-column label="性别" width="70">
            <template #default="{ row }">{{ row.gender || '—' }}</template>
          </el-table-column>
          <el-table-column label="出生年" width="90">
            <template #default="{ row }">{{ row.birth_year ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="健康状态" width="110">
            <template #default="{ row }">{{ row.health_status || '—' }}</template>
          </el-table-column>
          <el-table-column label="就业状态" width="110">
            <template #default="{ row }">{{ row.employment_status || '—' }}</template>
          </el-table-column>
          <el-table-column label="个人年收入(元)" width="130">
            <template #default="{ row }">{{ formatMoney(row.income) }}</template>
          </el-table-column>
          <el-table-column label="兜底保障" width="90">
            <template #default="{ row }">{{ yesNo(row.is_special_support) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                class="btn-member-edit"
                @click="openEditMember(row as HouseholdMember)"
              >
                编辑
              </el-button>
              <el-button
                link
                type="danger"
                class="btn-member-delete"
                @click="removeMember(row as HouseholdMember)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="muted">暂无家庭成员</div>
      </el-card>

      <!-- 走访记录 -->
      <el-card class="visit-card">
        <template #header>
          <div class="card-header">
            <span>走访记录</span>
            <span class="total-hint">共 {{ visits.length }} 次</span>
          </div>
        </template>
        <el-table v-if="visits.length > 0" :data="visits" class="visit-table">
          <el-table-column prop="visit_date" label="走访日期" width="120" />
          <el-table-column prop="visitors" label="走访人" min-width="120" />
          <el-table-column label="目的" min-width="140">
            <template #default="{ row }">{{ row.purpose || '—' }}</template>
          </el-table-column>
          <el-table-column label="内容" min-width="180">
            <template #default="{ row }">{{ row.content || '—' }}</template>
          </el-table-column>
        </el-table>
        <div v-else class="muted">暂无走访记录</div>
      </el-card>
    </template>

    <!-- 家庭成员对话框 -->
    <el-dialog
      v-model="memberVisible"
      :title="editingMemberId === null ? '新增家庭成员' : '编辑家庭成员'"
      width="520px"
    >
      <el-form :model="memberForm" label-width="110px">
        <el-form-item label="姓名" required>
          <el-input v-model="memberForm.name" class="member-name" maxlength="64" />
        </el-form-item>
        <el-form-item label="与户主关系">
          <el-input v-model="memberForm.relation" class="member-relation" maxlength="32" />
        </el-form-item>
        <el-form-item label="身份证号">
          <el-input v-model="memberForm.id_card" class="member-id-card" maxlength="64" />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="memberForm.gender" class="member-gender" clearable>
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
          </el-select>
        </el-form-item>
        <el-form-item label="出生年">
          <el-input-number
            v-model="memberForm.birth_year"
            class="member-birth"
            :min="1900"
            :max="2100"
          />
        </el-form-item>
        <el-form-item label="学历">
          <el-input v-model="memberForm.education" class="member-education" maxlength="32" />
        </el-form-item>
        <el-form-item label="健康状态">
          <el-select v-model="memberForm.health_status" class="member-health" clearable>
            <el-option label="健康" value="健康" />
            <el-option label="慢性病" value="慢性病" />
            <el-option label="大病" value="大病" />
            <el-option label="残疾" value="残疾" />
          </el-select>
        </el-form-item>
        <el-form-item label="就业状态">
          <el-select v-model="memberForm.employment_status" class="member-employment" clearable>
            <el-option label="务工" value="务工" />
            <el-option label="务农" value="务农" />
            <el-option label="学生" value="学生" />
            <el-option label="无劳动能力" value="无劳动能力" />
          </el-select>
        </el-form-item>
        <el-form-item label="个人年收入(元)">
          <el-input-number
            v-model="memberForm.income"
            class="member-income"
            :min="0"
            :precision="2"
          />
        </el-form-item>
        <el-form-item label="兜底保障">
          <el-switch v-model="memberForm.is_special_support" class="member-support" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button class="btn-member-cancel" @click="memberVisible = false">取消</el-button>
        <el-button
          type="primary"
          class="btn-member-save"
          :loading="memberSaving"
          @click="saveMember"
        >
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 风险登记对话框 -->
    <el-dialog v-model="riskVisible" title="登记风险记录" width="480px">
      <el-form :model="riskForm" label-width="100px">
        <el-form-item label="风险类型" required>
          <el-select v-model="riskForm.risk_type" class="risk-form-type">
            <el-option
              v-for="option in RISK_TYPE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级">
          <el-select v-model="riskForm.risk_level" class="risk-form-level">
            <el-option
              v-for="option in RISK_LEVEL_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="风险原因">
          <el-input
            v-model="riskForm.reason"
            class="risk-form-reason"
            type="textarea"
            :rows="3"
            maxlength="500"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button class="btn-risk-cancel" @click="riskVisible = false">取消</el-button>
        <el-button
          type="primary"
          class="btn-risk-save"
          :loading="riskSaving"
          @click="saveRiskRecord"
        >
          登记
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useDesensitize } from '@/composables/useDesensitize'
import {
  closeHouseholdRiskRecord,
  createHouseholdMember,
  createHouseholdRiskRecord,
  deleteHouseholdMember,
  getHousehold,
  getHouseholdMembers,
  updateHouseholdMember,
  type HouseholdDetail,
  type HouseholdMember,
  type HouseholdMemberPayload,
  type HouseholdRiskLevel,
  type HouseholdRiskRecord,
  type HouseholdRiskType,
  type HouseholdVisit,
} from '@/api/households'

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

const { pushSafe } = useRouterSafe()
const { ds } = useDesensitize()
const route = useRoute()
const householdId = Number(route.params.id)

const loading = ref(false)
const loadError = ref('')
const household = ref<HouseholdDetail | null>(null)
const members = ref<HouseholdMember[]>([])
const riskRecords = ref<HouseholdRiskRecord[]>([])
const visits = ref<HouseholdVisit[]>([])

const riskAlerts = computed(() => household.value?.risk_alerts ?? [])

// ── 展示映射 ──
function householdTypeLabel(value?: string | null): string {
  if (value === 'poverty') return '脱贫户'
  if (value === 'monitor') return '监测户'
  if (value === 'general') return '一般户'
  return value || '—'
}

function typeTagType(value?: string | null): 'success' | 'warning' | 'danger' {
  if (value === 'poverty') return 'warning'
  if (value === 'monitor') return 'danger'
  return 'success'
}

function riskLevelLabel(value?: string | null): string {
  if (value === 'high') return '高'
  if (value === 'medium') return '中'
  if (value === 'low') return '低'
  return value || '—'
}

function riskTagType(value?: string | null): 'info' | 'warning' | 'danger' {
  if (value === 'high') return 'danger'
  if (value === 'medium') return 'warning'
  return 'info'
}

function riskTypeLabel(value?: string | null): string {
  const found = RISK_TYPE_OPTIONS.find((option) => option.value === value)
  return found ? found.label : value || '—'
}

function formatDate(value?: string | null): string {
  return value || '—'
}

function formatMoney(value?: number | null): string {
  if (value === null || value === undefined) return '—'
  return Number(value).toFixed(2)
}

function yesNo(value?: boolean | null): string {
  return value === true ? '是' : '否'
}

function maskedPhone(): string {
  return household.value?.helper_phone ? ds(household.value.helper_phone, 'phone') : '—'
}

// ── 加载 ──
async function load(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    const detail = await getHousehold(householdId)
    household.value = detail
    riskRecords.value = detail.risk_records ?? []
    visits.value = detail.visits ?? []
    members.value = detail.members ?? []
    await loadMembers()
  } catch {
    household.value = null
    members.value = []
    riskRecords.value = []
    visits.value = []
    loadError.value = '档案加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

/** 成员列表（独立端点，详情未富化时作为数据源） */
async function loadMembers(): Promise<void> {
  try {
    const res = await getHouseholdMembers(householdId)
    members.value = Array.isArray(res) ? res : (res?.items ?? [])
  } catch {
    /* 成员接口失败保留详情内成员，不阻断页面 */
  }
}

function goBack(): void {
  pushSafe('/households')
}

// ── 家庭成员 CRUD ──
const memberVisible = ref(false)
const memberSaving = ref(false)
const editingMemberId = ref<number | null>(null)

function emptyMember(): HouseholdMemberPayload {
  return {
    name: '',
    relation: '',
    id_card: '',
    gender: '',
    birth_year: undefined,
    education: '',
    health_status: '',
    employment_status: '',
    income: undefined,
    is_special_support: false,
  }
}

const memberForm = reactive<HouseholdMemberPayload>(emptyMember())

function openAddMember(): void {
  editingMemberId.value = null
  Object.assign(memberForm, emptyMember())
  memberVisible.value = true
}

function openEditMember(row: HouseholdMember): void {
  editingMemberId.value = row.id
  Object.assign(memberForm, {
    name: row.name,
    relation: row.relation ?? '',
    id_card: row.id_card ?? '',
    gender: row.gender ?? '',
    birth_year: row.birth_year ?? undefined,
    education: row.education ?? '',
    health_status: row.health_status ?? '',
    employment_status: row.employment_status ?? '',
    income: row.income ?? undefined,
    is_special_support: row.is_special_support === true,
  })
  memberVisible.value = true
}

async function saveMember(): Promise<void> {
  if (!memberForm.name || !String(memberForm.name).trim()) {
    ElMessage.warning('请输入成员姓名')
    return
  }
  memberSaving.value = true
  try {
    if (editingMemberId.value === null) {
      await createHouseholdMember(householdId, memberForm)
      ElMessage.success('成员已新增')
    } else {
      await updateHouseholdMember(householdId, editingMemberId.value, memberForm)
      ElMessage.success('成员已更新')
    }
    memberVisible.value = false
    await loadMembers()
  } catch {
    ElMessage.error(editingMemberId.value === null ? '新增成员失败' : '更新成员失败')
  } finally {
    memberSaving.value = false
  }
}

async function removeMember(row: HouseholdMember): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除成员「${row.name}」吗？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteHouseholdMember(householdId, row.id)
    ElMessage.success('成员已删除')
    await loadMembers()
  } catch {
    ElMessage.error('删除成员失败')
  }
}

// ── 风险记录 ──
const riskVisible = ref(false)
const riskSaving = ref(false)
const riskForm = reactive<{
  risk_type: HouseholdRiskType
  risk_level: HouseholdRiskLevel
  reason: string
}>({
  risk_type: 'income_drop',
  risk_level: 'medium',
  reason: '',
})

function openRiskDialog(): void {
  riskForm.risk_type = 'income_drop'
  riskForm.risk_level = 'medium'
  riskForm.reason = ''
  riskVisible.value = true
}

async function saveRiskRecord(): Promise<void> {
  riskSaving.value = true
  try {
    await createHouseholdRiskRecord(householdId, {
      risk_type: riskForm.risk_type,
      risk_level: riskForm.risk_level,
      reason: riskForm.reason || undefined,
    })
    ElMessage.success('风险记录已登记')
    riskVisible.value = false
    await load()
  } catch {
    ElMessage.error('登记风险记录失败')
  } finally {
    riskSaving.value = false
  }
}

/** 关闭风险记录：弹窗填写关闭说明 → 调接口 → 刷新档案 */
async function closeRisk(record: HouseholdRiskRecord): Promise<void> {
  let note = ''
  try {
    const res = await ElMessageBox.prompt('请填写关闭说明（可选）', '关闭风险记录', {
      inputPlaceholder: '处理结果 / 备注',
      confirmButtonText: '确定关闭',
      cancelButtonText: '取消',
    })
    note = res.value || ''
  } catch {
    return
  }
  try {
    await closeHouseholdRiskRecord(record.id, { closed_note: note || undefined })
    ElMessage.success('风险记录已关闭')
    await load()
  } catch {
    ElMessage.error('关闭风险记录失败')
  }
}

onMounted(() => {
  void load()
})
</script>

<style lang="scss" scoped>
.household-detail-page {
  padding: 20px;
  background: var(--color-bg-hover);
  min-height: 100vh;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text-primary);
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.load-error {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
}
.error-text {
  color: var(--color-danger);
}
.loading-tip {
  padding: 24px;
}
.muted {
  color: var(--color-text-secondary);
}
.profile-card,
.indicator-card,
.alert-card,
.risk-card,
.member-card,
.visit-card {
  margin-bottom: 16px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.badges {
  display: flex;
  align-items: center;
  gap: 8px;
}
.household-name {
  font-size: 16px;
  color: var(--color-text-primary);
}
.indicator-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.indicator-item {
  text-align: center;
  padding: 12px 8px;
  border-radius: 8px;
  background: var(--color-bg-hover);
}
.indicator-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary);
}
.indicator-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.risk-alert {
  margin-bottom: 8px;
}
.risk-timeline {
  padding-left: 4px;
}
.risk-item {
  padding: 4px 0;
}
.risk-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.risk-type {
  font-size: 13px;
  color: var(--color-text-primary);
}
.risk-reason {
  margin: 6px 0;
  font-size: 13px;
  color: var(--color-text-regular);
}
.risk-closed-note {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.total-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--color-text-secondary);
}
</style>
