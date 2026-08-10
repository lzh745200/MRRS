<template>
  <div class="organization-detail">
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom: 16px">
      <el-breadcrumb-item :to="{ path: '/organizations' }">组织管理</el-breadcrumb-item>
      <el-breadcrumb-item v-for="a in detail.ancestors" :key="a.id">
        {{ a.name }}
      </el-breadcrumb-item>
      <el-breadcrumb-item>{{ detail.name }}</el-breadcrumb-item>
    </el-breadcrumb>

    <el-row :gutter="20">
      <!-- 左侧：基本信息 -->
      <el-col :span="16">
        <el-card v-loading="loading" class="detail-card">
          <template #header>
            <div class="card-header">
              <span class="title">组织详情</span>
              <div class="actions">
                <el-button type="primary" @click="handleEdit">编辑</el-button>
                <el-button @click="handleBack">返回</el-button>
              </div>
            </div>
          </template>

          <el-descriptions :column="2" border>
            <el-descriptions-item label="组织名称">{{ detail.name }}</el-descriptions-item>
            <el-descriptions-item label="组织编码">{{ detail.code || '—' }}</el-descriptions-item>
            <el-descriptions-item label="组织类型">
              <el-tag v-if="detail.org_type === 'department'" type="primary">部门单位</el-tag>
              <el-tag v-else-if="detail.org_type === 'support_unit'" type="success"
                >帮扶单位</el-tag
              >
              <el-tag v-else type="info">{{ detail.org_type || '未设置' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="层级">
              <el-tag size="small" type="info">{{ formatLevel(detail.level) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="联系人">{{
              ds(detail.contact_person, 'name') || '无'
            }}</el-descriptions-item>
            <el-descriptions-item label="联系电话">{{
              ds(detail.contact_phone, 'phone') || '无'
            }}</el-descriptions-item>
            <el-descriptions-item label="联系邮箱">{{
              ds(detail.contact_email, 'email') || '无'
            }}</el-descriptions-item>
            <el-descriptions-item label="地址">{{
              ds(detail.address, 'address') || '无'
            }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="detail.is_active ? 'success' : 'info'">
                {{ detail.is_active ? '正常' : '停用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="排序">{{ detail.sort_order }}</el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{
              detail.description || '无'
            }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{
              formatDate(detail.created_at)
            }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{
              formatDate(detail.updated_at)
            }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 子组织列表 -->
        <el-card style="margin-top: 20px">
          <template #header>
            <div class="card-header">
              <span class="title">下属组织（{{ detail.children?.length || 0 }}）</span>
            </div>
          </template>
          <el-table v-if="detail.children?.length" :data="detail.children" border stripe>
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="name" label="名称" min-width="200">
              <template #default="scope">
                <span class="org-name-link" @click="goToOrg(scope.row.id)">{{
                  scope.row.name
                }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="code" label="编码" width="120" />
            <el-table-column prop="org_type" label="类型" width="120">
              <template #default="scope">
                <el-tag v-if="scope.row.org_type === 'department'" type="primary" size="small"
                  >部门单位</el-tag
                >
                <el-tag
                  v-else-if="scope.row.org_type === 'support_unit'"
                  type="success"
                  size="small"
                  >帮扶单位</el-tag
                >
                <el-tag v-else type="info" size="small">{{ scope.row.org_type || '—' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="level" label="层级" width="100">
              <template #default="scope">
                <el-tag size="small" type="info">{{ formatLevel(scope.row.level) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="sort_order" label="排序" width="70" align="center" />
          </el-table>
          <el-empty v-else description="暂无下属组织" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 右侧：统计 + 成员 -->
      <el-col :span="8">
        <!-- 统计卡片 -->
        <el-card class="stat-card">
          <template #header>
            <span class="title">组织概览</span>
          </template>
          <div class="mini-stats">
            <div class="mini-stat-item">
              <div class="mini-stat-value">{{ detail.children_count || 0 }}</div>
              <div class="mini-stat-label">下属组织</div>
            </div>
            <div class="mini-stat-item">
              <div class="mini-stat-value">{{ detail.member_count || 0 }}</div>
              <div class="mini-stat-label">成员数量</div>
            </div>
          </div>
        </el-card>

        <!-- 成员列表 -->
        <el-card style="margin-top: 20px">
          <template #header>
            <div class="card-header">
              <span class="title">组织成员</span>
              <el-tag size="small" type="info">{{ memberTotal }}</el-tag>
              <el-button
                size="small"
                type="primary"
                style="margin-left: auto"
                @click="goManageMembers"
              >
                分配成员
              </el-button>
            </div>
          </template>
          <el-table v-loading="memberLoading" :data="members" border stripe size="small">
            <el-table-column prop="full_name" label="姓名" min-width="80">
              <template #default="scope">
                {{ ds(scope.row.full_name, 'name') || scope.row.username }}
              </template>
            </el-table-column>
            <el-table-column prop="role" label="角色" width="100">
              <template #default="scope">
                <el-tag size="small" :type="roleTagType(scope.row.role)">
                  {{ roleLabel(scope.row.role) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="memberTotal > memberPageSize"
            v-model:current-page="memberPage"
            :page-size="memberPageSize"
            :total="memberTotal"
            layout="prev, pager, next"
            small
            style="margin-top: 12px; justify-content: center"
            @current-change="loadMembers"
          />
          <el-empty
            v-if="!memberLoading && members.length === 0"
            description="暂无成员"
            :image-size="40"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe, safeRouteParam } from '@/composables/useRouterSafe'
import { useDesensitize } from '@/composables/useDesensitize'
import { ElMessage } from 'element-plus'
import { getOrganizationDetail, getOrganizationMembers } from '@/api/organization'

const { pushSafe } = useRouterSafe()
const { ds } = useDesensitize()
const route = useRoute()
const loading = ref(false)

const detail = reactive<any>({
  id: 0,
  name: '',
  code: '',
  org_type: null,
  level: null,
  parent_id: null,
  parent_name: null,
  is_active: true,
  sort_order: 0,
  description: '',
  contact_person: '',
  contact_phone: '',
  contact_email: '',
  address: '',
  created_at: '',
  updated_at: '',
  children_count: 0,
  member_count: 0,
  children: [],
  ancestors: [],
})

// 成员相关
const members = ref<any[]>([])
const memberLoading = ref(false)
const memberTotal = ref(0)
const memberPage = ref(1)
const memberPageSize = ref(10)

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '无'
  return dateStr.split('T')[0]
}

const formatLevel = (level: any): string => {
  if (!level) return '未设置'
  const levelStr = String(level)
  const match = levelStr.match(/level_(\d+)/)
  if (match) return `第${match[1]}级`
  return levelStr
}

const roleLabel = (role: string): string => {
  const map: Record<string, string> = {
    super_admin: '超级管理员',
    admin: '管理员',
    manager: '经理',
    approval_leader: '审批领导',
    user: '普通用户',
    viewer: '访客',
  }
  return map[role] || role || '未知'
}

const roleTagType = (role: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    super_admin: 'danger',
    admin: 'warning',
    manager: 'success',
    approval_leader: 'primary',
    user: 'info',
    viewer: 'info',
  }
  return map[role] || 'info'
}

const loadData = async () => {
  const id = safeRouteParam(route.params.id)
  if (!id) return

  loading.value = true
  try {
    const res = await getOrganizationDetail(id as number)
    const data = res.data?.data || res.data
    Object.assign(detail, data)
  } catch (error) {
    logger.error('加载组织信息失败:', error)
    ElMessage.error('加载组织信息失败')
  } finally {
    loading.value = false
  }
}

const loadMembers = async () => {
  const id = safeRouteParam(route.params.id)
  if (!id) return

  memberLoading.value = true
  try {
    const res = await getOrganizationMembers(id as number, {
      page: memberPage.value,
      page_size: memberPageSize.value,
    })
    const data = res.data?.data || res.data
    members.value = data?.items || []
    memberTotal.value = data?.total || 0
  } catch {
    members.value = []
    memberTotal.value = 0
  } finally {
    memberLoading.value = false
  }
}

const goToOrg = (orgId: number) => {
  pushSafe(`/organizations/${orgId}`)
}

const handleEdit = () => {
  pushSafe(`/organizations/${detail.id}/edit`)
}

const handleBack = () => {
  pushSafe('/organizations')
}

/** 成员本质为"用户 + 所属组织"，分配入口在用户管理（可编辑用户所属组织） */
const goManageMembers = () => {
  pushSafe(`/system/users?org_id=${detail.id}`)
}

onMounted(() => {
  loadData()
  loadMembers()
})
</script>

<style scoped>
.organization-detail {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 16px;
  font-weight: bold;
}

.actions {
  display: flex;
  gap: 10px;
}

.org-name-link {
  color: var(--color-primary);
  cursor: pointer;
  font-weight: 500;
}
.org-name-link:hover {
  text-decoration: underline;
}

/* 统计卡片 */
.stat-card {
  margin-bottom: 0;
}
.mini-stats {
  display: flex;
  justify-content: space-around;
}
.mini-stat-item {
  text-align: center;
}
.mini-stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1b4332;
}
.mini-stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
</style>
