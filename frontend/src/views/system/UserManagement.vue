<template>
  <div class="user-management">
    <PageHeader title="用户管理" subtitle="管理系统用户、角色与权限分配" />
    <!-- 用户/角色 Tab 切换 -->
    <el-tabs v-model="activeTab" class="user-role-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="用户列表" name="users" />
      <el-tab-pane label="角色管理" name="roles" />
    </el-tabs>

    <el-card v-if="activeTab === 'users'" class="search-card">
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="用户名">
          <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="searchForm.name" placeholder="请输入姓名" clearable />
        </el-form-item>
        <el-form-item label="角色">
          <el-select
            v-model="searchForm.role"
            placeholder="请选择角色"
            clearable
            teleported
            fit-input-width
          >
            <el-option
              v-for="role in roleOptions"
              :key="role.value"
              :label="role.label"
              :value="role.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="searchForm.is_active"
            placeholder="请选择状态"
            clearable
            teleported
            fit-input-width
          >
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <div class="title-area">
            <span class="title">用户列表</span>
            <el-badge
              v-if="isAdmin && pendingCount > 0"
              :value="pendingCount"
              class="pending-badge"
            >
              <el-button type="warning" size="small" @click="showPendingUsers"
                >待审核用户</el-button
              >
            </el-badge>
          </div>
          <div v-if="isAdmin" v-permission="['admin', 'super_admin']" class="header-actions">
            <el-button type="primary" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              新增用户
            </el-button>
            <el-dropdown @command="handlePermPackageCommand">
              <el-button type="info">
                权限包
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="export">导出权限包</el-dropdown-item>
                  <el-dropdown-item command="import">导入权限包</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </template>

      <el-alert
        v-if="orgFilterId"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      >
        <template #title>
          当前仅显示该组织的成员
          <el-button
            link
            type="primary"
            size="small"
            style="margin-left: 8px"
            @click="clearOrgFilter"
          >
            清除筛选
          </el-button>
        </template>
      </el-alert>

      <el-table v-loading="loading" :data="tableData" stripe border>
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="full_name" label="姓名" min-width="100">
          <template #default="{ row }">
            {{ ds(row.full_name, 'name') }}
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="130">
          <template #default="{ row }">
            <el-tag :type="getRoleTagType(row.role)">{{ getRoleName(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="data_scope" label="数据范围" width="120">
          <template #default="{ row }">
            {{ getDataScopeName(row.data_scope) }}
          </template>
        </el-table-column>
        <el-table-column label="权限包" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.permission_pack_id" type="warning" size="small">
              {{ packNameMap[row.permission_pack_id] || '未知包' }}
            </el-tag>
            <span v-else class="role-default-text">角色默认</span>
          </template>
        </el-table-column>
        <el-table-column prop="organization_name" label="所属组织" min-width="140">
          <template #default="{ row }">
            {{ row.organization_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="department" label="部门" min-width="120" />
        <el-table-column prop="phone" label="手机号" width="130">
          <template #default="{ row }">
            {{ ds(row.phone, 'phone') }}
          </template>
        </el-table-column>
        <el-table-column prop="machine_code" label="机器码" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.machine_code" type="success" size="small">
              <el-icon><Key /></el-icon>
              已绑定
            </el-tag>
            <el-tag v-else type="info" size="small">未绑定</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login" label="最后登录" width="160" />
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="操作" width="320" align="center" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button text type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
              <el-button text type="warning" size="small" @click="handleResetPassword(row)"
                >重置密码</el-button
              >
              <el-button text type="success" size="small" @click="handleRolePermission(row)"
                >角色/权限</el-button
              >
              <el-button text type="info" size="small" @click="handleMenuPermission(row)"
                >菜单权限</el-button
              >
              <el-button text type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </el-card>

    <!-- 用户编辑对话框 -->
    <el-dialog v-model="dialogVisible" append-to-body :title="dialogTitle" :width="DIALOG_MD">
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="formData.username" placeholder="请输入用户名" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="姓名" prop="full_name">
          <el-input v-model="formData.full_name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="初始密码" prop="password">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-input
              v-model="formData.password"
              type="password"
              placeholder="请输入密码"
              show-password
              style="flex: 1"
            />
            <el-button @click="generatePassword">自动生成</el-button>
          </div>
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select
            v-model="formData.role"
            placeholder="请选择角色"
            style="width: 100%"
            teleported
            fit-input-width
          >
            <el-option
              v-for="role in roleOptions"
              :key="role.value"
              :label="role.label"
              :value="role.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数据范围">
          <el-select
            v-model="formData.data_scope"
            placeholder="请选择数据范围"
            style="width: 100%"
            teleported
            fit-input-width
          >
            <el-option
              v-for="scope in dataScopeOptions"
              :key="scope.value"
              :label="scope.label"
              :value="scope.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属组织">
          <el-tree-select
            v-model="formData.organization_id"
            :data="orgTreeOptions"
            :props="{ label: 'name', value: 'id', children: 'children' } as any"
            placeholder="请选择所属组织"
            check-strictly
            clearable
            filterable
            style="width: 100%"
            teleported
            fit-input-width
          />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="功能权限">
          <el-select
            v-model="formData.permissions"
            multiple
            placeholder="请选择该用户的功能权限（不选则使用角色默认权限）"
            style="width: 100%"
            collapse-tags
            collapse-tags-tooltip
            teleported
            fit-input-width
          >
            <el-option-group
              v-for="group in permissionGroups"
              :key="group.category"
              :label="group.category"
            >
              <el-option
                v-for="perm in group.items"
                :key="perm.code"
                :label="perm.name"
                :value="perm.code"
              />
            </el-option-group>
          </el-select>
          <div class="form-item-tip">
            选择该用户可以使用的具体功能权限，未选择则使用角色默认权限
          </div>
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="formData.department" placeholder="请输入部门" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="formData.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="formData.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="formData.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>

      <!-- 活跃会话管理 (仅编辑模式) -->
      <div v-if="isEdit" class="session-section">
        <el-divider content-position="left">活跃会话</el-divider>
        <div v-loading="sessionsLoading">
          <el-table v-if="userSessions.length > 0" :data="userSessions" size="small" border>
            <el-table-column
              prop="session_id"
              label="会话ID"
              min-width="180"
              show-overflow-tooltip
            />
            <el-table-column prop="ip_address" label="IP 地址" width="140" />
            <el-table-column prop="user_agent" label="设备" min-width="160" show-overflow-tooltip />
            <el-table-column prop="created_at" label="登录时间" width="170">
              <template #default="{ row }">
                {{ formatSessionTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button
                  type="danger"
                  size="small"
                  :loading="revokingSession === row.session_id"
                  @click="revokeSession(row)"
                >
                  强制登出
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <EmptyState v-else-if="!sessionsLoading" text="无活跃会话" :size="40" />
        </div>
        <div class="session-actions">
          <el-button type="warning" size="small" :loading="resetting2fa" @click="handleReset2fa">
            重置 2FA
          </el-button>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetPwdDialogVisible" append-to-body title="重置密码" :width="DIALOG_SM">
      <el-form :model="resetPwdForm" label-width="100px">
        <el-form-item label="用户名">
          <el-input :value="currentUser?.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-input
              v-model="resetPwdForm.newPassword"
              type="password"
              placeholder="请输入新密码"
              show-password
              style="flex: 1"
            />
            <el-button @click="generateResetPassword">自动生成</el-button>
          </div>
        </el-form-item>
        <el-form-item v-if="resetPwdForm.newPassword" label="生成的密码">
          <el-input :value="resetPwdForm.newPassword" readonly>
            <template #append>
              <el-button @click="copyPassword">复制</el-button>
            </template>
          </el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmResetPassword">确认重置</el-button>
      </template>
    </el-dialog>

    <!-- 角色/权限分配抽屉 -->
    <PermissionAssignmentDrawer
      v-model="permDrawerVisible"
      :user="permDrawerUser"
      @saved="handlePermSaved"
    />

    <!-- 菜单权限配置对话框 -->
    <el-dialog
      v-model="menuPermDialogVisible"
      append-to-body
      title="菜单权限配置"
      :width="DIALOG_SM"
    >
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
        为「{{ menuPermUser?.username || '' }}」配置可见页面。勾选后该用户仅能看到所选菜单；
        不勾选任何菜单时使用角色默认权限。
      </el-alert>
      <div v-loading="menuPermLoading" style="min-height: 200px; max-height: 400px; overflow: auto">
        <el-checkbox
          :model-value="menuPermAllChecked"
          :indeterminate="menuPermIndeterminate"
          @change="toggleMenuPermAll"
        >
          全选 / 恢复角色默认
        </el-checkbox>
        <el-tree
          ref="menuPermTreeRef"
          :data="menuPermTree"
          show-checkbox
          node-key="key"
          :props="{ label: 'label', children: 'children' }"
          default-expand-all
          style="margin-top: 8px"
        />
      </div>
      <template #footer>
        <el-button @click="menuPermDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="menuPermSaving" @click="saveMenuPermission">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 导出权限包：角色选择对话框 -->
    <el-dialog
      v-model="permExportDialogVisible"
      append-to-body
      title="导出权限包"
      :width="DIALOG_SM"
    >
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
        不勾选任何角色将导出全部权限配置；勾选后仅导出所选角色及其用户绑定。
      </el-alert>
      <div v-loading="permRolesLoading" style="max-height: 320px; overflow: auto">
        <el-checkbox-group v-model="permExportRoleNames">
          <el-checkbox v-for="r in permExportRoleOptions" :key="r.name" :value="r.name">
            {{ r.label || r.name }}
          </el-checkbox>
        </el-checkbox-group>
        <div v-if="!permRolesLoading && permExportRoleOptions.length === 0" class="empty-hint">
          未检测到自定义 RBAC 角色，可直接导出基础配置。
        </div>
      </div>
      <el-divider style="margin: 12px 0" />
      <el-form label-width="110px">
        <el-form-item label="加密密码">
          <el-input
            v-model="permExportPassword"
            type="password"
            show-password
            placeholder="可选；设置后导入需输入该密码"
            clearable
          />
        </el-form-item>
        <el-form-item label="机器码绑定">
          <el-switch v-model="permBindMachineCode" />
          <span class="form-hint">开启后仅本机可导入该权限包</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="permExportDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="exportingPermPackage"
          @click="doExportPermissionPackage"
        >
          导出
        </el-button>
      </template>
    </el-dialog>

    <!-- ========== 角色管理 Tab ========== -->
    <div v-if="activeTab === 'roles'" class="role-section">
      <RoleManagement />
    </div>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM, DIALOG_MD } from '@/config/dialog'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import { logger } from '@/utils/logger'
import { generateRandomPassword } from '@/utils/clipboard'

import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import RoleManagement from './Role.vue'

const activeTab = ref('users')
function handleTabChange(_tab: any) {
  /* tab switched */
}
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus, Key, ArrowDown } from '@element-plus/icons-vue'
import request, { get, post, put, del, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'
import { listPermissionPacks } from '@/api/permissionPack'
import { useAuthStore } from '@/stores/auth'
import { useDesensitize } from '@/composables/useDesensitize'
import PermissionAssignmentDrawer from '@/components/permission/PermissionAssignmentDrawer.vue'

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)
const { ds } = useDesensitize()
const route = useRoute()

// 组织成员预筛选（从组织详情"分配成员"进入时携带 ?org_id=）
const orgFilterId = ref<number | null>(null)

function clearOrgFilter() {
  orgFilterId.value = null
  pagination.page = 1
  loadData()
}

interface User {
  id: number
  username: string
  full_name: string
  role: string
  data_scope?: string
  department: string
  phone: string
  email: string
  is_active: boolean
  last_login?: string
  organization_id?: number | null
  organization_name?: string
  permissions?: string
  created_at?: string
  machine_code?: string
  machine_binding_required?: boolean
  allowed_permissions?: string
  permission_pack_id?: number | null
}

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增用户')
const isEdit = ref(false)
const resetPwdDialogVisible = ref(false)
const permDrawerVisible = ref(false)
const permDrawerUser = ref<User | null>(null)
const pendingDialogVisible = ref(false)
const formRef = ref<FormInstance>()
const currentUser = ref<User | null>(null)

const pendingCount = ref(0)
const pendingUsers = ref<User[]>([])

const searchForm = reactive({
  username: '',
  name: '',
  role: '',
  is_active: undefined as boolean | undefined,
})

const pagination = reactive({
  page: 1,
  size: 10,
  total: 0,
})

const tableData = ref<User[]>([])

const formData = reactive({
  id: 0,
  username: '',
  full_name: '',
  password: '',
  role: 'user',
  data_scope: 'org',
  department: '',
  phone: '',
  email: '',
  is_active: true,
  organization_id: null as number | null,
  permissions: [] as string[],
})

import { normalizeTreeNodes } from '@/utils/treeNormalizer'

const orgTreeOptions = ref<any[]>([])

async function loadOrgTree() {
  try {
    const res = await get('/organizations/tree')
    const raw = res.data || res || []
    orgTreeOptions.value = Array.isArray(raw) ? normalizeTreeNodes(raw) : []
  } catch {
    orgTreeOptions.value = []
  }
}

const resetPwdForm = reactive({
  newPassword: '',
})

// Permission groups for UI grouping - 与后端 /users/permissions/options 保持一致
const permissionGroups = [
  {
    category: '系统',
    items: [
      { code: 'system:manage', name: '系统管理' },
      { code: 'user:manage', name: '用户管理' },
      { code: 'org:manage', name: '组织管理' },
      { code: 'role:manage', name: '角色管理' },
    ],
  },
  {
    category: '数据',
    items: [
      { code: 'village:manage', name: '村庄管理' },
      { code: 'project:manage', name: '项目管理' },
      { code: 'fund:manage', name: '资金管理' },
      { code: 'report:manage', name: '报表管理' },
    ],
  },
  {
    category: '操作',
    items: [
      { code: 'data:view', name: '数据查看' },
      { code: 'data:create', name: '数据创建' },
      { code: 'data:edit', name: '数据编辑' },
      { code: 'data:delete', name: '数据删除' },
      { code: 'data:export', name: '数据导出' },
      { code: 'data:import', name: '数据导入' },
    ],
  },
  {
    category: '审批',
    items: [
      { code: 'approve:view', name: '查看审批' },
      { code: 'approve:submit', name: '提交审批' },
      { code: 'approve:process', name: '处理审批' },
    ],
  },
]

// 角色选项：精简为 4 个实用角色（users.role 体系）
// 兼容映射：approval_leader/manager→管理员级，operator→普通用户
const roleOptions = ref<{ value: string; label: string }[]>([
  { value: 'super_admin', label: '超级管理员' },
  { value: 'admin', label: '系统管理员' },
  { value: 'user', label: '普通用户' },
  { value: 'viewer', label: '访客' },
])

// 角色选项固定使用 users.role 体系（4 个实用角色）。
// 注意：不再用 /rbac/roles（RbacRole 表）覆盖选项——
// RBAC 角色是细粒度权限包的补充，与 users.role 是两套体系，
// 混用会导致 users.role 存入 RBAC 角色名而使权限判断失效。

const dataScopeOptions = [
  { value: 'all', label: '全部数据' },
  { value: 'org_children', label: '本组织及下级' },
  { value: 'org', label: '仅本组织' },
  { value: 'self', label: '仅自己' },
]

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '长度在 3 到 20 个字符', trigger: 'blur' },
  ],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 50, message: '长度在 6 到 50 个字符', trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

const getRoleTagType = (role: string): 'info' | 'primary' | 'success' | 'warning' | 'danger' => {
  const types: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
    super_admin: 'danger',
    admin: 'danger',
    approval_leader: 'warning',
    manager: 'warning',
    operator: 'success',
    user: 'success',
    viewer: 'info',
  }
  return types[role] || 'info'
}

const getRoleName = (role: string) => {
  const names: Record<string, string> = {
    super_admin: '超级管理员',
    admin: '系统管理员',
    approval_leader: '审批领导',
    manager: '管理人员',
    operator: '操作员',
    user: '普通用户',
    viewer: '访客',
  }
  return names[role] || role
}

const getDataScopeName = (scope: string) => {
  const names: Record<string, string> = {
    all: '全部',
    org_children: '本组织及下级',
    org: '仅本组织',
    self: '仅自己',
  }
  return names[scope] || scope || '-'
}

const generatePassword = () => {
  formData.password = generateRandomPassword()
}

const generateResetPassword = () => {
  resetPwdForm.newPassword = generateRandomPassword()
}

const copyPassword = async () => {
  try {
    await navigator.clipboard.writeText(resetPwdForm.newPassword)
    ElMessage.success('密码已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const response = await apiRequest({
      method: 'GET',
      url: '/users',
      params: {
        page: pagination.page,
        page_size: pagination.size,
        username: searchForm.username || undefined,
        keyword: searchForm.name || undefined,
        role: searchForm.role || undefined,
        is_active: searchForm.is_active,
        organization_id: orgFilterId.value || undefined,
      },
    })
    const data = response
    tableData.value = data.items || []
    pagination.total = data.total || tableData.value.length
  } catch (error) {
    logger.error('加载用户数据失败:', error)
    ElMessage.error('加载用户数据失败')
  } finally {
    loading.value = false
  }
}

// 权限包 id → 名称映射（用户列表"权限包"列展示用；加载失败静默降级为空映射）
const packNameMap = ref<Record<number, string>>({})

const loadPackNameMap = async () => {
  try {
    const packs = await listPermissionPacks()
    const map: Record<number, string> = {}
    for (const p of packs) {
      map[p.id] = p.name
    }
    packNameMap.value = map
  } catch {
    packNameMap.value = {}
  }
}

const loadPendingCount = async () => {
  if (!isAdmin.value) return
  try {
    const res = await get('/users/pending/list')
    const data = res.data || res || []
    pendingCount.value = Array.isArray(data) ? data.length : data.total || 0
  } catch {
    pendingCount.value = 0
  }
}

const showPendingUsers = async () => {
  try {
    const res = await get('/users/pending/list')
    const data = res.data || res || []
    const items = Array.isArray(data) ? data : data.items || []
    pendingUsers.value = items
    pendingCount.value = items.length
    pendingDialogVisible.value = true
  } catch {
    ElMessage.error('加载待审核用户失败')
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadData()
}

const handleReset = () => {
  Object.assign(searchForm, {
    username: '',
    name: '',
    role: '',
    is_active: undefined,
  })
  handleSearch()
}

const handleSizeChange = () => {
  pagination.page = 1
  loadData()
}

const handlePageChange = () => {
  loadData()
}

const handleAdd = () => {
  isEdit.value = false
  dialogTitle.value = '新增用户'
  Object.assign(formData, {
    id: 0,
    username: '',
    full_name: '',
    password: '',
    role: 'user',
    data_scope: 'org',
    department: '',
    phone: '',
    email: '',
    is_active: true,
    organization_id: null,
    permissions: [],
  })
  dialogVisible.value = true
}

const handleEdit = (row: any) => {
  isEdit.value = true
  dialogTitle.value = '编辑用户'
  currentUser.value = row
  Object.assign(formData, {
    ...row,
    organization_id: row.organization_id ?? null,
  })
  dialogVisible.value = true
  // Load active sessions for this user
  loadUserSessions(row.id)
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (isEdit.value) {
        await put(`/users/${formData.id}`, {
          full_name: formData.full_name,
          email: formData.email,
          phone: formData.phone,
          department: formData.department,
          role: formData.role,
          is_active: formData.is_active,
          data_scope: formData.data_scope,
          organization_id: formData.organization_id,
        })
        ElMessage.success('用户更新成功')
      } else {
        const res = await post('/users', {
          username: formData.username,
          full_name: formData.full_name,
          password: formData.password || undefined,
          email: formData.email,
          phone: formData.phone,
          department: formData.department,
          role: formData.role,
          data_scope: formData.data_scope,
          organization_id: formData.organization_id,
          is_active: formData.is_active,
          permissions: formData.permissions?.join(',') || '',
        })
        const created = res.data?.data
        if (created?.password) {
          ElMessage.success(
            `用户创建成功！\n用户名: ${formData.username}\n初始密码: ${created.password}`
          )
        } else {
          ElMessage.success('用户创建成功')
        }
      }
      dialogVisible.value = false
      pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
      await Promise.all([loadData(), loadPendingCount()])
    } catch (error: any) {
      const msg = error?.response?.data?.detail || '操作失败'
      ElMessage.error(msg)
    } finally {
      submitting.value = false
    }
  })
}

const handleResetPassword = (row: any) => {
  currentUser.value = row
  resetPwdForm.newPassword = ''
  resetPwdDialogVisible.value = true
}

const confirmResetPassword = async () => {
  if (!resetPwdForm.newPassword) {
    ElMessage.warning('请输入或生成新密码')
    return
  }

  try {
    const newPwd = resetPwdForm.newPassword
    await post(`/users/${currentUser.value?.id}/admin-reset-password`, {
      new_password: newPwd,
    })
    try {
      await navigator.clipboard.writeText(newPwd)
    } catch {
      /* ignore */
    }
    ElMessageBox.alert(`新密码：${newPwd}`, `用户「${currentUser.value?.username}」密码已重置`, {
      confirmButtonText: '已复制到剪贴板，知道了',
      type: 'success',
    })
    resetPwdDialogVisible.value = false
    resetPwdForm.newPassword = ''
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '重置密码失败'
    ElMessage.error(msg)
  }
}

// ── 角色/权限分配抽屉 ──
const handleRolePermission = (row: any) => {
  permDrawerUser.value = row
  permDrawerVisible.value = true
}

const handlePermSaved = async () => {
  pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
  await Promise.all([loadData(), loadPendingCount()])
}

// ── 菜单权限配置 ──
const menuPermDialogVisible = ref(false)
const menuPermLoading = ref(false)
const menuPermSaving = ref(false)
const menuPermUser = ref<any>(null)
const menuPermTree = ref<any[]>([])
const menuPermTreeRef = ref<any>(null)
const menuPermAllChecked = ref(false)
const menuPermIndeterminate = ref(false)

async function handleMenuPermission(row: any) {
  menuPermUser.value = row
  menuPermDialogVisible.value = true
  menuPermLoading.value = true
  menuPermAllChecked.value = false
  menuPermIndeterminate.value = false
  try {
    // 拉取用户菜单配置 + 全量菜单树
    const [cfgRes, menuRes] = await Promise.all([
      get(`/menus/user-menus/${row.id}`),
      get('/menus/all'),
    ])
    const cfg = (cfgRes as any)?.data ?? cfgRes ?? {}
    const menuKeys: string[] = cfg.menu_keys || []
    const menuData = (menuRes as any)?.data ?? menuRes ?? []
    menuPermTree.value = Array.isArray(menuData) ? menuData : []
    await nextTick()
    const tree = menuPermTreeRef.value
    if (tree) {
      tree.setCheckedKeys(menuKeys)
      updateMenuPermAllState()
    }
  } catch (e: any) {
    logger.error('加载菜单权限配置失败', e)
    ElMessage.error(e?.response?.data?.detail || '加载菜单权限配置失败')
  } finally {
    menuPermLoading.value = false
  }
}

function updateMenuPermAllState() {
  const tree = menuPermTreeRef.value
  if (!tree) return
  const checked = tree.getCheckedKeys(false)
  const allKeys = flattenMenuKeys(menuPermTree.value)
  menuPermAllChecked.value = allKeys.length > 0 && checked.length === allKeys.length
  menuPermIndeterminate.value = checked.length > 0 && checked.length < allKeys.length
}

function flattenMenuKeys(items: any[]): string[] {
  const keys: string[] = []
  const walk = (list: any[]) => {
    for (const item of list) {
      keys.push(item.key)
      if (item.children?.length) walk(item.children)
    }
  }
  walk(items)
  return keys
}

function toggleMenuPermAll(checked: boolean | string | number) {
  const tree = menuPermTreeRef.value
  if (!tree) return
  if (checked) {
    tree.setCheckedKeys(flattenMenuKeys(menuPermTree.value))
  } else {
    tree.setCheckedKeys([])
  }
  updateMenuPermAllState()
}

async function saveMenuPermission() {
  if (!menuPermUser.value) return
  const tree = menuPermTreeRef.value
  if (!tree) return
  menuPermSaving.value = true
  try {
    const checkedKeys = tree.getCheckedKeys(false) as string[]
    await put(`/menus/user-menus/${menuPermUser.value.id}`, { menu_keys: checkedKeys })
    ElMessage.success('菜单权限已保存')
    menuPermDialogVisible.value = false
  } catch (e: any) {
    logger.error('保存菜单权限失败', e)
    ElMessage.error(e?.response?.data?.detail || '保存菜单权限失败')
  } finally {
    menuPermSaving.value = false
  }
}

// ── 用户会话管理 ──
const userSessions = ref<any[]>([])
const sessionsLoading = ref(false)
const revokingSession = ref<string | null>(null)
const resetting2fa = ref(false)

async function loadUserSessions(userId: number) {
  sessionsLoading.value = true
  userSessions.value = []
  try {
    const res = await get(`/system/admin/users/${userId}/sessions`)
    const data = res.data?.data ?? res.data ?? res
    userSessions.value = Array.isArray(data) ? data : (data?.sessions ?? [])
  } catch (e: any) {
    // 会话接口异常时提示而非静默吞错，避免掩盖后端故障
    userSessions.value = []
    ElMessage.error(e?.response?.data?.detail || '会话信息加载失败，请检查后端服务')
  } finally {
    sessionsLoading.value = false
  }
}

async function revokeSession(session: any) {
  if (!currentUser.value) return
  revokingSession.value = session.session_id
  try {
    await post(`/system/admin/users/${currentUser.value.id}/sessions/${session.session_id}/revoke`)
    ElMessage.success('已强制登出该会话')
    userSessions.value = userSessions.value.filter((s) => s.session_id !== session.session_id)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '强制登出失败，接口可能尚未实现')
  } finally {
    revokingSession.value = null
  }
}

async function handleReset2fa() {
  if (!currentUser.value) return
  try {
    await ElMessageBox.confirm(
      `确定要重置用户「${currentUser.value.username}」的两步验证 (2FA) 吗？`,
      '重置 2FA',
      { type: 'warning' }
    )
  } catch {
    return // user cancelled
  }
  resetting2fa.value = true
  try {
    await post(`/system/admin/users/${currentUser.value.id}/two-factor/reset`)
    ElMessage.success('2FA 已重置')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '重置 2FA 失败，接口可能尚未实现')
  } finally {
    resetting2fa.value = false
  }
}

function formatSessionTime(time: string | null) {
  if (!time) return '-'
  try {
    return new Date(time).toLocaleString('zh-CN')
  } catch {
    return '-'
  }
}

// ── 权限包导入/导出 ──
const exportingPermPackage = ref(false)
const importingPermPackage = ref(false)

const handlePermPackageCommand = (command: string) => {
  if (command === 'export') openPermExportDialog()
  else if (command === 'import') handleImportPermissionPackage()
}

// ── 导出：角色选择对话框（P1 选择性导出） ──
const permExportDialogVisible = ref(false)
const permRolesLoading = ref(false)
const permExportRoleOptions = ref<{ name: string; label?: string }[]>([])
const permExportRoleNames = ref<string[]>([])
const permExportPassword = ref('')
const permBindMachineCode = ref(false)

async function openPermExportDialog() {
  permExportDialogVisible.value = true
  permExportRoleNames.value = []
  permExportPassword.value = ''
  permBindMachineCode.value = false
  if (permExportRoleOptions.value.length > 0) return
  permRolesLoading.value = true
  try {
    const res: any = await get('/rbac/roles', { limit: 200 })
    const data = res?.data || res || {}
    const roles = Array.isArray(data) ? data : data.data || data.items || []
    permExportRoleOptions.value = roles.map((r: any) => ({
      name: r.name,
      label: r.label || r.description || r.name,
    }))
  } catch {
    // 角色列表获取失败不阻断导出，仍可全量导出
    permExportRoleOptions.value = []
  } finally {
    permRolesLoading.value = false
  }
}

const doExportPermissionPackage = async () => {
  exportingPermPackage.value = true
  try {
    const payload: Record<string, unknown> = {}
    if (permExportRoleNames.value.length > 0) {
      payload.role_names = permExportRoleNames.value
    }
    if (permExportPassword.value) {
      payload.password = permExportPassword.value
    }
    if (permBindMachineCode.value) {
      payload.bind_machine_code = true
    }
    const res = await post('/permission-packages/export', payload)
    const data = res.data || res
    if (!data.file_name) {
      throw new Error('导出响应缺少 file_name')
    }
    // 必须走带 Authorization 拦截器的 axios 实例：/permission-packages/download
    // 依赖 get_current_user，裸 <a> 导航不带认证头会恒 401（表现为“提示成功却没有文件”）。
    // await 下载真正完成后才提示成功；失败会抛出并由下方 catch 提示真实原因。
    await downloadBlobAsFile(
      () =>
        request.get(`/permission-packages/download/${encodeURIComponent(data.file_name)}`, {
          responseType: 'blob',
        }),
      { fallbackFileName: data.file_name }
    )
    ElMessage.success(`权限包导出成功 (${data.role_count} 个角色, ${data.user_count} 个用户)`)
    permExportDialogVisible.value = false
  } catch (err: any) {
    ElMessage.error(err?.userMessage || err?.response?.data?.detail || err?.message || '导出失败')
  } finally {
    exportingPermPackage.value = false
  }
}

const handleImportPermissionPackage = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.zip'

  // 清理函数：移除 input 元素 + 重置状态
  const cleanup = () => {
    importingPermPackage.value = false
    input.remove()
    window.removeEventListener('focus', cleanup)
  }

  // 用户取消文件对话框时 change 事件不触发，用 window focus 代理清理
  window.addEventListener('focus', cleanup, { once: true })

  input.addEventListener('change', async (e: Event) => {
    // 用户已选择文件 → 取消 focus 清理（change 事件先于 focus）
    window.removeEventListener('focus', cleanup)

    importingPermPackage.value = true
    try {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) {
        cleanup()
        return
      }
      const fd = new FormData()
      fd.append('file', file)
      const res = await post('/permission-packages/import', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const result = res.data || res
      // Phase E：加密包需要密码；预览失败且标记加密时提示输入并重传
      let importPassword = ''
      if (!result.success && /加密/.test(result.message || '')) {
        try {
          const { value } = await ElMessageBox.prompt(
            '该权限包已加密，请输入导出时设置的密码：',
            '解密密码',
            {
              inputType: 'password',
              inputValidator: (v: string) => (v ? true : '密码不能为空'),
            }
          )
          importPassword = value || ''
        } catch {
          cleanup()
          return
        }
        const fd2 = new FormData()
        fd2.append('file', file)
        fd2.append('password', importPassword)
        const res2 = await post('/permission-packages/import', fd2, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        const merged = res2.data || res2
        Object.assign(result, merged)
        if (!result.success) {
          ElMessage.error(merged.message || result.message || '导入失败')
          return
        }
      }
      if (result.success) {
        const p = result.preview || {}
        let msg = `将导入 ${p.role_count || 0} 个角色, ${p.user_legacy_count || 0} 个用户权限`
        if (p.warnings?.length) msg += `\n警告: ${p.warnings.join('; ')}`
        // 选择导入模式：确定=合并（保留本机其他配置）；取消=完全替换；关闭=放弃
        msg +=
          '\n\n【合并导入】保留本机已有权限，仅追加包内配置\n【覆盖导入】清空本机现有配置后按包内容重建'
        let mode: 'merge' | 'overwrite' | null = null
        await ElMessageBox.confirm(msg, '选择导入模式', {
          type: 'warning',
          distinguishCancelAndClose: true,
          confirmButtonText: '合并导入',
          cancelButtonText: '覆盖导入',
        })
          .then(() => {
            mode = 'merge'
          })
          .catch(async (action: any) => {
            if (action === 'cancel') mode = 'overwrite'
          })
        if (!mode) return // 用户关闭 → 放弃导入
        const cRes = await post(`/permission-packages/confirm/${encodeURIComponent(file.name)}`, {
          overwrite_existing: mode === 'overwrite',
          mode,
        })
        ElMessage.success(cRes.data?.message || cRes.message || '导入完成')
        pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
        loadData()
      } else {
        ElMessage.error(result.message || '导入失败')
      }
    } catch (err: any) {
      if (err === 'cancel') return
      ElMessage.error(err?.response?.data?.detail || err?.message || '导入失败')
    } finally {
      cleanup()
    }
  })

  input.click()
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定删除用户 "${row.full_name || row.username}" 吗？`, '提示', {
      type: 'warning',
    })
    await del(`/users/${row.id}`)
    ElMessage.success('删除成功')
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await Promise.all([loadData(), loadPendingCount()])
    pendingDialogVisible.value = false
  } catch (error: any) {
    if (error !== 'cancel' && error?.toString() !== 'cancel') {
      const msg = error?.response?.data?.detail || '删除失败'
      ElMessage.error(msg)
    }
  }
}

onMounted(() => {
  // 组织详情"分配成员"跳转携带 ?org_id=，预筛选本组织成员
  const q = Number(route?.query?.org_id)
  if (q > 0) {
    orgFilterId.value = q
  }
  loadData()
  loadOrgTree()
  loadPendingCount()
  loadPackNameMap()
})
</script>

<style lang="scss" scoped>
.user-management {
  padding: 20px;
}

.search-card,
.table-card {
  margin-bottom: 20px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 16px;
  font-weight: bold;
  color: var(--color-text-inverse);
}

.pending-badge :deep(.el-badge__content) {
  top: 4px;
}

.role-default-text {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-card__header) {
  border-bottom: 1px solid var(--color-border-light);
  padding: 15px 20px;
}

:deep(.el-form-item__label) {
  color: var(--color-text-primary);
}

.action-buttons {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  white-space: nowrap;
}

.action-buttons .el-button + .el-button {
  margin-left: 0;
}

.action-buttons .el-button {
  padding: 4px 8px;
}

.machine-code-preview {
  margin-left: 10px;
  color: var(--color-info);
  font-size: 12px;
}

.form-item-tip {
  font-size: 12px;
  color: var(--color-info);
  line-height: 1.4;
  margin-top: 4px;
}

.session-section {
  margin-top: 8px;
}
.session-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
</style>
