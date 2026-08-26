<template>
  <div class="org-module-policy">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>模块策略配置</span>
          <div>
            <el-select
              v-model="selectedOrgId"
              placeholder="选择下级组织"
              style="width: 200px; margin-right: 12px"
              @change="loadPolicies"
            >
              <el-option v-for="org in orgs" :key="org.id" :label="org.name" :value="org.id" />
            </el-select>
            <el-button
              type="primary"
              :disabled="!selectedOrgId"
              :loading="saving"
              @click="handleSave"
              >保存策略</el-button
            >
          </div>
        </div>
      </template>

      <el-alert
        v-if="!selectedOrgId"
        type="info"
        :closable="false"
        title="请先选择要配置的下级组织"
        style="margin-bottom: 16px"
      />

      <el-table v-else v-loading="loading" :data="policies">
        <el-table-column prop="name" label="模块名称" width="140" />
        <el-table-column prop="category" label="分类" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ categoryLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="可见性" width="160">
          <template #default="{ row }">
            <el-switch
              v-model="row.visibility"
              active-value="visible"
              inactive-value="hidden"
              active-text="可见"
              inactive-text="隐藏"
            />
          </template>
        </el-table-column>
        <el-table-column label="编辑模式" min-width="200">
          <template #default="{ row }">
            <el-radio-group v-model="row.edit_mode" size="small">
              <el-radio-button value="full_edit">完全编辑</el-radio-button>
              <el-radio-button value="read_only">只读</el-radio-button>
              <el-radio-button value="disabled">禁用</el-radio-button>
            </el-radio-group>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_custom" size="small" type="warning">自定义</el-tag>
            <el-tag v-else size="small" type="info">默认</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { get, put } from '@/api/request'

interface PolicyRow {
  key: string
  name: string
  category: string
  visibility: string
  edit_mode: string
  is_custom: boolean
}

interface OrgOption {
  id: number
  name: string
}

const orgs = ref<OrgOption[]>([])
const selectedOrgId = ref<number | null>(null)
const policies = ref<PolicyRow[]>([])
const loading = ref(false)
const saving = ref(false)

function categoryLabel(cat: string) {
  const map: Record<string, string> = {
    core: '核心',
    business: '业务',
    analysis: '分析',
    data: '数据',
    system: '系统',
  }
  return map[cat] || cat
}

async function loadOrgs() {
  try {
    const res = await get('/organizations', { page_size: 100 })
    const data = res.data || res
    orgs.value = (data.items || []).map((o: Record<string, unknown>) => ({
      id: o.id as number,
      name: o.name as string,
    }))
  } catch {
    // 静默失败
  }
}

async function loadPolicies() {
  if (!selectedOrgId.value) return
  loading.value = true
  try {
    const res = await get(`/org-policies/${selectedOrgId.value}`)
    policies.value = res.data || res || []
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载策略失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!selectedOrgId.value) return
  saving.value = true
  try {
    await put(`/org-policies/${selectedOrgId.value}`, {
      policies: policies.value.map((p) => ({
        module_key: p.key,
        visibility: p.visibility,
        edit_mode: p.edit_mode,
      })),
    })
    ElMessage.success('模块策略已保存')
    await loadPolicies()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadOrgs)
</script>

<style scoped>
.org-module-policy {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
