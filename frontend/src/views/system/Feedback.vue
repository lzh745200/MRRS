<template>
  <div class="feedback-page">
    <el-card class="search-card">
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="反馈类型">
          <el-select
            v-model="searchForm.type"
            placeholder="请选择反馈类型"
            clearable
            style="width: 140px"
          >
            <el-option label="Bug反馈" value="bug" />
            <el-option label="功能建议" value="suggestion" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <span class="title">意见反馈列表</span>
          <el-tag type="info">共 {{ pagination.total }} 条</el-tag>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe border>
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="type" label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="typeTagMap[row.type] || 'info'" size="small">
              {{ typeNameMap[row.type] || row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="反馈内容" min-width="300" show-overflow-tooltip />
        <el-table-column prop="username" label="提交用户" width="120">
          <template #default="{ row }">
            {{ row.username || '匿名' }}
          </template>
        </el-table-column>
        <el-table-column prop="contact" label="联系方式" width="150">
          <template #default="{ row }">
            {{ row.contact ? ds(row.contact, 'email') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="180" />
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, prev, pager, next"
        class="pagination"
        @current-change="loadData"
      />
    </el-card>

    <!-- 反馈详情 -->
    <el-dialog v-model="detailVisible" append-to-body title="反馈详情" :width="DIALOG_MD">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="类型">{{
          typeNameMap[currentItem?.type]
        }}</el-descriptions-item>
        <el-descriptions-item label="内容">{{ currentItem?.content }}</el-descriptions-item>
        <el-descriptions-item label="用户">{{
          currentItem?.username || '匿名'
        }}</el-descriptions-item>
        <el-descriptions-item label="联系方式">{{
          currentItem?.contact ? ds(currentItem.contact, 'email') : '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ currentItem?.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_MD } from '@/config/dialog'
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '@/api/request'
import { useDesensitize } from '@/composables/useDesensitize'

const { ds } = useDesensitize()

const loading = ref(false)
const tableData = ref<any[]>([])
const detailVisible = ref(false)
const currentItem = ref<any>(null)

const searchForm = reactive({ type: undefined as string | undefined })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const typeNameMap: Record<string, string> = {
  bug: 'Bug反馈',
  suggestion: '功能建议',
  other: '其他',
}
type TagType = 'info' | 'primary' | 'success' | 'warning' | 'danger'
const typeTagMap: Record<string, TagType> = {
  bug: 'danger',
  suggestion: 'warning',
  other: 'info',
}

async function loadData() {
  loading.value = true
  try {
    const { data } = await apiRequest({
      method: 'GET',
      url: '/feedback',
      params: {
        page: pagination.page,
        page_size: pagination.pageSize,
        type: searchForm.type,
      },
    })
    if (data?.data) {
      tableData.value = data.data.items || []
      pagination.total = data.data.total || 0
    }
  } catch (e: any) {
    tableData.value = []
    pagination.total = 0
    ElMessage.error('加载反馈列表失败')
  } finally {
    loading.value = false
  }
}

function handleReset() {
  searchForm.type = undefined
  pagination.page = 1
  loadData()
}

onMounted(() => loadData())
</script>

<style lang="scss" scoped>
.feedback-page {
  padding: 20px;
}
.search-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
