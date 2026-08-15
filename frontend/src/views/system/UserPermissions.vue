<template>
  <div class="user-permissions-page">
    <!-- 左侧面板：组织机构树 -->
    <div class="left-panel">
      <el-card class="org-card">
        <template #header>
          <div class="card-header">
            <span class="title">组织机构</span>
            <el-button size="small" text @click="refreshTree">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </div>
        </template>
        <div v-loading="treeLoading" class="tree-container">
          <el-tree
            ref="treeRef"
            :data="treeData"
            :props="treeProps"
            node-key="id"
            :expand-on-click-node="false"
            lazy
            :load="loadNode"
            :highlight-current="true"
            @node-click="handleNodeClick"
          >
            <template #default="{ data }">
              <span class="tree-node">
                <el-icon><FolderOpened /></el-icon>
                <span class="node-label">{{ data.name }}</span>
              </span>
            </template>
          </el-tree>
          <el-empty
            v-if="!treeLoading && treeData.length === 0"
            description="暂无组织机构数据"
            :image-size="80"
          />
        </div>
      </el-card>
    </div>

    <!-- 右侧面板：用户权限管理 -->
    <div class="right-panel">
      <!-- 未选择组织时的提示 -->
      <div v-if="!selectedOrgId" class="no-selection">
        <el-empty description="请在左侧选择组织机构" :image-size="120">
          <template #image>
            <el-icon :size="80" color="#c0c4cc"><User /></el-icon>
          </template>
        </el-empty>
      </div>

      <!-- 已选择组织的管理面板 -->
      <template v-else>
        <!-- 组织标题栏 -->
        <div class="org-header">
          <div class="org-title">
            <el-icon :size="20"><OfficeBuilding /></el-icon>
            <span class="org-name">{{ selectedOrg?.name || '未命名组织' }}</span>
          </div>
          <el-tag type="info" size="small">用户数: {{ userCount }}</el-tag>
        </div>

        <!-- Tab 切换 -->
        <el-tabs v-model="activeTab" @tab-change="handleTabChange">
          <!-- Tab 1: 组织分配 -->
          <el-tab-pane label="组织分配" name="org-assign">
            <div class="tab-toolbar">
              <el-button type="primary" size="small" @click="openAddUserDialog">
                <el-icon><Plus /></el-icon>
                添加用户
              </el-button>
              <el-button size="small" @click="loadOrgUsers">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
            <el-table
              v-loading="usersLoading"
              :data="orgUsers"
              stripe
              border
              empty-text="该组织下暂无用户"
            >
              <el-table-column prop="user_id" label="用户ID" width="80" align="center" />
              <el-table-column prop="username" label="用户名" min-width="130" />
              <el-table-column prop="org_role" label="组织角色" min-width="120">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.is_primary ? 'success' : 'info'">
                    {{ row.org_role || 'member' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="is_primary" label="主组织" width="90" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.is_primary" type="success" size="small">是</el-tag>
                  <span v-else class="text-muted">否</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100" align="center" fixed="right">
                <template #default="{ row }">
                  <el-popconfirm
                    title="确定从组织中移除此用户？"
                    confirm-button-text="确定"
                    cancel-button-text="取消"
                    @confirm="handleRemoveUser(row)"
                  >
                    <template #reference>
                      <el-button type="danger" size="small" link>
                        <el-icon><Delete /></el-icon>
                        移除
                      </el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- Tab 2: 角色分配 -->
          <el-tab-pane label="角色分配" name="role-assign">
            <div v-loading="rolesLoading" class="role-list">
              <el-empty
                v-if="orgUsersWithRoles.length === 0"
                description="该组织下暂无用户"
                :image-size="80"
              />
              <el-card
                v-for="user in orgUsersWithRoles"
                :key="user.user_id"
                class="role-user-card"
                shadow="never"
              >
                <div class="role-user-header">
                  <span class="role-username">
                    <el-icon><User /></el-icon>
                    {{ user.username }}
                  </span>
                  <el-button size="small" type="primary" text @click="openAddRoleDialog(user)">
                    <el-icon><Plus /></el-icon>
                    添加角色
                  </el-button>
                </div>
                <div class="role-tags">
                  <el-tag
                    v-for="role in user.roles"
                    :key="role.id || role.role_id"
                    closable
                    size="small"
                    :type="getRoleTagType(role)"
                    @close="handleRemoveRole(user, role)"
                  >
                    {{ role.name || role.role_id || role }}
                  </el-tag>
                  <span v-if="!user.roles || user.roles.length === 0" class="text-muted"
                    >暂无角色</span
                  >
                </div>
              </el-card>
            </div>
          </el-tab-pane>

          <!-- Tab 3: 权限授予 -->
          <el-tab-pane label="权限授予" name="perm-grant">
            <div v-loading="permsLoading" class="perm-list">
              <el-empty
                v-if="orgUsersWithPerms.length === 0"
                description="该组织下暂无用户"
                :image-size="80"
              />
              <el-card
                v-for="user in orgUsersWithPerms"
                :key="user.user_id"
                class="perm-user-card"
                shadow="never"
              >
                <div class="perm-user-header">
                  <span class="perm-username">
                    <el-icon><User /></el-icon>
                    {{ user.username }}
                  </span>
                  <el-button size="small" type="primary" text @click="openGrantPermDialog(user)">
                    <el-icon><Plus /></el-icon>
                    授予权限
                  </el-button>
                </div>
                <div class="perm-tags">
                  <el-tag
                    v-for="perm in user.permissions"
                    :key="perm"
                    closable
                    size="small"
                    type="warning"
                    @close="handleRevokePermission(user, perm)"
                  >
                    {{ perm }}
                  </el-tag>
                  <span v-if="!user.permissions || user.permissions.length === 0" class="text-muted"
                    >暂无权限</span
                  >
                </div>
              </el-card>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </div>

    <!-- 对话框：添加用户到组织 -->
    <el-dialog
      v-model="addUserDialogVisible"
      title="添加用户到组织"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form ref="addUserFormRef" :model="addUserForm" :rules="addUserRules" label-width="100px">
        <el-form-item label="选择用户" prop="user_id">
          <el-select
            v-model="addUserForm.user_id"
            placeholder="请选择用户"
            filterable
            style="width: 100%"
            :loading="allUsersLoading"
          >
            <el-option
              v-for="user in allUsers"
              :key="user.id"
              :label="`${user.username} (${user.name || user.id})`"
              :value="Number(user.id)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标组织">
          <el-input :model-value="selectedOrg?.name || ''" disabled />
        </el-form-item>
        <el-form-item label="组织角色" prop="role">
          <el-select v-model="addUserForm.role" placeholder="请选择组织角色" style="width: 100%">
            <el-option label="成员 (member)" value="member" />
            <el-option label="管理员 (admin)" value="admin" />
            <el-option label="观察者 (viewer)" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item label="设为主组织">
          <el-switch v-model="addUserForm.is_primary" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addUserDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addUserSubmitting" @click="handleAddUserSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 对话框：添加角色 -->
    <el-dialog
      v-model="addRoleDialogVisible"
      title="为用户添加角色"
      width="480px"
      :close-on-click-modal="false"
    >
      <div class="dialog-user-info">
        用户: <strong>{{ addRoleTarget?.username }}</strong>
      </div>
      <el-form
        ref="addRoleFormRef"
        :model="addRoleForm"
        :rules="addRoleRules"
        label-width="100px"
        class="dialog-form"
      >
        <el-form-item label="角色" prop="role_id">
          <el-select v-model="addRoleForm.role_id" placeholder="请选择角色" style="width: 100%">
            <el-option
              v-for="role in commonRoles"
              :key="role.value"
              :label="role.label"
              :value="role.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="过期时间">
          <el-date-picker
            v-model="addRoleForm.expires_at"
            type="datetime"
            placeholder="留空表示永不过期"
            style="width: 100%"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addRoleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addRoleSubmitting" @click="handleAddRoleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 对话框：授予权限 -->
    <el-dialog
      v-model="grantPermDialogVisible"
      title="授予用户权限"
      width="480px"
      :close-on-click-modal="false"
    >
      <div class="dialog-user-info">
        用户: <strong>{{ grantPermTarget?.username }}</strong>
      </div>
      <el-form
        ref="grantPermFormRef"
        :model="grantPermForm"
        :rules="grantPermRules"
        label-width="100px"
        class="dialog-form"
      >
        <el-form-item label="权限标识" prop="permission">
          <el-input
            v-model="grantPermForm.permission"
            placeholder="例如: user:read, project:write"
          />
        </el-form-item>
        <el-form-item label="过期时间">
          <el-date-picker
            v-model="grantPermForm.expires_at"
            type="datetime"
            placeholder="留空表示永不过期"
            style="width: 100%"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="grantPermDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="grantPermSubmitting" @click="handleGrantPermSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type TabPaneName,
} from 'element-plus'
import { Plus, Delete, Refresh, User, FolderOpened, OfficeBuilding } from '@element-plus/icons-vue'
import { userPermissionsApi, type OrganizationTreeNode } from '@/api/userPermissions'
import { listUsers, type ManagedUser } from '@/api/userManagement'

// ==================== 类型定义 ====================

interface OrgUser {
  user_id: number
  username: string
  org_role: string
  is_primary: boolean
  roles: RoleItem[]
  permissions: string[]
}

interface RoleItem {
  id?: string | number
  role_id?: string
  name?: string
}

// ==================== 组织机构树 ====================

const treeRef = ref()
const treeLoading = ref(false)
const treeData = ref<OrganizationTreeNode[]>([])
const selectedOrgId = ref<number | null>(null)
const selectedOrg = ref<OrganizationTreeNode | null>(null)

const treeProps = {
  label: 'name',
  children: 'children',
  isLeaf: 'leaf',
}

import { normalizeTreeNodes } from '@/utils/treeNormalizer'

/** 懒加载树节点 */
const loadNode = (node: any, resolve: (data: any[]) => void) => {
  if (node.level === 0) {
    // 根级别：加载顶级组织
    treeLoading.value = true
    userPermissionsApi
      .getOrganizationTree()
      .then((res) => {
        if (res.success && Array.isArray(res.data)) {
          resolve(normalizeTreeNodes(res.data))
        } else {
          resolve([])
        }
      })
      .catch(() => {
        ElMessage.error('加载组织树失败')
        resolve([])
      })
      .finally(() => {
        treeLoading.value = false
      })
  } else {
    // 子节点：加载指定父节点下的组织
    userPermissionsApi
      .getOrganizationTree(node.data.id)
      .then((res) => {
        if (res.success && Array.isArray(res.data)) {
          resolve(normalizeTreeNodes(res.data))
        } else {
          resolve([])
        }
      })
      .catch(() => {
        ElMessage.error('加载子组织失败')
        resolve([])
      })
  }
}

/** 树节点点击 */
const handleNodeClick = (data: OrganizationTreeNode) => {
  selectedOrg.value = data
  selectedOrgId.value = data.id
  activeTab.value = 'org-assign'
  loadOrgUsers()
}

/** 刷新组织树 */
const refreshTree = () => {
  treeData.value = []
  selectedOrgId.value = null
  selectedOrg.value = null
  nextTick(() => {
    // 重新加载根节点需要通过 tree 组件实例触发
    if (treeRef.value) {
      treeRef.value.store.nodesMap = {}
      treeRef.value.root.childNodes = []
      treeRef.value.root.loadData()
    }
  })
}

// ==================== 标签页状态 ====================

const activeTab = ref('org-assign')
const usersLoading = ref(false)
const rolesLoading = ref(false)
const permsLoading = ref(false)

/** Tab 切换时按需加载数据 */
const handleTabChange = (tabName: TabPaneName) => {
  if (!selectedOrgId.value) return
  if (tabName === 'org-assign') {
    loadOrgUsers()
  } else if (tabName === 'role-assign') {
    loadOrgUsersWithRoles()
  } else if (tabName === 'perm-grant') {
    loadOrgUsersWithPermissions()
  }
}

// ==================== 组织下的用户数据 ====================

const orgUsers = ref<OrgUser[]>([])
const userCount = computed(() => orgUsers.value.length)

/** 加载组织下的用户（基础信息） */
const loadOrgUsers = async () => {
  if (!selectedOrgId.value) return
  usersLoading.value = true
  try {
    const res = await userPermissionsApi.getOrganizationUsers(selectedOrgId.value, false)
    if (res.success && Array.isArray(res.data)) {
      orgUsers.value = res.data.map((item: any) => ({
        user_id: item.user_id || item.id,
        username: item.username || '',
        org_role: item.role || item.org_role || 'member',
        is_primary: Boolean(item.is_primary),
        roles: [],
        permissions: [],
      }))
    } else {
      orgUsers.value = []
    }
  } catch {
    ElMessage.error('加载组织用户失败')
    orgUsers.value = []
  } finally {
    usersLoading.value = false
  }
}

// ==================== Tab 1: 组织分配 ====================

const addUserDialogVisible = ref(false)
const addUserSubmitting = ref(false)
const addUserFormRef = ref<FormInstance>()
const addUserForm = reactive({
  user_id: null as number | null,
  role: 'member',
  is_primary: false,
})

const addUserRules: FormRules = {
  user_id: [{ required: true, message: '请选择用户', trigger: 'change' }],
  role: [{ required: true, message: '请输入或选择角色', trigger: 'blur' }],
}

/** 可用于分配的用户列表 */
const allUsers = ref<ManagedUser[]>([])
const allUsersLoading = ref(false)

const openAddUserDialog = async () => {
  addUserForm.user_id = null
  addUserForm.role = 'member'
  addUserForm.is_primary = false
  addUserDialogVisible.value = true

  // 加载全部用户列表
  if (allUsers.value.length === 0) {
    allUsersLoading.value = true
    try {
      const res = await listUsers({ page_size: 200 })
      if (res.success && res.data?.items) {
        allUsers.value = res.data.items
      }
    } catch {
      ElMessage.error('加载用户列表失败')
    } finally {
      allUsersLoading.value = false
    }
  }
}

const handleAddUserSubmit = async () => {
  if (!addUserFormRef.value) return
  await addUserFormRef.value.validate(async (valid) => {
    if (!valid) return
    if (!selectedOrgId.value || !addUserForm.user_id) return

    addUserSubmitting.value = true
    try {
      await userPermissionsApi.assignOrganization({
        user_id: addUserForm.user_id,
        organization_id: selectedOrgId.value,
        role: addUserForm.role,
        is_primary: addUserForm.is_primary,
      })
      ElMessage.success('用户已添加到组织')
      addUserDialogVisible.value = false
      await loadOrgUsers()
    } catch {
      ElMessage.error('添加用户失败')
    } finally {
      addUserSubmitting.value = false
    }
  })
}

/** 从组织中移除用户 */
const handleRemoveUser = async (row: any) => {
  if (!selectedOrgId.value) return
  try {
    await userPermissionsApi.removeOrganization(row.user_id, selectedOrgId.value)
    ElMessage.success('用户已从组织中移除')
    await loadOrgUsers()
  } catch {
    ElMessage.error('移除用户失败')
  }
}

// ==================== Tab 2: 角色分配 ====================

/** 带角色信息的用户列表 */
const orgUsersWithRoles = ref<OrgUser[]>([])

/** 常用角色选项（角色精简：4 个实用角色） */
const commonRoles = [
  { label: '超级管理员 (super_admin)', value: 'super_admin' },
  { label: '管理员 (admin)', value: 'admin' },
  { label: '普通用户 (user)', value: 'user' },
  { label: '访客 (viewer)', value: 'viewer' },
]

const addRoleDialogVisible = ref(false)
const addRoleSubmitting = ref(false)
const addRoleFormRef = ref<FormInstance>()
const addRoleTarget = ref<OrgUser | null>(null)
const addRoleForm = reactive({
  role_id: '',
  expires_at: '' as string,
})

const addRoleRules: FormRules = {
  role_id: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

/** 加载每个用户的角色信息 */
const loadOrgUsersWithRoles = async () => {
  if (!selectedOrgId.value) return
  rolesLoading.value = true
  try {
    const res = await userPermissionsApi.getOrganizationUsers(selectedOrgId.value, false)
    if (res.success && Array.isArray(res.data)) {
      const users = res.data.map((item: any) => ({
        user_id: item.user_id || item.id,
        username: item.username || '',
        org_role: item.role || item.org_role || 'member',
        is_primary: Boolean(item.is_primary),
        roles: [] as RoleItem[],
        permissions: [] as string[],
      }))

      // 并行加载所有用户的角色
      await Promise.all(
        users.map(async (user) => {
          try {
            const roleRes = await userPermissionsApi.getUserRoles(user.user_id)
            if (roleRes.success && Array.isArray(roleRes.data)) {
              user.roles = roleRes.data
            }
          } catch {
            // 忽略单个用户的加载失败
          }
        })
      )

      orgUsersWithRoles.value = users
    } else {
      orgUsersWithRoles.value = []
    }
  } catch {
    ElMessage.error('加载组织用户失败')
    orgUsersWithRoles.value = []
  } finally {
    rolesLoading.value = false
  }
}

const getRoleTagType = (role: RoleItem): 'success' | 'warning' | 'info' | 'danger' | 'primary' => {
  const name = role.name || role.role_id || ''
  if (name.includes('super_admin') || name.includes('admin')) return 'danger'
  if (name.includes('manager')) return 'warning'
  if (name.includes('approval')) return 'success'
  return 'info'
}

const openAddRoleDialog = (user: OrgUser) => {
  addRoleTarget.value = user
  addRoleForm.role_id = ''
  addRoleForm.expires_at = ''
  addRoleDialogVisible.value = true
}

const handleAddRoleSubmit = async () => {
  if (!addRoleFormRef.value) return
  await addRoleFormRef.value.validate(async (valid) => {
    if (!valid) return
    if (!addRoleTarget.value) return

    addRoleSubmitting.value = true
    try {
      await userPermissionsApi.assignRole({
        user_id: addRoleTarget.value.user_id,
        role_id: addRoleForm.role_id,
        expires_at: addRoleForm.expires_at || undefined,
      })
      ElMessage.success('角色已分配')
      addRoleDialogVisible.value = false
      await loadOrgUsersWithRoles()
    } catch {
      ElMessage.error('分配角色失败')
    } finally {
      addRoleSubmitting.value = false
    }
  })
}

/** 移除用户角色 */
const handleRemoveRole = async (user: OrgUser, role: RoleItem) => {
  const roleId = (role.role_id || role.id || '').toString()
  const roleName = role.name || roleId

  try {
    await ElMessageBox.confirm(
      `确定移除用户 "${user.username}" 的角色 "${roleName}"？`,
      '确认操作',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return // 用户取消
  }

  try {
    await userPermissionsApi.removeRole(user.user_id, roleId)
    ElMessage.success('角色已移除')
    await loadOrgUsersWithRoles()
  } catch {
    ElMessage.error('移除角色失败')
  }
}

// ==================== Tab 3: 权限授予 ====================

/** 带权限信息的用户列表 */
const orgUsersWithPerms = ref<OrgUser[]>([])

const grantPermDialogVisible = ref(false)
const grantPermSubmitting = ref(false)
const grantPermFormRef = ref<FormInstance>()
const grantPermTarget = ref<OrgUser | null>(null)
const grantPermForm = reactive({
  permission: '',
  expires_at: '' as string,
})

const grantPermRules: FormRules = {
  permission: [
    { required: true, message: '请输入权限标识', trigger: 'blur' },
    {
      pattern: /^[a-z_]+:[a-z_]+$/i,
      message: '格式: module:action (如 user:read)',
      trigger: 'blur',
    },
  ],
}

/** 加载每个用户的权限信息 */
const loadOrgUsersWithPermissions = async () => {
  if (!selectedOrgId.value) return
  permsLoading.value = true
  try {
    const res = await userPermissionsApi.getOrganizationUsers(selectedOrgId.value, false)
    if (res.success && Array.isArray(res.data)) {
      const users = res.data.map((item: any) => ({
        user_id: item.user_id || item.id,
        username: item.username || '',
        org_role: item.role || item.org_role || 'member',
        is_primary: Boolean(item.is_primary),
        roles: [] as RoleItem[],
        permissions: [] as string[],
      }))

      // 并行加载所有用户的权限
      await Promise.all(
        users.map(async (user) => {
          try {
            const permRes = await userPermissionsApi.getUserPermissions(user.user_id)
            if (permRes.success && Array.isArray(permRes.data)) {
              user.permissions = permRes.data
            }
          } catch {
            // 忽略单个用户的加载失败
          }
        })
      )

      orgUsersWithPerms.value = users
    } else {
      orgUsersWithPerms.value = []
    }
  } catch {
    ElMessage.error('加载组织用户失败')
    orgUsersWithPerms.value = []
  } finally {
    permsLoading.value = false
  }
}

const openGrantPermDialog = (user: OrgUser) => {
  grantPermTarget.value = user
  grantPermForm.permission = ''
  grantPermForm.expires_at = ''
  grantPermDialogVisible.value = true
}

const handleGrantPermSubmit = async () => {
  if (!grantPermFormRef.value) return
  await grantPermFormRef.value.validate(async (valid) => {
    if (!valid) return
    if (!grantPermTarget.value) return

    grantPermSubmitting.value = true
    try {
      await userPermissionsApi.grantPermission({
        user_id: grantPermTarget.value.user_id,
        permission: grantPermForm.permission,
        expires_at: grantPermForm.expires_at || undefined,
      })
      ElMessage.success('权限已授予')
      grantPermDialogVisible.value = false
      await loadOrgUsersWithPermissions()
    } catch {
      ElMessage.error('授予权限失败')
    } finally {
      grantPermSubmitting.value = false
    }
  })
}

/** 撤销用户权限 */
const handleRevokePermission = async (user: OrgUser, perm: string) => {
  try {
    await ElMessageBox.confirm(`确定撤销用户 "${user.username}" 的权限 "${perm}"？`, '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }

  try {
    await userPermissionsApi.revokePermission(user.user_id, perm)
    ElMessage.success('权限已撤销')
    await loadOrgUsersWithPermissions()
  } catch {
    ElMessage.error('撤销权限失败')
  }
}

// ==================== 初始化 ====================

onMounted(() => {
  // 组织树由 el-tree 的 lazy load 机制自动加载根节点
})
</script>

<style scoped>
.user-permissions-page {
  display: flex;
  height: 100%;
  gap: 16px;
  padding: 16px;
  background-color: #f5f7fa;
}

/* 左侧面板 */
.left-panel {
  width: 300px;
  min-width: 280px;
  flex-shrink: 0;
}

.org-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.org-card :deep(.el-card__body) {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.tree-container {
  min-height: 200px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header .title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  flex: 1;
  overflow: hidden;
}

.tree-node .el-icon {
  color: var(--color-primary);
  flex-shrink: 0;
}

.tree-node .node-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 右侧面板 */
.right-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #ebeef5;
  overflow: hidden;
}

.no-selection {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.org-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px 10px;
  border-bottom: 1px solid #ebeef5;
}

.org-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.org-title .el-icon {
  color: var(--color-primary);
}

.org-name {
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Tab 内容 */
.tab-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

/* 角色分配 Tab */
.role-list,
.perm-list {
  max-height: 520px;
  overflow-y: auto;
}

.role-user-card,
.perm-user-card {
  margin-bottom: 12px;
}

.role-user-header,
.perm-user-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.role-username,
.perm-username {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.role-tags,
.perm-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 28px;
}

/* Dialog 样式 */
.dialog-user-info {
  margin-bottom: 16px;
  padding: 8px 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
  font-size: 14px;
}

.dialog-user-info strong {
  color: var(--color-primary);
}

.dialog-form {
  margin-top: 4px;
}

/* 通用 */
.text-muted {
  color: var(--color-info);
  font-size: 13px;
}

/* Element Plus Overrides */
:deep(.el-tabs__content) {
  padding: 12px 20px;
}

:deep(.el-table) {
  font-size: 13px;
}
</style>
