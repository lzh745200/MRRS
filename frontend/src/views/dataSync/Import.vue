<template>
  <div class="data-sync-import">
    <el-card class="page-header">
      <div class="header-content">
        <h2>数据导入</h2>
        <p class="description">导入其他电脑导出的数据包</p>
      </div>
    </el-card>

    <!-- 导入配置 -->
    <el-card class="import-config">
      <h3 class="section-title">导入数据包</h3>
      <el-form :model="importForm" label-width="120px">
        <el-form-item label="选择数据包">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".zip,.rrs"
            :on-change="handleFileChange"
            :file-list="fileList"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 .zip（旧版）和 .rrs（加密）格式的数据包文件</div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item v-if="isEncryptedFile" label="解密密码" required>
          <el-input
            v-model="importForm.password"
            type="password"
            placeholder="输入导出时设置的密码"
            show-password
          />
        </el-form-item>

        <el-form-item label="冲突策略">
          <el-radio-group v-model="importForm.strategy">
            <el-radio value="merge">智能合并（推荐）</el-radio>
            <el-radio value="skip">跳过冲突记录</el-radio>
            <el-radio value="overwrite">覆盖本地数据</el-radio>
          </el-radio-group>
          <div class="form-tip">
            <div>智能合并: 根据时间戳自动选择最新数据</div>
            <div>跳过: 保留本地数据,不导入冲突记录</div>
            <div>覆盖: 使用导入数据覆盖本地数据</div>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="importing"
            :disabled="!selectedFile"
            @click="handleImport"
          >
            开始导入
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 导入结果 -->
    <el-card v-if="importResult" class="import-result">
      <h3 class="section-title">导入结果</h3>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="数据包名称">
          {{ importResult.package_name }}
        </el-descriptions-item>
        <el-descriptions-item label="导入时间">
          {{ formatDate(importResult.imported_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="总记录数">
          {{ importResult.total_records }}
        </el-descriptions-item>
        <el-descriptions-item label="成功记录数">
          <el-tag type="success">{{ importResult.success_records }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="新增记录">
          <el-tag type="primary">{{ importResult.inserted_count || 0 }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="更新记录">
          <el-tag type="warning">{{ importResult.updated_count || 0 }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="跳过记录">
          <el-tag type="info">{{ importResult.skipped_count || 0 }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="失败记录数">
          <el-tag v-if="importResult.failed_records > 0" type="danger">
            {{ importResult.failed_records }}
          </el-tag>
          <span v-else>0</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 冲突列表 -->
      <div v-if="importResult.conflicts.length > 0" class="conflicts-section">
        <h4>冲突记录</h4>
        <el-button type="primary" size="small" @click="showConflicts"> 查看并解决冲突 </el-button>
      </div>

      <!-- 错误列表 -->
      <div v-if="importResult.errors.length > 0" class="errors-section">
        <h4>错误信息</h4>
        <el-alert
          v-for="(error, index) in importResult.errors"
          :key="index"
          :title="error"
          type="error"
          :closable="false"
          style="margin-bottom: 10px"
        />
      </div>
    </el-card>

    <!-- 导入历史 -->
    <el-card class="import-history">
      <h3 class="section-title">导入历史</h3>
      <el-table :data="importHistory" style="width: 100%">
        <el-table-column prop="package_name" label="数据包名称" />
        <el-table-column prop="total_records" label="总记录数" width="100" />
        <el-table-column prop="success_records" label="成功" width="80">
          <template #default="{ row }">
            <el-tag type="success" size="small">{{ row.success_records }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="failed_records" label="失败" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.failed_records > 0" type="danger" size="small">
              {{ row.failed_records }}
            </el-tag>
            <span v-else>0</span>
          </template>
        </el-table-column>
        <el-table-column prop="conflicts_count" label="冲突" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.conflicts_count > 0" type="warning" size="small">
              {{ row.conflicts_count }}
            </el-tag>
            <span v-else>0</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="导入时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="user_name" label="操作人" width="120" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage } from 'element-plus'
import { logger } from '@/utils/logger'
import { importData, importEncryptedData, getSyncLogs } from '@/api/dataSync'
import type { UploadFile } from 'element-plus'

const { pushSafe } = useRouterSafe()

const importForm = ref({
  strategy: 'merge' as 'skip' | 'overwrite' | 'merge',
  password: '',
})

const importing = ref(false)
const selectedFile = ref<File | null>(null)
const fileList = ref<UploadFile[]>([])
const importResult = ref<any>(null)
const importHistory = ref<any[]>([])

const isEncryptedFile = computed(() => {
  if (!selectedFile.value) return false
  return selectedFile.value.name.endsWith('.rrs')
})

const handleFileChange = (file: UploadFile) => {
  if (file.raw) {
    selectedFile.value = file.raw
  }
}

const handleImport = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择要导入的数据包')
    return
  }

  if (isEncryptedFile.value && !importForm.value.password) {
    ElMessage.warning('请输入解密密码')
    return
  }

  importing.value = true
  importResult.value = null

  try {
    let response

    if (isEncryptedFile.value) {
      // 加密文件导入（importEncryptedData 签名: file, password 位置参数）
      response = await importEncryptedData(
        selectedFile.value,
        importForm.value.password || ''
      )
    } else {
      // 旧版文件导入
      response = await importData(selectedFile.value, importForm.value.strategy)
    }

    // post() 已自动解包，后端裸返回 {success, total_records, ...}
    const result = response?.data ?? response
    importResult.value = result

    if (result?.success) {
      const stats = [
        `成功 ${result.success_records ?? 0} 条`,
        `失败 ${result.failed_records ?? 0} 条`,
      ]
      if (result.inserted_count !== undefined) {
        stats.push(`新增 ${result.inserted_count} 条`)
      }
      if (result.updated_count !== undefined) {
        stats.push(`更新 ${result.updated_count} 条`)
      }
      if (result.skipped_count !== undefined) {
        stats.push(`跳过 ${result.skipped_count} 条`)
      }

      ElMessage.success(`导入成功! ${stats.join(', ')}`)
      // 刷新历史
      await loadImportHistory()
      // 清空密码
      importForm.value.password = ''
    } else if (result?.message) {
      ElMessage.warning(result.message)
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '导入失败')
  } finally {
    importing.value = false
  }
}

const showConflicts = () => {
  const conflicts = importResult.value?.conflicts
  if (Array.isArray(conflicts) && conflicts.length > 0) {
    // 跳转到冲突解决页面
    pushSafe({
      name: 'DataSyncConflicts',
      query: { syncLogId: importResult.value.sync_log_id.toString() },
    })
  } else {
    ElMessage.info('没有需要解决的冲突')
  }
}

const loadImportHistory = async () => {
  try {
    const response: any = await getSyncLogs({ action: 'import', page: 1, page_size: 20 })
    // 后端 ok_list 信封 → items 已在顶层
    const list = response?.items || response?.data?.items || []
    importHistory.value = Array.isArray(list) ? list : []
  } catch (error) {
    logger.error('加载导入历史失败', error)
  }
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadImportHistory()
})
</script>

<style scoped lang="scss">
.data-sync-import {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;

  .header-content {
    h2 {
      margin: 0 0 8px 0;
      font-size: 24px;
      color: #303133;
    }

    .description {
      margin: 0;
      color: #909399;
      font-size: 14px;
    }
  }
}

.import-config,
.import-result,
.import-history {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #303133;
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 10px;
}

.form-tip {
  margin-top: 5px;
  font-size: 12px;
  color: #909399;

  div {
    margin-top: 3px;
  }
}

.conflicts-section,
.errors-section {
  margin-top: 20px;

  h4 {
    margin: 0 0 10px 0;
    font-size: 16px;
    color: #303133;
  }
}
</style>
