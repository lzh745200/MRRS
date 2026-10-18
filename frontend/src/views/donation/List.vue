<template>
  <div class="donation-list">
    <div class="page-header">
      <h2>捐赠物资台账</h2>
      <div class="header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">登记物资</el-button>
      </div>
    </div>

    <div class="stats-row">
      <el-tag>总数 {{ stats.total }}</el-tag>
      <el-tag type="success">图书 {{ stats.books }}</el-tag>
      <el-tag type="info">设备 {{ stats.equipment }}</el-tag>
      <el-tag type="warning">物资 {{ stats.materials }}</el-tag>
      <el-tag type="danger">折价合计 {{ stats.valuation }} 万元</el-tag>
    </div>

    <el-card>
      <div class="filters">
        <el-input
          v-model="query.keyword"
          placeholder="名称 / 来源单位 / 签收人"
          clearable
          class="f-keyword"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="query.category" placeholder="物资类别" clearable class="f-select">
          <el-option
            v-for="o in DONATION_CATEGORIES"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
        <el-select
          v-model="query.destination_type"
          placeholder="去向类型"
          clearable
          class="f-select"
        >
          <el-option
            v-for="o in DONATION_DESTINATIONS"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <EmptyState v-if="!loading && items.length === 0" description="暂无捐赠物资记录" />
      <template v-else>
        <el-table v-loading="loading" :data="items">
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column label="类别" width="90">
            <template #default="{ row }">
              <el-tag size="small">{{ categoryLabel((row as DonationItem).category) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="110">
            <template #default="{ row }">{{ row.quantity }} {{ row.unit || '' }}</template>
          </el-table-column>
          <el-table-column label="折价(万元)" width="110">
            <template #default="{ row }">{{ row.valuation }}</template>
          </el-table-column>
          <el-table-column prop="source_unit" label="来源单位" min-width="130" />
          <el-table-column label="去向" min-width="150">
            <template #default="{ row }">{{ destinationText(row as DonationItem) }}</template>
          </el-table-column>
          <el-table-column prop="delivery_date" label="交付日期" width="110" />
          <el-table-column prop="receiver" label="签收人" width="100" />
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row as DonationItem)">编辑</el-button>
              <el-button link type="danger" @click="remove(row as DonationItem)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          class="pager"
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :current-page="query.page"
          :page-size="query.page_size"
          :page-sizes="[10, 20, 50]"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </template>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑物资' : '登记物资'" width="640px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" maxlength="200" placeholder="如：课外图书一批" />
        </el-form-item>
        <el-form-item label="类别" prop="category">
          <el-select v-model="form.category" class="w-full">
            <el-option
              v-for="o in DONATION_CATEGORIES"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="form.quantity" :min="0" :precision="2" />
          <el-input v-model="form.unit" placeholder="单位（本/台/件）" class="unit-input" />
        </el-form-item>
        <el-form-item label="折价(万元)" prop="valuation">
          <el-input-number v-model="form.valuation" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="来源单位">
          <el-input v-model="form.source_unit" maxlength="200" />
        </el-form-item>
        <el-form-item label="去向类型" prop="destination_type">
          <el-select
            v-model="form.destination_type"
            class="w-full"
            @change="handleDestinationTypeChange"
          >
            <el-option
              v-for="o in DONATION_DESTINATIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="去向对象" prop="destination_id">
          <el-select
            v-model="form.destination_id"
            filterable
            clearable
            placeholder="选择具体对象"
            class="w-full"
          >
            <el-option v-for="o in destinationOptions" :key="o.id" :label="o.label" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="交付日期">
          <el-date-picker
            v-model="form.delivery_date"
            type="date"
            value-format="YYYY-MM-DD"
            class="w-full"
          />
        </el-form-item>
        <el-form-item label="签收人">
          <el-input v-model="form.receiver" maxlength="100" />
        </el-form-item>
        <el-form-item label="附件链接">
          <el-input
            v-model="form.attachment_text"
            type="textarea"
            :rows="2"
            placeholder="每行一个附件链接（可选）"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { schoolsApi } from '@/api/schools'
import { projectsApi } from '@/api/projects'
import { getSupportedVillages } from '@/api/supportedVillage'
import {
  DONATION_CATEGORIES,
  DONATION_DESTINATIONS,
  createDonation,
  deleteDonation,
  getDonationStats,
  getDonations,
  updateDonation,
} from '@/api/donations'
import type { DonationItem, DonationPayload, DonationStats } from '@/api/donations'

interface Option {
  id: number
  label: string
}

interface DonationForm {
  name: string
  category: string
  quantity: number
  unit: string
  valuation: number
  source_unit: string
  destination_type: string
  destination_id: number | null
  delivery_date: string
  receiver: string
  attachment_text: string
  remark: string
}

const EMPTY_STATS: DonationStats = {
  total: 0,
  villages: 0,
  schools: 0,
  projects: 0,
  books: 0,
  equipment: 0,
  materials: 0,
  quantity: 0,
  valuation: 0,
}

const loading = ref(false)
const saving = ref(false)
const items = ref<DonationItem[]>([])
const total = ref(0)
const stats = ref<DonationStats>({ ...EMPTY_STATS })
const villages = ref<Option[]>([])
const schools = ref<Option[]>([])
const projects = ref<Option[]>([])

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  category: '',
  destination_type: '',
})

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

function emptyForm(): DonationForm {
  return {
    name: '',
    category: 'material',
    quantity: 0,
    unit: '',
    valuation: 0,
    source_unit: '',
    destination_type: 'village',
    destination_id: null,
    delivery_date: '',
    receiver: '',
    attachment_text: '',
    remark: '',
  }
}

const form = reactive<DonationForm>(emptyForm())

/** 表单校验（与后端 ensure_donation_valid 口径一致；返回错误文案或 null） */
function validateForm(): string | null {
  if (!form.name.trim()) return '请填写名称'
  if (!form.category) return '请选择类别'
  if (!Number.isFinite(form.quantity) || form.quantity < 0) return '数量不能为负数'
  if (!Number.isFinite(form.valuation) || form.valuation < 0) return '折价不能为负数'
  if (!form.destination_type) return '请选择去向类型'
  if (!form.destination_id) return '请选择去向对象'
  return null
}

/** 当前去向类型可选对象（类型切换后自动清空已选 id） */
const destinationOptions = computed<Option[]>(() => {
  if (form.destination_type === 'village') return villages.value
  if (form.destination_type === 'school') return schools.value
  return projects.value
})

function labelOf(options: readonly { value: string; label: string }[], value: string): string {
  return options.find((o) => o.value === value)?.label || value || '-'
}

function categoryLabel(value: string): string {
  return labelOf(DONATION_CATEGORIES, value)
}

function destinationTypeLabel(value: string): string {
  return labelOf(DONATION_DESTINATIONS, value)
}

function destinationText(row: DonationItem): string {
  const typeLabel = destinationTypeLabel(row.destination_type)
  return row.destination_name ? `${typeLabel}：${row.destination_name}` : typeLabel
}

async function load() {
  loading.value = true
  try {
    const [listRes, statsRes] = await Promise.all([
      getDonations({
        ...query,
        keyword: query.keyword || undefined,
        category: query.category || undefined,
        destination_type: query.destination_type || undefined,
      }),
      getDonationStats(),
    ])
    items.value = listRes?.items ?? []
    total.value = listRes?.total ?? 0
    stats.value = statsRes ? { ...EMPTY_STATS, ...statsRes } : { ...EMPTY_STATS }
  } catch {
    ElMessage.error('加载捐赠物资台账失败')
  } finally {
    loading.value = false
  }
}

async function handleSearch() {
  query.page = 1
  await load()
}

async function handleReset() {
  query.keyword = ''
  query.category = ''
  query.destination_type = ''
  query.page = 1
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

async function loadOptions() {
  try {
    const [villageRes, schoolRes, projectRes] = await Promise.all([
      getSupportedVillages({ page: 1, page_size: 200 }),
      schoolsApi.list({ page: 1, page_size: 200 }),
      projectsApi.list({ page: 1, page_size: 200 }),
    ])
    villages.value = (villageRes?.items ?? []).map((v: any) => ({
      id: v.id,
      label: v.village_name || v.name || `村#${v.id}`,
    }))
    schools.value = (schoolRes?.items ?? []).map((s: any) => ({
      id: s.id,
      label: s.name || s.school_name || `学校#${s.id}`,
    }))
    projects.value = (projectRes?.items ?? []).map((p: any) => ({
      id: p.id,
      label: p.name || p.project_name || `项目#${p.id}`,
    }))
  } catch {
    ElMessage.error('加载去向对象选项失败')
  }
}

function handleDestinationTypeChange() {
  form.destination_id = null
}

function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row: DonationItem) {
  editingId.value = row.id
  const destinationId =
    row.destination_type === 'village'
      ? row.village_id
      : row.destination_type === 'school'
        ? row.school_id
        : row.project_id
  Object.assign(form, emptyForm(), {
    name: row.name,
    category: row.category,
    quantity: row.quantity,
    unit: row.unit || '',
    valuation: row.valuation,
    source_unit: row.source_unit || '',
    destination_type: row.destination_type,
    destination_id: destinationId ?? null,
    delivery_date: row.delivery_date || '',
    receiver: row.receiver || '',
    attachment_text: (row.attachments || []).map((a) => a.url).join('\n'),
    remark: row.remark || '',
  })
  dialogVisible.value = true
}

function buildPayload(): DonationPayload {
  const urls = form.attachment_text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  const payload: DonationPayload = {
    name: form.name,
    category: form.category,
    quantity: form.quantity,
    unit: form.unit || null,
    valuation: form.valuation,
    source_unit: form.source_unit || null,
    destination_type: form.destination_type,
    delivery_date: form.delivery_date || null,
    receiver: form.receiver || null,
    attachments: urls.length
      ? urls.map((url) => ({ url, file_name: url.split('/').pop() || null }))
      : null,
    remark: form.remark || null,
  }
  if (form.destination_type === 'village') payload.village_id = form.destination_id
  if (form.destination_type === 'school') payload.school_id = form.destination_id
  if (form.destination_type === 'project') payload.project_id = form.destination_id
  return payload
}

async function submit() {
  const errorText = validateForm()
  if (errorText) {
    ElMessage.error(errorText)
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateDonation(editingId.value, buildPayload())
      ElMessage.success('已更新')
    } else {
      await createDonation(buildPayload())
      ElMessage.success('已登记')
    }
    dialogVisible.value = false
    await load()
  } catch {
    ElMessage.error('保存失败，请检查填写内容')
  } finally {
    saving.value = false
  }
}

async function remove(row: DonationItem) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.name}」？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteDonation(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(async () => {
  await Promise.all([load(), loadOptions()])
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.stats-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.f-keyword {
  width: 240px;
}
.f-select {
  width: 150px;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.w-full {
  width: 100%;
}
.unit-input {
  width: 150px;
  margin-left: 8px;
}
</style>
