<template>
  <div class="pairing-list">
    <div class="page-header">
      <h2>结对帮扶与走访台账</h2>
      <div class="header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">新建结对</el-button>
      </div>
    </div>

    <div class="stats-row">
      <el-tag>结对总数 {{ stats.total }}</el-tag>
      <el-tag type="success">在帮 {{ stats.active }}</el-tag>
      <el-tag type="info">已结束 {{ stats.ended }}</el-tag>
      <el-tag type="warning">走访 {{ stats.visits }} 次</el-tag>
    </div>

    <el-card>
      <div class="filters">
        <el-input
          v-model="query.keyword"
          placeholder="主体 / 事项 / 学生"
          clearable
          class="f-keyword"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="query.subject_type" placeholder="帮扶主体" clearable class="f-select">
          <el-option
            v-for="o in SUBJECT_OPTIONS"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
        <el-select
          v-model="query.partner_type"
          placeholder="帮扶对象"
          clearable
          class="f-select"
          @change="handlePartnerTypeFilterChange"
        >
          <el-option
            v-for="o in PARTNER_OPTIONS"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
        <el-select
          v-if="query.partner_type === 'village' || query.partner_type === 'school'"
          v-model="query.partner_id"
          clearable
          filterable
          placeholder="选择具体对象"
          class="f-partner"
        >
          <el-option v-for="o in partnerOptions" :key="o.id" :label="o.label" :value="o.id" />
        </el-select>
        <el-select v-model="query.status" placeholder="状态" clearable class="f-select">
          <el-option v-for="o in STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <div v-if="partnerScopeText" class="partner-scope">
        <el-tag type="success">对象：{{ partnerScopeText }}</el-tag>
        <el-button link class="btn-clear-partner" @click="clearPartnerScope"
          >清除对象筛选</el-button
        >
      </div>

      <el-table v-loading="loading" :data="items" class="pairing-table">
        <el-table-column label="帮扶主体" min-width="180">
          <template #default="{ row }">{{ subjectLabel(row as PairingItem) }}</template>
        </el-table-column>
        <el-table-column label="帮扶对象" min-width="180">
          <template #default="{ row }">{{ partnerLabel(row as PairingItem) }}</template>
        </el-table-column>
        <el-table-column prop="title" label="帮扶事项" min-width="160" />
        <el-table-column label="起止日期" min-width="180">
          <template #default="{ row }">{{ dateRange(row as PairingItem) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row as PairingItem)">{{
              statusText(row as PairingItem)
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              class="act-visits"
              @click="openVisits(row as PairingItem)"
            >
              走访台账
            </el-button>
            <el-button link class="act-edit" @click="openEdit(row as PairingItem)">编辑</el-button>
            <el-button
              link
              type="danger"
              class="act-delete"
              @click="handleDeleteRow(row as PairingItem)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <EmptyState text="暂无结对记录" />
        </template>
      </el-table>

      <el-pagination
        :current-page="query.page"
        :page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pairing-pagination"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </el-card>

    <!-- 新建 / 编辑结对 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="帮扶主体">
          <el-select v-model="form.subject_type" class="form-subject-type">
            <el-option
              v-for="o in SUBJECT_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
          <el-input
            v-model="form.subject_name"
            placeholder="单位 / 支部 / 干部姓名"
            class="form-subject-name"
          />
        </el-form-item>
        <el-form-item label="帮扶对象">
          <el-select
            v-model="form.partner_type"
            class="form-partner-type"
            @change="handlePartnerTypeChange"
          >
            <el-option
              v-for="o in PARTNER_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.partner_type === 'village'" label="帮扶村">
          <el-select
            v-model="form.village_id"
            filterable
            placeholder="请选择帮扶村"
            class="form-village"
          >
            <el-option v-for="v in villages" :key="v.id" :label="v.village_name" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else-if="form.partner_type === 'school'" label="帮扶学校">
          <el-select
            v-model="form.school_id"
            filterable
            placeholder="请选择帮扶学校"
            class="form-school"
          >
            <el-option v-for="s in schools" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="学生姓名">
          <el-input v-model="form.student_name" placeholder="困难学生姓名" class="form-student" />
        </el-form-item>
        <el-form-item label="帮扶事项">
          <el-input v-model="form.title" placeholder="如：助学帮扶、产业帮扶" class="form-title" />
        </el-form-item>
        <el-form-item label="帮扶内容">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="3"
            placeholder="帮扶计划 / 措施"
            class="form-content"
          />
        </el-form-item>
        <el-form-item label="起止日期">
          <el-date-picker
            v-model="form.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="起始日期"
            class="form-start"
          />
          <el-date-picker
            v-model="form.end_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="结束日期"
            class="form-end"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="active">帮扶中</el-radio>
            <el-radio value="ended">已结束</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" placeholder="备注（选填）" class="form-note" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" class="btn-save" @click="handleSubmit">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 走访台账 -->
    <el-drawer v-model="visitsVisible" :title="visitsTitle" size="680px">
      <div class="visit-form">
        <el-date-picker
          v-model="visitForm.visit_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="走访日期"
          class="vf-date"
        />
        <el-input v-model="visitForm.visitors" placeholder="走访人员" class="vf-visitors" />
        <el-input v-model="visitForm.purpose" placeholder="走访事项" class="vf-purpose" />
        <el-input v-model="visitForm.materials" placeholder="慰问物资" class="vf-materials" />
        <el-button
          type="primary"
          :loading="visitSaving"
          class="btn-visit-submit"
          @click="handleVisitSubmit"
        >
          {{ visitSubmitText }}
        </el-button>
        <el-button v-if="editingVisitId" class="btn-visit-cancel" @click="resetVisitForm">
          取消编辑
        </el-button>
      </div>

      <el-table v-loading="visitsLoading" :data="visits" size="small" class="visits-table">
        <el-table-column prop="visit_date" label="走访日期" width="120" />
        <el-table-column prop="visitors" label="走访人员" width="150" />
        <el-table-column prop="purpose" label="走访事项" />
        <el-table-column prop="materials" label="慰问物资" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button link class="act-visit-edit" @click="handleVisitEdit(row as VisitItem)">
              编辑
            </el-button>
            <el-button
              link
              type="danger"
              class="act-visit-delete"
              @click="handleVisitDelete(row as VisitItem)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <EmptyState text="暂无走访记录" />
        </template>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { schoolsApi } from '@/api/schools'
import { getSupportedVillages } from '@/api/supportedVillage'
import {
  createPairing,
  createVisit,
  deletePairing,
  deleteVisit,
  getPairingStats,
  getPairings,
  getVisits,
  updatePairing,
  updateVisit,
  type PairingItem,
  type PairingListQuery,
  type PairingStats,
  type VisitItem,
} from '@/api/pairings'

const SUBJECT_OPTIONS = [
  { value: 'unit', label: '单位' },
  { value: 'branch', label: '党支部' },
  { value: 'person', label: '个人' },
]

const PARTNER_OPTIONS = [
  { value: 'village', label: '帮扶村' },
  { value: 'school', label: '帮扶学校' },
  { value: 'student', label: '困难学生' },
]

const STATUS_OPTIONS = [
  { value: 'active', label: '帮扶中' },
  { value: 'ended', label: '已结束' },
]

const EMPTY_STATS: PairingStats = {
  total: 0,
  active: 0,
  ended: 0,
  villages: 0,
  schools: 0,
  students: 0,
  visits: 0,
}

function labelOf(options: { value: string; label: string }[], value: string): string {
  return options.find((o) => o.value === value)?.label ?? value
}

const loading = ref(false)
const saving = ref(false)
const items = ref<PairingItem[]>([])
const total = ref(0)
const stats = ref<PairingStats>({ ...EMPTY_STATS })

const route = useRoute()

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  subject_type: '',
  partner_type: '',
  partner_id: null as number | null,
  status: '',
})

/**
 * 深链预填「按对象聚合」筛选：
 * `/pairings?partner_type=village&partner_id=1`（村/校详情入口直接跳该对象台账）。
 * 非法值静默忽略（fail-open 为“全量列表”，不阻塞页面）。
 */
function applyQueryPrefill() {
  const type = String(route.query.partner_type ?? '')
  if (PARTNER_OPTIONS.some((o) => o.value === type)) query.partner_type = type
  const id = Number(route.query.partner_id ?? '')
  if (id > 0) query.partner_id = id
}

function buildParams(): PairingListQuery {
  const params: PairingListQuery = { page: query.page, page_size: query.page_size }
  if (query.keyword) params.keyword = query.keyword
  if (query.subject_type) params.subject_type = query.subject_type
  if (query.partner_type) params.partner_type = query.partner_type
  if (query.partner_id) params.partner_id = query.partner_id
  if (query.status) params.status = query.status
  return params
}

function subjectLabel(row: PairingItem): string {
  return `${labelOf(SUBJECT_OPTIONS, row.subject_type)} · ${row.subject_name}`
}

function partnerLabel(row: PairingItem): string {
  return `${labelOf(PARTNER_OPTIONS, row.partner_type)} · ${row.partner_name || row.student_name || '未关联'}`
}

function dateRange(row: PairingItem): string {
  const parts = [row.start_date, row.end_date].filter(Boolean)
  return parts.length ? parts.join(' ~ ') : '-'
}

function statusText(row: PairingItem): string {
  return row.status === 'active' ? '帮扶中' : '已结束'
}

function statusTagType(row: PairingItem): 'success' | 'info' {
  return row.status === 'active' ? 'success' : 'info'
}

async function load() {
  loading.value = true
  try {
    const [listRes, statsRes] = await Promise.all([getPairings(buildParams()), getPairingStats()])
    items.value = listRes?.items ?? []
    total.value = listRes?.total ?? 0
    stats.value = statsRes ?? { ...EMPTY_STATS }
  } catch {
    ElMessage.error('加载台账失败')
  } finally {
    loading.value = false
  }
}

async function handleSearch() {
  query.page = 1
  await load()
}

async function handleReset() {
  query.page = 1
  query.page_size = 20
  query.keyword = ''
  query.subject_type = ''
  query.partner_type = ''
  query.partner_id = null
  query.status = ''
  await load()
}

async function handlePageChange(page: number) {
  query.page = page
  await load()
}

async function handleSizeChange(size: number) {
  query.page_size = size
  query.page = 1
  await load()
}

// ==================== 新建 / 编辑 ====================

interface PairingForm {
  subject_type: string
  subject_name: string
  partner_type: string
  village_id: number | null
  school_id: number | null
  student_name: string
  title: string
  content: string
  start_date: string
  end_date: string
  status: string
  note: string
}

function emptyForm(): PairingForm {
  return {
    subject_type: 'unit',
    subject_name: '',
    partner_type: 'village',
    village_id: null,
    school_id: null,
    student_name: '',
    title: '',
    content: '',
    start_date: '',
    end_date: '',
    status: 'active',
    note: '',
  }
}

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<PairingForm>(emptyForm())
const dialogTitle = computed(() => (editingId.value ? '编辑结对记录' : '新建结对记录'))

const villages = ref<{ id: number; village_name: string }[]>([])
const schools = ref<{ id: number; name: string }[]>([])

/** 当前对象类型下的可选对象（村/学校）；学生按关键字搜索，不做 id 过滤 */
const partnerOptions = computed(() => {
  if (query.partner_type === 'village') {
    return villages.value.map((v) => ({ id: v.id, label: v.village_name }))
  }
  if (query.partner_type === 'school') {
    return schools.value.map((s) => ({ id: s.id, label: s.name }))
  }
  return []
})

const partnerScopeText = computed(() => {
  if (!query.partner_id) return ''
  const hit = partnerOptions.value.find((o) => o.id === query.partner_id)
  return hit ? hit.label : `#${query.partner_id}`
})

function handlePartnerTypeFilterChange() {
  query.partner_id = null
}

function clearPartnerScope() {
  query.partner_type = ''
  query.partner_id = null
}

async function loadOptions() {
  try {
    const [villageRes, schoolRes] = await Promise.all([
      getSupportedVillages({ page: 1, page_size: 200 }),
      schoolsApi.list({ page: 1, page_size: 200 }),
    ])
    villages.value = villageRes?.items ?? []
    schools.value = schoolRes?.items ?? []
  } catch {
    ElMessage.error('加载帮扶村 / 学校选项失败')
  }
}

function handlePartnerTypeChange() {
  form.village_id = null
  form.school_id = null
  form.student_name = ''
}

function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row: PairingItem) {
  editingId.value = row.id
  Object.assign(form, emptyForm(), {
    subject_type: row.subject_type,
    subject_name: row.subject_name,
    partner_type: row.partner_type,
    village_id: row.village_id ?? null,
    school_id: row.school_id ?? null,
    student_name: row.student_name ?? '',
    title: row.title,
    content: row.content ?? '',
    start_date: row.start_date ?? '',
    end_date: row.end_date ?? '',
    status: row.status,
    note: row.note ?? '',
  })
  dialogVisible.value = true
}

function validateForm(): string | null {
  if (!form.subject_name.trim()) return '请填写帮扶主体名称'
  if (!form.title.trim()) return '请填写帮扶事项'
  if (form.partner_type === 'village' && !form.village_id) return '请选择帮扶村'
  if (form.partner_type === 'school' && !form.school_id) return '请选择帮扶学校'
  if (form.partner_type === 'student' && !form.student_name.trim()) return '请填写学生姓名'
  if (form.start_date && form.end_date && form.end_date < form.start_date) {
    return '结束日期不能早于起始日期'
  }
  return null
}

async function handleSubmit() {
  const error = validateForm()
  if (error) {
    ElMessage.warning(error)
    return
  }
  const payload = { ...form }
  saving.value = true
  try {
    if (editingId.value) {
      await updatePairing(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createPairing(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await load()
  } catch {
    ElMessage.error('保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

async function runMutation(action: () => Promise<unknown>, successText: string) {
  try {
    await action()
    ElMessage.success(successText)
    await load()
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  }
}

async function handleDeleteRow(row: PairingItem) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.title}」的结对记录吗？`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  await runMutation(() => deletePairing(row.id), '删除成功')
}

// ==================== 走访台账 ====================

const visitsVisible = ref(false)
const visitsLoading = ref(false)
const visitSaving = ref(false)
const visits = ref<VisitItem[]>([])
const currentPairing = ref<PairingItem | null>(null)
const editingVisitId = ref<number | null>(null)

const visitForm = reactive({
  visit_date: '',
  visitors: '',
  purpose: '',
  content: '',
  materials: '',
})

const visitsTitle = computed(() =>
  currentPairing.value ? `走访台账 · ${currentPairing.value.title}` : '走访台账'
)
const visitSubmitText = computed(() => (editingVisitId.value ? '保存修改' : '登记走访'))

function resetVisitForm() {
  visitForm.visit_date = ''
  visitForm.visitors = ''
  visitForm.purpose = ''
  visitForm.content = ''
  visitForm.materials = ''
  editingVisitId.value = null
}

function openVisits(row: PairingItem) {
  currentPairing.value = row
  resetVisitForm()
  visitsVisible.value = true
  void loadVisits()
}

async function loadVisits() {
  if (!currentPairing.value) return
  visitsLoading.value = true
  try {
    const res = await getVisits(currentPairing.value.id)
    visits.value = res?.items ?? []
  } catch {
    ElMessage.error('加载走访记录失败')
  } finally {
    visitsLoading.value = false
  }
}

function validateVisitForm(): string | null {
  if (!visitForm.visit_date) return '请选择走访日期'
  if (!visitForm.visitors.trim()) return '请填写走访人员'
  return null
}

async function handleVisitSubmit() {
  const error = validateVisitForm()
  if (error) {
    ElMessage.warning(error)
    return
  }
  if (!currentPairing.value) return
  const payload = { ...visitForm }
  visitSaving.value = true
  try {
    if (editingVisitId.value) {
      await updateVisit(currentPairing.value.id, editingVisitId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createVisit(currentPairing.value.id, payload)
      ElMessage.success('登记成功')
    }
    resetVisitForm()
    await loadVisits()
    await load()
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  } finally {
    visitSaving.value = false
  }
}

function handleVisitEdit(row: VisitItem) {
  editingVisitId.value = row.id
  visitForm.visit_date = row.visit_date ?? ''
  visitForm.visitors = row.visitors ?? ''
  visitForm.purpose = row.purpose ?? ''
  visitForm.content = row.content ?? ''
  visitForm.materials = row.materials ?? ''
}

async function handleVisitDelete(row: VisitItem) {
  if (!currentPairing.value) return
  try {
    await ElMessageBox.confirm(`确定删除 ${row.visit_date} 的走访记录吗？`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteVisit(currentPairing.value.id, row.id)
    ElMessage.success('删除成功')
    await loadVisits()
    await load()
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  }
}

onMounted(() => {
  applyQueryPrefill()
  void load()
  void loadOptions()
})
</script>

<style lang="scss" scoped>
.pairing-list {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.page-header h2 {
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.stats-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.f-keyword {
  width: 220px;
}
.f-select {
  width: 140px;
}
.f-partner {
  width: 180px;
}
.partner-scope {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.visit-form {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.form-subject-type,
.form-partner-type {
  width: 160px;
}
.form-subject-name,
.form-title,
.form-note {
  width: 320px;
}
.form-village,
.form-school,
.form-student {
  width: 320px;
}
</style>
