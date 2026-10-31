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
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 用户列表卡片（W5-T10 拆至 components/UserTableCard.vue；数据/状态仍在本组件持有） -->
    <UserTableCard
      v-model:page="pagination.page"
      v-model:size="pagination.size"
      :users="tableData"
      :loading="loading || importingPermPackage"
      :is-admin="isAdmin"
      :pending-count="pendingCount"
      :org-filter-id="orgFilterId"
      :pack-name-map="packNameMap"
      :total="pagination.total"
      :role-tag-type="getRoleTagType"
      :role-name="getRoleName"
      :data-scope-name="getDataScopeName"
      :desensitize="ds"
      @size-change="handleSizeChange"
      @page-change="handlePageChange"
      @add="handleAdd"
      @open-pending="showPendingUsers"
      @perm-command="handlePermPackageCommand"
      @clear-org-filter="clearOrgFilter"
      @edit="handleEdit"
      @reset-password="handleResetPassword"
      @role-permission="handleRolePermission"
      @delete="handleDelete"
    />

    <!-- 待审核用户对话框（2026-10-14 接通：此前按钮只拉数据、无弹窗消费） -->
    <PendingUsersDialog
      v-model="pendingDialogVisible"
      :users="pendingUsers"
      @approve="approvePendingUser"
    />

    <!-- 用户编辑对话框（W5-T10 拆至 components/UserFormDialog.vue；提交/校验规则仍在本组件） -->
    <UserFormDialog
      ref="userFormRef"
      v-model="dialogVisible"
      :title="dialogTitle"
      :is-edit="isEdit"
      :form="formData"
      :rules="rules"
      :role-options="roleOptions"
      :data-scope-options="dataScopeOptions"
      :org-tree-options="orgTreeOptions"
      :permission-groups="permissionGroups"
      :submitting="submitting"
      :sessions="userSessions"
      :sessions-loading="sessionsLoading"
      :revoking-session="revokingSession"
      :resetting2fa="resetting2fa"
      @update:username="formData.username = $event"
      @update:full_name="formData.full_name = $event"
      @update:password="formData.password = $event"
      @update:role="formData.role = $event"
      @update:data_scope="formData.data_scope = $event"
      @update:organization_id="formData.organization_id = $event"
      @update:permissions="formData.permissions = $event"
      @update:department="formData.department = $event"
      @update:phone="formData.phone = $event"
      @update:email="formData.email = $event"
      @update:is_active="formData.is_active = $event"
      @generate-password="generatePassword"
      @revoke-session="revokeSession"
      @reset-2fa="handleReset2fa"
      @submit="handleSubmit"
    />

    <!-- 重置密码对话框（W5-T10 拆至 components/ResetPasswordDialog.vue） -->
    <ResetPasswordDialog
      v-model="resetPwdDialogVisible"
      :username="currentUser?.username"
      :form="resetPwdForm"
      @update:new-password="resetPwdForm.newPassword = $event"
      @generate="generateResetPassword"
      @copy="copyPassword"
      @confirm="confirmResetPassword"
    />

    <!-- 角色/权限分配抽屉 -->
    <PermissionAssignmentDrawer
      v-model="permDrawerVisible"
      :user="permDrawerUser"
      @saved="handlePermSaved"
    />

    <!-- 导出权限包：角色选择对话框（W5-T10 拆至 components/PermissionPackExportDialog.vue） -->
    <PermissionPackExportDialog
      v-model="permExportDialogVisible"
      :roles-loading="permRolesLoading"
      :role-options="permExportRoleOptions"
      :selected-roles="permExportRoleNames"
      :password="permExportPassword"
      :bind-machine-code="permBindMachineCode"
      :exporting="exportingPermPackage"
      @update:selected-roles="permExportRoleNames = $event"
      @update:password="permExportPassword = $event"
      @update:bind-machine-code="permBindMachineCode = $event"
      @export="doExportPermissionPackage"
    />

    <!-- ========== 角色管理 Tab ========== -->
    <div v-if="activeTab === 'roles'" class="role-section">
      <RoleManagement />
    </div>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/common/PageHeader.vue'
import { logger } from '@/utils/logger'
import { generateRandomPassword } from '@/utils/clipboard'
import { passwordValidator } from '@/utils/passwordPolicy'

import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import RoleManagement from './Role.vue'

const activeTab = ref('users')
function handleTabChange(_tab: any) {
  /* tab switched */
}
import { ElMessage, ElMessageBox } from 'element-plus'
import { get, post, put, del, apiRequest } from '@/api/request'
import { listPermissionPacks } from '@/api/permissionPack'
import { useAuthStore } from '@/stores/auth'
import { useDesensitize } from '@/composables/useDesensitize'
import { usePermissionPackTransfer } from '@/composables/usePermissionPackTransfer'
import PermissionAssignmentDrawer from '@/components/permission/PermissionAssignmentDrawer.vue'
import { useDangerConfirm } from '@/composables/useDangerConfirm'
import UserTableCard from './components/UserTableCard.vue'
import PendingUsersDialog from './components/PendingUsersDialog.vue'
import ResetPasswordDialog from './components/ResetPasswordDialog.vue'
import PermissionPackExportDialog from './components/PermissionPackExportDialog.vue'
import UserFormDialog from './components/UserFormDialog.vue'
import { roleLabel } from '@/utils/roleAccess'
import { unwrapList } from '@/utils/unwrapList'

const authStore = useAuthStore()
const { confirmDanger } = useDangerConfirm()
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
// 对话框组件 ref：只用于把 `validate(cb)` 转发给 components/UserFormDialog.vue（不再直连 el-form）
const userFormRef = ref<InstanceType<typeof UserFormDialog> | null>(null)
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
  organization_id: null as number | string | null,
  permissions: [] as string[],
})

import { normalizeTreeNodes } from '@/utils/treeNormalizer'

import { Refresh, Search } from '@element-plus/icons-vue'
const orgTreeOptions = ref<any[]>([])

/**
 * 组织树节点 id 前缀还原。
 *
 * `normalizeTreeNodes` 为了 DOM 安全会给"纯数字开头的 id"加下划线前缀
 * （`3` → `_3`），而 `el-tree-select` 直接把这些 id 作为 v-model 的值。
 * 后端 `organization_id` 是 int，提交 `"_3"` 会被 Pydantic 判定为非法 → 422。
 * 因此提交前必须还原为数字；空值统一给 undefined（后端按"未选择"处理）。
 */
function toOrgIdPayload(value: unknown): number | undefined {
  if (value === null || value === undefined || value === '') return undefined
  const raw = String(value).replace(/^_/, '')
  const num = Number(raw)
  return Number.isFinite(num) ? num : undefined
}

/** 回显时把后端数字 id 转成树节点 id 形态（`3` → `_3`），否则选不中 */
function toOrgTreeValue(value: unknown): string | undefined {
  if (value === null || value === undefined || value === '') return undefined
  const raw = String(value)
  return /^[0-9]/.test(raw) ? `_${raw}` : raw
}

async function loadOrgTree(reportError = false) {
  try {
    const res: any = await get('/organizations/tree')
    // 兼容真实信封（res.data / res.items）与测试/旧版直接数组三种形态。
    // 旧实现只看 res.data，后端若改成 {items: tree} 会静默变空，用户表现为“没有组织可选”。
    // 统一走 unwrapList：裸数组 / data 数组 / items / data.items 全部兼容，
    // 且避免手写 `.data.items` 绕过 W5-T5 响应解包门禁。
    const raw = unwrapList<any>(res).items
    orgTreeOptions.value = normalizeTreeNodes(raw)
    return orgTreeOptions.value.length > 0
  } catch {
    // 保留空态，但不要阻断弹窗；打开弹窗时给出可操作提示，避免只看到空下拉。
    orgTreeOptions.value = []
    if (reportError) ElMessage.warning('组织列表加载失败，请检查后端服务后重试')
    return false
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
const ALL_ROLE_OPTIONS = [
  { value: 'super_admin', label: '超级管理员' },
  { value: 'admin', label: '系统管理员' },
  { value: 'user', label: '普通用户' },
  { value: 'viewer', label: '访客' },
] as const

// 契约口径（2026-10-31 对抗评审 + 契约修复）：登录响应此前对 role∈ADMIN_ROLES
// 的账号统一标记 is_superuser=true，前端无法用 is_superuser 区分部门级管理员与超管，
// 按 is_superuser 隐藏「超级管理员」选项是永不生效的死分支。后端现已修正为
// 严格口径（auth.py _user_info_is_superuser：仅 DB 标志或 role=='super_admin'），
// 但选项仍恒为 4 个（简洁且无损）：部门级管理员选择超管时由后端
// _assert_can_manage_super_admin 403 拦截，前端不做隐藏。
const roleOptions = ref<{ value: string; label: string }[]>([...ALL_ROLE_OPTIONS])

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

// 与后端 PasswordPolicy 同源的密码校验器（>=12 位 + 大小写 + 数字 + 白名单特殊字符）
const validatePassword = passwordValidator()

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '长度在 3 到 20 个字符', trigger: 'blur' },
  ],
  full_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  password: [
    // 密码策略统一走 @/utils/passwordPolicy（前端单一事实源，与后端 PasswordPolicy 对齐）。
    // 此前为 min:6 + 各自书写的字符类别规则，用户填 6~11 位或白名单外特殊字符时
    // 会出现「前端放行、后端 400」。
    { required: true, validator: validatePassword, trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  organization_id: [
    {
      // 与后端守卫对齐（POST/PUT /api/v1/users）：部门级管理员必须有组织，
      // 否则服务端 400。此处提前拦截，避免用户填完整张表单才被拒绝。
      validator: (_rule: any, value: number | null, callback: (error?: Error) => void) => {
        if ((formData.role === 'admin' || formData.role === 'super_admin') && !value) {
          return callback(new Error('管理员必须指定所属组织'))
        }
        callback()
      },
      trigger: ['change', 'blur'],
    },
  ],
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

// 与待审核弹窗、四角色契约共用同一展示名（历史角色值在 roleLabel 内归一化）
const getRoleName = (role: string) => roleLabel(role)

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

/**
 * 通过审核（启用账号）—— 闭合"待审核用户"闭环。
 *
 * 背景：该按钮此前只拉数据却没有任何弹窗消费 `pendingDialogVisible/pendingUsers`，
 * 属于"点了没反应"的死功能；`is_active=false` 在本系统既表示"待审核"也表示
 * "已禁用"，故列表口径与按钮文案保持"待审核（未启用）"语义，操作即启用账号。
 */
const approvePendingUser = async (row: any) => {
  try {
    await put(`/users/${row.id}`, { is_active: true })
    ElMessage.success(`已通过 ${row.username} 的审核`)
    pendingUsers.value = pendingUsers.value.filter((u) => u.id !== row.id)
    pendingCount.value = pendingUsers.value.length
    pendingDialogVisible.value = pendingUsers.value.length > 0
    await loadPendingCount()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '审核失败')
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

const handleAdd = async () => {
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
  // 组织可能在其它页签刚创建/改名：每次打开都刷新，避免只靠 onMounted 的旧快照。
  await loadOrgTree(true)
}

const handleEdit = async (row: any) => {
  isEdit.value = true
  dialogTitle.value = '编辑用户'
  currentUser.value = row
  Object.assign(formData, {
    ...row,
    // 树节点 id 带 `_` 前缀，回显必须转回树形态，否则下拉框选不中当前组织
    organization_id: toOrgTreeValue(row.organization_id) ?? null,
  })
  dialogVisible.value = true
  // 组织可能已变更；与活跃会话并行刷新，不阻塞表单回显。
  await Promise.all([loadOrgTree(true), loadUserSessions(row.id)])
}

const handleSubmit = async () => {
  if (!userFormRef.value) return

  await userFormRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (isEdit.value) {
        await put(`/users/${formData.id}`, {
          full_name: formData.full_name,
          // 空邮箱由后端统一归一到 NULL（单一事实源），前端不做二次判断
          email: formData.email,
          phone: formData.phone,
          department: formData.department,
          role: formData.role,
          is_active: formData.is_active,
          data_scope: formData.data_scope,
          organization_id: toOrgIdPayload(formData.organization_id),
        })
        ElMessage.success('用户更新成功')
      } else {
        await post('/users', {
          username: formData.username,
          full_name: formData.full_name,
          password: formData.password || undefined,
          // 空邮箱由后端统一归一到 NULL（单一事实源），前端不做二次判断
          email: formData.email,
          phone: formData.phone,
          department: formData.department,
          role: formData.role,
          data_scope: formData.data_scope,
          organization_id: toOrgIdPayload(formData.organization_id),
          is_active: formData.is_active,
          permissions: formData.permissions?.join(',') || '',
        })
        // 后端出于安全不回传密码；创建成功后展示管理员刚提交/自动生成的密码，
        // 避免“初始密码”提示分支永远不可达（旧实现读 res.data.data 是错误契约）。
        const initialPassword = formData.password
        if (initialPassword) {
          ElMessage.success(
            `用户创建成功！\n用户名: ${formData.username}\n初始密码: ${initialPassword}`
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

  // 批次 3：管理员重置他人密码属账号接管级操作 → 必须手工输入目标用户名才能执行
  const targetUsername = String(currentUser.value?.username ?? '')
  const confirmed = await confirmDanger({
    title: '确认重置密码',
    message:
      `即将重置用户「${targetUsername}」的密码。\n\n` +
      '执行后该用户全部登录令牌立即失效，且下次登录会被强制改密。\n' +
      '请确认你确实要接管该账号。',
    confirmButtonText: '确认重置',
    typedConfirmation: targetUsername,
  })
  if (!confirmed) return

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
    // 后端密码策略失败返回的是 {code, message, field}（而非 detail）；
    // 只读 detail 会把「具体哪条策略不满足」丢掉，退化成通用文案。
    const msg = error?.response?.data?.detail || error?.response?.data?.message || '重置密码失败'
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

// ── 权限包导入/导出（W5-T10 拆至 composables/usePermissionPackTransfer.ts） ──
// 用户列表刷新由本组件注入：导入成功后必须回到第 1 页，否则新数据落在看不到的页码上。
const {
  exportingPermPackage,
  importingPermPackage,
  permExportDialogVisible,
  permRolesLoading,
  permExportRoleOptions,
  permExportRoleNames,
  permExportPassword,
  permBindMachineCode,
  openPermExportDialog,
  doExportPermissionPackage,
  handleImportPermissionPackage,
} = usePermissionPackTransfer({
  reload: loadData,
  resetPage: () => {
    pagination.page = 1
  },
})

/** 权限包下拉命令分发（toolbar 的 export/import 两个入口） */
const handlePermPackageCommand = (command: string) => {
  if (command === 'export') openPermExportDialog()
  else if (command === 'import') handleImportPermissionPackage()
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

.search-card {
  margin-bottom: 20px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
}

// 用户表格/表头/操作列/分页等样式随模板迁至 components/UserTableCard.vue（scoped 样式
// 不会跨组件生效），此处只保留本组件仍有渲染的搜索卡与表单标签。
:deep(.el-form-item__label) {
  color: var(--color-text-primary);
}
</style>
