<template>
  <div class="policy-detail">
    <el-card v-loading="loading">
      <template #header>
        <div class="detail-header">
          <span class="title">{{ policy?.title || '政策详情' }}</span>
          <div class="header-actions">
            <el-button size="small" @click="goBack">返回</el-button>
            <el-button v-if="policy && canEdit" size="small" type="primary" @click="goEdit"
              >编辑</el-button
            >
            <el-button
              v-if="canEdit && policy?.status === 'draft'"
              size="small"
              type="success"
              @click="handlePublish"
              >发布</el-button
            >
            <el-button
              v-if="canEdit && policy?.status === 'active'"
              size="small"
              type="warning"
              @click="handleArchive"
              >归档</el-button
            >
            <el-button
              v-if="policy"
              size="small"
              :type="isFavorite ? 'danger' : 'default'"
              @click="toggleFavorite"
            >
              {{ isFavorite ? '已收藏' : '收藏' }}
            </el-button>
          </div>
        </div>
      </template>

      <el-descriptions v-if="policy" :column="2" border>
        <el-descriptions-item label="标题">{{ policy.title }}</el-descriptions-item>
        <el-descriptions-item label="分类">{{
          getCategoryLabel(policy.category)
        }}</el-descriptions-item>
        <el-descriptions-item label="级别">{{ getLevelLabel(policy.level) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusColor(policy.status) as any" size="small">{{
            getStatusLabel(policy.status)
          }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="生效日期">{{
          policy.effective_date || '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="失效日期">{{
          policy.expiry_date || '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ policy.created_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ policy.updated_at || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 政策正文 -->
    <el-card v-if="policy?.content" class="content-card">
      <template #header><span>政策内容</span></template>
      <!-- 已净化（sanitizedPolicyContent 经 sanitizeHtml）：v-html 渲染安全 -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="policy-content" v-html="sanitizedPolicyContent"></div>
    </el-card>

    <!-- 文件操作 -->
    <el-card class="file-card">
      <template #header><span>附件操作</span></template>
      <el-space>
        <el-button :loading="previewLoading" @click="handlePreview">预览文件</el-button>
        <el-button type="primary" @click="handleDownload">下载文件</el-button>
      </el-space>
      <div v-if="previewUrl" class="preview-area">
        <iframe :src="previewUrl" class="preview-frame" />
      </div>
    </el-card>

    <!-- 相关政策 -->
    <el-card v-if="relatedPolicies.length" class="related-card">
      <template #header><span>相关政策</span></template>
      <el-table :data="relatedPolicies" stripe size="small">
        <el-table-column prop="title" label="标题" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="goDetail(row.id)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">{{ getCategoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusColor(row.status) as any" size="small">{{
              getStatusLabel(row.status)
            }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage, ElMessageBox } from 'element-plus'
import { sanitizeHtml } from '@/utils/sanitize'
import {
  getPolicy,
  publishPolicy,
  archivePolicy,
  previewPolicyFile,
  downloadPolicyFile,
  addPolicyFavorite,
  removePolicyFavorite,
  getPolicyRelated,
  getCategoryLabel,
  getLevelLabel,
  getStatusLabel,
  getStatusColor,
  type Policy,
} from '@/api/policy'
import { downloadBlob } from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import { ADMIN_ROLES, normalizeRole } from '@/utils/roleAccess'

const route = useRoute()
const { pushSafe } = useRouterSafe()

// 政策写操作（编辑/发布/归档）仅管理员可见，与 List.vue canEdit 规则一致
const authStore = useAuthStore()
const canEdit = computed(() => {
  const user = authStore.user
  if (!user) return false
  if (user.is_superuser) return true
  const role = normalizeRole(user.role)
  return ADMIN_ROLES.includes(role)
})
const policy = ref<Policy | null>(null)
// 净化后内容（v-html 渲染前必须 sanitize，防 XSS）
const sanitizedPolicyContent = computed(() =>
  policy.value?.content ? sanitizeHtml(policy.value.content) : ''
)
const loading = ref(false)
const previewLoading = ref(false)
const previewUrl = ref('')
const isFavorite = ref(false)
const relatedPolicies = ref<any[]>([])

const policyId = Number(route.params.id)

async function loadData() {
  if (!policyId) return
  loading.value = true
  try {
    policy.value = await getPolicy(policyId)
    loadRelated()
  } catch {
    ElMessage.error('加载政策详情失败')
  } finally {
    loading.value = false
  }
}

async function loadRelated() {
  try {
    const res = await getPolicyRelated(policyId)
    relatedPolicies.value = Array.isArray(res) ? res : ((res as any)?.items ?? [])
  } catch {
    relatedPolicies.value = []
  }
}

function goBack() {
  pushSafe('/policies')
}

function goEdit() {
  pushSafe(`/policies/${policyId}/edit`)
}

function goDetail(id: number) {
  pushSafe(`/policies/${id}`)
}

async function handlePublish() {
  try {
    await ElMessageBox.confirm('确定发布该政策？发布后将对所有用户可见。', '确认发布')
    await publishPolicy(policyId)
    ElMessage.success('发布成功')
    loadData()
  } catch {
    // cancelled
  }
}

async function handleArchive() {
  try {
    await ElMessageBox.confirm('确定归档该政策？归档后将不再显示为有效状态。', '确认归档')
    await archivePolicy(policyId)
    ElMessage.success('归档成功')
    loadData()
  } catch {
    // cancelled
  }
}

async function toggleFavorite() {
  try {
    if (isFavorite.value) {
      await removePolicyFavorite(policyId)
      isFavorite.value = false
      ElMessage.success('已取消收藏')
    } else {
      await addPolicyFavorite(policyId)
      isFavorite.value = true
      ElMessage.success('已收藏')
    }
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handlePreview() {
  previewLoading.value = true
  try {
    const blob = (await previewPolicyFile(policyId)) as Blob
    if (!blob || blob.size === 0) {
      ElMessage.info('暂无可预览的文件')
      return
    }
    // 释放上一个预览 Blob URL
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value)
      previewUrl.value = ''
    }
    const type = blob.type || ''
    // 图片 / PDF / HTML（正文或 mammoth 转换结果）可直接 iframe 预览
    if (type.startsWith('image/') || type === 'application/pdf' || type.includes('html')) {
      previewUrl.value = URL.createObjectURL(blob)
    } else {
      // Office 等其他类型不支持在线预览 → 提示并直接下载
      const ext = (policy.value?.fileType as string) || (policy.value as any)?.file_type || 'file'
      downloadBlob(blob, `${policy.value?.title || '政策文件'}.${ext}`)
      ElMessage.info('该文件类型不支持在线预览，已为您下载')
    }
  } catch {
    ElMessage.warning('该政策暂无附件')
  } finally {
    previewLoading.value = false
  }
}

async function handleDownload() {
  try {
    const blob = (await downloadPolicyFile(policyId)) as Blob
    const ext = (policy.value?.fileType as string) || (policy.value as any)?.file_type || 'file'
    downloadBlob(blob, `${policy.value?.title || '政策文件'}.${ext}`)
  } catch {
    ElMessage.warning('该政策暂无附件')
  }
}

onMounted(loadData)
</script>

<style scoped>
.policy-detail {
  padding: 0;
}
.policy-detail > .el-card + .el-card {
  margin-top: 16px;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.detail-header .title {
  font-size: 18px;
  font-weight: 600;
}
.policy-content {
  line-height: 1.8;
  font-size: 15px;
  min-height: 100px;
}
.preview-area {
  margin-top: 16px;
}
.preview-frame {
  width: 100%;
  height: 500px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}
</style>
