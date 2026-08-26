<template>
  <div class="role-management">
    <!-- 系统固定角色提示 -->
    <el-alert
      title="系统角色说明"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #default>
        系统固定角色为：<b>超级管理员</b>、<b>系统管理员</b>、<b>普通用户</b>、<b>访客</b>。
        用户注册时默认为「普通用户」。此处的 RBAC 角色用于细粒度权限包管理，
        不影响用户角色（users.role）的分配。
      </template>
    </el-alert>
    <el-card class="search-card">
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="角色名称">
          <el-input v-model="searchForm.name" placeholder="请输入角色名称" clearable />
        </el-form-item>
        <el-form-item label="角色编码">
          <el-input v-model="searchForm.code" placeholder="请输入角色编码" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable>
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
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
          <span class="title">角色列表</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            新增角色
          </el-button>
        </div>
      </template>

      <el-table :data="tableData" stripe border>
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="name" label="角色名称" min-width="150" />
        <el-table-column prop="code" label="角色编码" min-width="120" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column label="用户数" width="100" align="center">
          <template #default="{ row }">
            <el-button type="text" @click="handleViewUsers(row as any)">
              {{ row.userCount }} 人
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="160" />
        <el-table-column prop="status" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="handleEdit(row as any)">编辑</el-button>
            <el-button type="success" size="small" @click="handlePermission(row as any)"
              >权限</el-button
            >
            <el-button type="danger" size="small" @click="handleDelete(row as any)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        layout="total, prev, pager, next"
        class="pagination"
      />
    </el-card>

    <!-- 角色编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" :width="DIALOG_MD">
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="100px">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入角色名称" />
        </el-form-item>
        <el-form-item label="角色编码" prop="code">
          <el-input v-model="formData.code" placeholder="请输入角色编码" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch
            v-model="formData.status"
            active-value="active"
            inactive-value="inactive"
            active-text="启用"
            inactive-text="禁用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 用户列表对话框 -->
    <el-dialog
      v-model="usersDialogVisible"
      :title="`角色关联用户 - ${currentRole?.name}`"
      :width="DIALOG_MD"
    >
      <el-table v-loading="loadingUsers" :data="roleUsers" border stripe>
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="real_name" label="姓名" min-width="100">
          <template #default="{ row }">
            {{ ds(row.real_name, 'name') }}
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="150">
          <template #default="{ row }">
            {{ ds(row.email, 'email') }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="roleUsers.length === 0" style="text-align: center; padding: 40px; color: #999">
        暂无关联用户
      </div>
      <template #footer>
        <el-button @click="usersDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 权限配置对话框 -->
    <el-dialog v-model="permissionDialogVisible" title="权限配置" :width="DIALOG_LG">
      <div class="permission-header">
        <span
          >当前角色: <strong>{{ currentRole?.name }}</strong></span
        >
        <div>
          <el-button size="small" @click="checkAll">全选</el-button>
          <el-button size="small" @click="uncheckAll">全不选</el-button>
        </div>
      </div>
      <el-tree
        ref="treeRef"
        :data="menuTreeData"
        show-checkbox
        node-key="id"
        :props="treeProps"
        :default-checked-keys="defaultCheckedKeys"
        default-expand-all
        class="permission-tree"
      />
      <template #footer>
        <el-button @click="permissionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePermissions">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_MD, DIALOG_LG } from '@/config/dialog'
// ================================================================
// DEPRECATED: 角色管理功能已集成到 UserManagement.vue 中
// 通过用户管理页面的"角色/权限"按钮打开 PermissionAssignmentDrawer
// 本文件保留以供参考，不再独立路由访问（/system/roles → redirect /system/users）
// ================================================================
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, ElTree } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useDesensitize } from '@/composables/useDesensitize'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { get, post, put, del } from '@/api/request'

interface RoleItem {
  id: string
  name: string
  code: string
  description: string
  userCount: number
  createTime: string
  status: string
}

interface RoleUser {
  username: string
  real_name?: string
  email?: string
  is_active?: boolean
}

interface PermissionItem {
  code: string
  name: string
  description?: string
}

interface TreeNode {
  id: string
  label: string
  children?: TreeNode[]
}

const { ds } = useDesensitize()

const searchForm = reactive({
  name: '',
  code: '',
  status: '',
})

const tableData = ref<RoleItem[]>([])

const pagination = reactive({
  page: 1,
  size: 10,
  total: 0,
})

const dialogVisible = ref(false)
const permissionDialogVisible = ref(false)
const usersDialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const treeRef = ref<InstanceType<typeof ElTree> | null>(null)
const saving = ref(false)
const loadingUsers = ref(false)
const roleUsers = ref<RoleUser[]>([])

const formData = reactive({
  id: '',
  name: '',
  code: '',
  description: '',
  status: 'active',
})

const rules: FormRules = {
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 2, max: 20, message: '长度在 2 到 20 个字符', trigger: 'blur' },
  ],
  code: [
    { required: true, message: '请输入角色编码', trigger: 'blur' },
    {
      pattern: /^[A-Z_]+$/,
      message: '角色编码只能包含大写字母和下划线',
      trigger: 'blur',
    },
  ],
}

// 权限树数据 - 从后端动态加载
const menuTreeData = ref<TreeNode[]>([])

const treeProps = {
  children: 'children',
  label: 'label',
}

const defaultCheckedKeys = ref<string[]>([])
const currentRole = ref<RoleItem | null>(null)

// 获取所有叶子节点ID
const getAllLeafKeys = (nodes: TreeNode[]): string[] => {
  let keys: string[] = []
  nodes.forEach((node) => {
    if (node.children && node.children.length > 0) {
      keys = keys.concat(getAllLeafKeys(node.children))
    } else {
      keys.push(node.id)
    }
  })
  return keys
}

const checkAll = () => {
  const allKeys = getAllLeafKeys(menuTreeData.value)
  treeRef.value?.setCheckedKeys(allKeys)
}

const uncheckAll = () => {
  treeRef.value?.setCheckedKeys([])
}

const handleSearch = () => {
  loadRoles()
}

const handleReset = () => {
  Object.assign(searchForm, { name: '', code: '', status: '' })
  loadRoles()
}

const handleAdd = () => {
  isEdit.value = false
  dialogTitle.value = '新增角色'
  Object.assign(formData, {
    id: '',
    name: '',
    code: '',
    description: '',
    status: 'active',
  })
  dialogVisible.value = true
}

const handleEdit = (row: RoleItem) => {
  isEdit.value = true
  dialogTitle.value = '编辑角色'
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handlePermission = async (row: RoleItem) => {
  currentRole.value = row
  // 从后端加载角色已有权限
  try {
    const res = await get(`/rbac/roles/${row.id}`)
    const perms: string[] = res.data?.permissions || []
    defaultCheckedKeys.value = perms
  } catch {
    defaultCheckedKeys.value = []
  }
  permissionDialogVisible.value = true
}

const handleViewUsers = async (row: RoleItem) => {
  currentRole.value = row
  usersDialogVisible.value = true
  loadingUsers.value = true
  try {
    // 从后端加载该角色关联的用户
    const res = await get(`/rbac/roles/${row.id}/users`)
    roleUsers.value = (res.data || res?.users || []) as RoleUser[]
  } catch {
    roleUsers.value = []
  } finally {
    loadingUsers.value = false
  }
}

const handleDelete = async (row: RoleItem) => {
  try {
    // 检查是否有关联用户
    const res = await get(`/rbac/roles/${row.id}/users`)
    const users = res.data || res?.users || []
    if (users.length > 0) {
      await ElMessageBox.confirm(
        `该角色下还有 ${users.length} 个用户，删除后这些用户将失去此角色权限。确定继续删除？`,
        '警告',
        {
          type: 'warning',
          confirmButtonText: '确认删除',
          cancelButtonText: '取消',
        }
      )
    } else {
      await ElMessageBox.confirm(`确定删除角色 "${row.name}" 吗？`, '提示', {
        type: 'warning',
      })
    }

    await del(`/rbac/roles/${row.id}`)
    ElMessage.success('删除成功')
    loadRoles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleCancel = () => {
  dialogVisible.value = false
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      if (isEdit.value) {
        await put(`/rbac/roles/${formData.id}`, {
          name: formData.name,
          description: formData.description,
          is_active: formData.status === 'active',
        })
        ElMessage.success('已保存')
      } else {
        await post('/rbac/roles', {
          name: formData.name,
          description: formData.description,
          permissions: [],
          is_system: false,
        })
        ElMessage.success('已创建')
      }
      dialogVisible.value = false
      loadRoles()
    } catch {
      ElMessage.error('保存失败')
    } finally {
      saving.value = false
    }
  })
}

const savePermissions = async () => {
  if (!currentRole.value) return
  const checkedKeys = treeRef.value?.getCheckedKeys() || []
  saving.value = true
  try {
    // 保存角色权限到后端
    await put(`/rbac/roles/${currentRole.value.id}`, {
      permissions: checkedKeys,
    })
    ElMessage.success('已保存')
    permissionDialogVisible.value = false
  } catch {
    ElMessage.error('权限保存失败')
  } finally {
    saving.value = false
  }
}

/** 从后端加载权限列表并构建树形结构 */
async function loadPermissions() {
  try {
    const res = await get('/rbac/permissions')
    const categories: Record<string, PermissionItem[]> = res.categories || {}

    // 扩展权限类别中文映射，覆盖所有系统模块
    const categoryNames: Record<string, string> = {
      user: '用户管理',
      org: '组织管理',
      village: '帮扶村管理',
      project: '帮扶项目管理',
      school: '帮扶学校管理',
      funds: '经费管理',
      policy: '政策法规',
      rural_works: '乡村工作',
      approval: '审批管理',
      data_entry: '数据录入',
      data_import: '数据导入',
      data_verify: '数据校验审核',
      data_analysis: '数据统计分析',
      report: '报表管理',
      analytics: '数据分析',
      data_management: '数据管理',
      backup: '备份管理',
      quality: '数据质量监控',
      logs: '操作日志',
      system: '系统管理',
      role: '角色权限管理',
      audit: '安全审计',
      config: '系统配置',
      admin: '管理员',
    }

    const actionNames: Record<string, string> = {
      read: '查看',
      write: '编辑',
      create: '创建',
      update: '修改',
      delete: '删除',
      import: '导入',
      export: '导出',
      download: '下载',
      upload: '上传',
      publish: '发布',
      approve: '审批',
      reject: '驳回',
      backup: '备份',
      restore: '恢复',
      verify: '校验',
      monitor: '监控',
      manage_roles: '角色管理',
      manage_users: '用户管理',
      config: '配置',
      all: '全部权限',
    }

    const tree: TreeNode[] = []
    for (const [cat, perms] of Object.entries(categories)) {
      if (!perms || perms.length === 0) continue
      tree.push({
        id: cat,
        label: categoryNames[cat] || cat,
        children: perms.map((p: PermissionItem) => {
          const action = p.code?.split(':')[1] || p.name
          return {
            id: p.code,
            label: actionNames[action] || p.description || action,
          }
        }),
      })
    }
    menuTreeData.value = tree
  } catch (error) {
    // 加载失败使用空树
    menuTreeData.value = []
    ElMessage.error(getErrorMessage(error, '加载权限菜单失败，请稍后重试'))
  }
}

/** 加载角色列表 */
async function loadRoles() {
  try {
    const res: any = await get('/rbac/roles')
    // 后端返回 {success:true, data:[...], total} —— res.data 即角色数组
    const roles = res?.data || res?.items || []

    // 并行加载每个角色的用户数
    const rolesWithUserCount = await Promise.all(
      roles.map(async (r: unknown) => {
        const roleItem = r as Record<string, unknown>
        const rid = String(roleItem.id)
        let userCount = 0
        try {
          const userRes = await get(`/rbac/roles/${rid}/users`)
          const users = userRes.data || userRes?.users || []
          userCount = users.length
        } catch {
          // 如果接口不存在或失败，用户数为0
        }
        return {
          id: rid,
          name: String(roleItem.name || ''),
          code: String(roleItem.name || '')
            .toUpperCase()
            .replace(/\s+/g, '_'),
          description: String(roleItem.description || ''),
          userCount,
          createTime: String(roleItem.created_at || ''),
          status: roleItem.is_active !== false ? 'active' : 'inactive',
        }
      })
    )

    tableData.value = rolesWithUserCount
    pagination.total = tableData.value.length
  } catch (error) {
    tableData.value = []
    ElMessage.error(getErrorMessage(error, '加载角色列表失败，请稍后重试'))
  }
}

onMounted(() => {
  loadRoles()
  loadPermissions()
})
</script>

<style scoped>
.role-management {
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

.title {
  font-size: 16px;
  font-weight: bold;
  color: var(--color-text-inverse);
}

:deep(.el-dialog__title) {
  color: var(--color-text-inverse);
}

:deep(.el-table th.el-table__cell) {
  color: var(--color-text-inverse);
  background-color: transparent;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-card__header) {
  padding: 15px 20px;
  border-bottom: 1px solid var(--color-border-light);
  box-sizing: border-box;
}

:deep(.el-tree) {
  background: var(--color-bg-card);
  color: var(--color-text-regular);
}

.permission-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eee;
}

.permission-header strong {
  color: var(--color-primary);
}

.permission-tree {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 10px;
}
</style>
