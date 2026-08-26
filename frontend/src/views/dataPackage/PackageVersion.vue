<template>
  <div class="package-version">
    <el-alert
      title="该功能正在开发中"
      description="数据包版本管理的后端接口尚未实现，当前页面操作暂不可用。如有紧急需求请联系开发团队。"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据包版本管理</span>
          <el-button type="primary" disabled @click="handleCreateVersion"> 创建新版本 </el-button>
        </div>
      </template>

      <!-- 版本列表 -->
      <el-table :data="versionList" style="width: 100%">
        <el-table-column prop="version" label="版本号" width="120" />
        <el-table-column prop="description" label="版本说明" />
        <el-table-column label="变更统计" width="200">
          <template #default="{ row }">
            <el-tag type="success" size="small" style="margin-right: 5px">
              新增: {{ getChangeCount(row.changes, 'added') }}
            </el-tag>
            <el-tag type="warning" size="small" style="margin-right: 5px">
              修改: {{ getChangeCount(row.changes, 'modified') }}
            </el-tag>
            <el-tag type="danger" size="small">
              删除: {{ getChangeCount(row.changes, 'deleted') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button size="small" @click="handleViewDetail(row as VersionItem)"> 详情 </el-button>
            <el-button
              size="small"
              type="primary"
              :disabled="versionList.length < 2"
              @click="handleCompare(row as VersionItem)"
            >
              对比
            </el-button>
            <el-button size="small" type="danger" disabled @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建版本对话框 -->
    <el-dialog v-model="createDialogVisible" title="创建新版本" :width="DIALOG_SM">
      <el-form :model="versionForm" label-width="100px">
        <el-form-item label="版本号" required>
          <el-input v-model="versionForm.version" placeholder="如: 1.1, 2.0" />
        </el-form-item>
        <el-form-item label="版本说明">
          <el-input
            v-model="versionForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入版本说明"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="confirmCreate"> 确定 </el-button>
      </template>
    </el-dialog>

    <!-- 版本详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="版本详情" :width="DIALOG_LG">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="版本号">
          {{ currentVersion.version }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatTime(currentVersion.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="版本说明" :span="2">
          {{ currentVersion.description || '-' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-divider>变更详情</el-divider>

      <el-tabs v-model="activeTab">
        <el-tab-pane
          v-for="(changes, dataType) in currentVersion.changes"
          :key="dataType"
          :label="String(dataType)"
          :name="dataType"
        >
          <el-descriptions :column="3" border>
            <el-descriptions-item label="新增">
              {{ changes.added?.length || 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="修改">
              {{ changes.modified?.length || 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="删除">
              {{ changes.deleted?.length || 0 }}
            </el-descriptions-item>
          </el-descriptions>

          <div v-if="changes.added?.length" style="margin-top: 20px">
            <h4>新增记录ID:</h4>
            <el-tag v-for="id in changes.added" :key="id" type="success" style="margin: 5px">
              {{ id }}
            </el-tag>
          </div>

          <div v-if="changes.modified?.length" style="margin-top: 20px">
            <h4>修改记录ID:</h4>
            <el-tag v-for="id in changes.modified" :key="id" type="warning" style="margin: 5px">
              {{ id }}
            </el-tag>
          </div>

          <div v-if="changes.deleted?.length" style="margin-top: 20px">
            <h4>删除记录ID:</h4>
            <el-tag v-for="id in changes.deleted" :key="id" type="danger" style="margin: 5px">
              {{ id }}
            </el-tag>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 版本对比对话框 -->
    <el-dialog v-model="compareDialogVisible" title="版本对比" :width="DIALOG_LG">
      <el-form :inline="true">
        <el-form-item label="版本1">
          <el-select v-model="compareForm.version1" placeholder="选择版本">
            <el-option
              v-for="v in versionList"
              :key="v.version"
              :label="v.version"
              :value="v.version"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="版本2">
          <el-select v-model="compareForm.version2" placeholder="选择版本">
            <el-option
              v-for="v in versionList"
              :key="v.version"
              :label="v.version"
              :value="v.version"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" disabled @click="doCompare">对比</el-button>
        </el-form-item>
      </el-form>

      <div v-if="compareResult" style="margin-top: 20px">
        <el-alert title="对比结果" type="info" :closable="false" style="margin-bottom: 20px" />

        <el-descriptions :column="2" border>
          <el-descriptions-item label="版本1">
            {{ compareResult.version1.version }}
          </el-descriptions-item>
          <el-descriptions-item label="版本2">
            {{ compareResult.version2.version }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider>差异详情</el-divider>

        <el-tabs>
          <el-tab-pane
            v-for="(diff, dataType) in compareResult.differences.added_in_v2"
            :key="dataType"
            :label="dataType"
          >
            <el-descriptions :column="3" border>
              <el-descriptions-item label="新增">
                {{ diff.length }}
              </el-descriptions-item>
              <el-descriptions-item label="修改">
                {{ compareResult.differences.modified[dataType]?.length || 0 }}
              </el-descriptions-item>
              <el-descriptions-item label="删除">
                {{ compareResult.differences.removed_in_v2[dataType]?.length || 0 }}
              </el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM, DIALOG_LG } from '@/config/dialog'
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import { get, post, del, apiRequest } from '@/api/request'
import { handleApiError } from '@/utils/errorHandler'
import { format } from '@/utils'

const route = useRoute()
const packageId = ref(route.params.id)

interface VersionChanges {
  [dataType: string]: {
    added?: (string | number)[]
    modified?: (string | number)[]
    deleted?: (string | number)[]
  }
}

interface VersionItem {
  id: number | string
  version: string
  description: string
  created_at: string
  changes: VersionChanges
}

interface CompareResult {
  version1: { version: string }
  version2: { version: string }
  differences: {
    added_in_v2: Record<string, (string | number)[]>
    modified: Record<string, (string | number)[]>
    removed_in_v2: Record<string, (string | number)[]>
  }
}

const versionList = ref<VersionItem[]>([])
const createDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const compareDialogVisible = ref(false)
const loading = ref(false)
const activeTab = ref('')

const versionForm = ref({
  version: '',
  description: '',
})

const currentVersion = ref<VersionItem>({
  id: 0,
  version: '',
  description: '',
  created_at: '',
  changes: {},
})

const compareForm = ref({
  version1: '',
  version2: '',
})

const compareResult = ref<CompareResult | null>(null)

// 获取版本列表
const fetchVersionList = async () => {
  try {
    const response: any = await get(`/data-packages/${packageId.value}/versions`)
    // 后端裸返回 {versions, total}
    const versions = response?.versions || response?.data?.versions || []
    versionList.value = Array.isArray(versions) ? versions : []
  } catch {
    ElMessage.error('获取版本列表失败')
  }
}

// 创建版本
const handleCreateVersion = () => {
  versionForm.value = { version: '', description: '' }
  createDialogVisible.value = true
}

const confirmCreate = async () => {
  if (!versionForm.value.version) {
    ElMessage.warning('请输入版本号')
    return
  }

  loading.value = true
  try {
    const response = await post(`/data-packages/${packageId.value}/versions`, versionForm.value)

    if (response.success) {
      ElMessage.success('版本创建成功')
      createDialogVisible.value = false
      fetchVersionList()
    }
  } catch (error: unknown) {
    handleApiError(error, '创建失败')
  } finally {
    loading.value = false
  }
}

// 查看详情
const handleViewDetail = async (version: VersionItem) => {
  try {
    const response = await get(`/data-packages/${packageId.value}/versions/${version.id}`)

    if (response.success) {
      currentVersion.value = response.data
      if (Object.keys(currentVersion.value.changes).length > 0) {
        activeTab.value = Object.keys(currentVersion.value.changes)[0]
      }
      detailDialogVisible.value = true
    }
  } catch (error) {
    ElMessage.error('获取版本详情失败')
  }
}

// 对比版本
const handleCompare = (version: VersionItem) => {
  compareForm.value.version1 = version.version
  compareForm.value.version2 = ''
  compareResult.value = null
  compareDialogVisible.value = true
}

const doCompare = async () => {
  if (!compareForm.value.version1 || !compareForm.value.version2) {
    ElMessage.warning('请选择两个版本')
    return
  }

  try {
    const response = await apiRequest({
      method: 'GET',
      url: `/data-packages/${packageId.value}/versions/compare`,
      params: {
        version1: compareForm.value.version1,
        version2: compareForm.value.version2,
      },
    })

    if (response.success) {
      compareResult.value = response.data.comparison
    }
  } catch (error: unknown) {
    handleApiError(error, '对比失败')
  }
}

// 删除版本
const handleDelete = async (versionId: number | string) => {
  try {
    await ElMessageBox.confirm('确定要删除此版本吗？', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    const response = await del(`/data-packages/${packageId.value}/versions/${versionId}`)

    if (response.success) {
      ElMessage.success('删除成功')
      fetchVersionList()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 获取变更数量
const getChangeCount = (
  changes: VersionChanges | undefined,
  type: 'added' | 'modified' | 'deleted'
) => {
  if (!changes) return 0
  let total = 0
  for (const dataType in changes) {
    total += changes[dataType][type]?.length || 0
  }
  return total
}

// 格式化时间
const formatTime = (time: string | undefined) => format.formatDateTimeLocale(time || '')

onMounted(() => {
  fetchVersionList()
})
</script>

<style scoped>
.package-version {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
