<template>
  <div class="permission-packs-page">
    <el-card>
      <div class="page-header">
        <div>
          <h2>权限包管理</h2>
          <p class="description">配置菜单权限套餐，绑定给普通用户后可批量控制其可见功能板块</p>
        </div>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>新建权限包
        </el-button>
      </div>

      <el-table v-loading="loading" :data="packs" border stripe>
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column label="描述" min-width="200">
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column label="菜单数" width="90" align="center">
          <template #default="{ row }">{{ row.menu_keys?.length ?? 0 }}</template>
        </el-table-column>
        <el-table-column prop="bound_user_count" label="绑定人数" width="90" align="center" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text type="primary" @click="openBind(row)">绑定用户</el-button>
            <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      :title="editingPack ? '编辑权限包' : '新建权限包'"
      width="640px"
      destroy-on-close
    >
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="editForm.name" placeholder="请输入权限包名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="2"
            placeholder="可选，说明该套餐用途"
          />
        </el-form-item>
        <el-form-item label="菜单权限">
          <el-tree
            ref="menuTreeRef"
            :data="menuTreeData"
            node-key="key"
            show-checkbox
            :default-checked-keys="editDefaultCheckedKeys"
            style="width: 100%; max-height: 320px; overflow: auto"
          >
            <template #default="{ data }">{{ data?.label || '' }}</template>
          </el-tree>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePack">保存</el-button>
      </template>
    </el-dialog>

    <!-- 绑定用户对话框 -->
    <el-dialog
      v-model="bindDialogVisible"
      :title="bindingPack ? `绑定用户到「${bindingPack.name}」` : '绑定用户'"
      width="720px"
      destroy-on-close
      @opened="preselectBoundUsers"
    >
      <el-table
        ref="bindTableRef"
        :data="bindableUsers"
        border
        @selection-change="(rows) => (bindSelection = rows)"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column label="姓名" min-width="120">
          <template #default="{ row }">{{ row.full_name || row.username }}</template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column label="角色" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.role === 'user'" type="primary">普通用户</el-tag>
            <el-tag v-else-if="row.role === 'viewer'" type="info">访客</el-tag>
            <el-tag v-else>{{ row.role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前权限包" min-width="120">
          <template #default="{ row }">
            <el-tag v-if="bindingPack && row.permission_pack_id === bindingPack.id" type="success"
              >本包</el-tag
            >
            <el-tag v-else-if="row.permission_pack_id" type="warning">其他包</el-tag>
            <span v-else>角色默认</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="bindDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="binding" @click="saveBind">保存绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  listPermissionPacks,
  createPermissionPack,
  updatePermissionPack,
  deletePermissionPack,
  bindPackUsers,
  unbindPackUsers,
  type PermissionPack,
} from '@/api/permissionPack'
import { get, apiRequest } from '@/api/request'

const packs = ref<PermissionPack[]>([])
const loading = ref(false)
const menuTreeData = ref<any[]>([])
const menuTreeRef = ref<any>()

// 叶子菜单 key 集合：父级 key（存在 children 的）不参与勾选回显
const leafKeySet = computed(() => {
  const parents = new Set<string>()
  const walk = (items: any[]) => {
    for (const item of items) {
      if (item.children?.length) {
        parents.add(item.key)
        walk(item.children)
      }
    }
  }
  walk(menuTreeData.value)
  const leaves = new Set<string>()
  const collect = (items: any[]) => {
    for (const item of items) {
      if (!parents.has(item.key)) leaves.add(item.key)
      if (item.children?.length) collect(item.children)
    }
  }
  collect(menuTreeData.value)
  return leaves
})

// ── 编辑对话框 ──
const editDialogVisible = ref(false)
const editingPack = ref<PermissionPack | null>(null)
const saving = ref(false)
const editForm = ref({ name: '', description: '', is_active: true })
const editDefaultCheckedKeys = ref<string[]>([])

function openCreate() {
  editingPack.value = null
  editForm.value = { name: '', description: '', is_active: true }
  editDefaultCheckedKeys.value = []
  editDialogVisible.value = true
}

function openEdit(row: any) {
  editingPack.value = row
  editForm.value = {
    name: row.name,
    description: row.description || '',
    is_active: row.is_active !== false,
  }
  // 仅叶子 key 回显（父级由树的半选态表达）
  editDefaultCheckedKeys.value = (row.menu_keys || []).filter((k: string) =>
    leafKeySet.value.has(k)
  )
  editDialogVisible.value = true
}

async function savePack() {
  const name = editForm.value.name.trim()
  if (!name) {
    ElMessage.error('请输入权限包名称')
    return
  }
  let menuKeys: string[] = editDefaultCheckedKeys.value
  const tree = menuTreeRef.value
  if (
    tree &&
    typeof tree.getCheckedKeys === 'function' &&
    typeof tree.getHalfCheckedKeys === 'function'
  ) {
    menuKeys = [...(tree.getCheckedKeys() as string[]), ...(tree.getHalfCheckedKeys() as string[])]
  }
  const payload = {
    name,
    description: editForm.value.description,
    menu_keys: menuKeys,
    is_active: editForm.value.is_active,
  }
  saving.value = true
  try {
    if (editingPack.value) {
      await updatePermissionPack(editingPack.value.id, payload)
    } else {
      await createPermissionPack(payload)
    }
    editDialogVisible.value = false
    await loadPacks()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// ── 删除 ──
async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除权限包「${row.name}」吗？已绑定用户将回落角色默认菜单。`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deletePermissionPack(row.id)
    await loadPacks()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

// ── 绑定用户 ──
const bindDialogVisible = ref(false)
const bindingPack = ref<PermissionPack | null>(null)
const binding = ref(false)
const bindableUsers = ref<any[]>([])
const bindSelection = ref<any[]>([])
const bindTableRef = ref<any>()

async function openBind(row: any) {
  bindingPack.value = row
  bindDialogVisible.value = true
  try {
    const res: any = await apiRequest({
      method: 'GET',
      url: '/users',
      params: { page: 1, page_size: 500 },
    })
    const users = res?.items || res?.data?.items || res || []
    // 仅普通用户/访客可绑定（管理员不受权限包限制）
    bindableUsers.value = (users as any[]).filter((u) => u.role === 'user' || u.role === 'viewer')
  } catch {
    ElMessage.error('加载用户列表失败')
  }
}

function preselectBoundUsers() {
  if (!bindingPack.value) return
  const table = bindTableRef.value
  if (!table || typeof table.toggleRowSelection !== 'function') return
  for (const u of bindableUsers.value) {
    table.toggleRowSelection(u, u.permission_pack_id === bindingPack.value.id)
  }
}

async function saveBind() {
  if (!bindingPack.value) return
  const selectedIds = new Set(bindSelection.value.map((u) => u.id))
  const boundIds = new Set(
    bindableUsers.value
      .filter((u) => u.permission_pack_id === bindingPack.value!.id)
      .map((u) => u.id)
  )
  const bindIds = [...selectedIds].filter((id) => !boundIds.has(id))
  const unbindIds = [...boundIds].filter((id) => !selectedIds.has(id))

  if (!bindIds.length && !unbindIds.length) {
    bindDialogVisible.value = false
    return
  }
  binding.value = true
  try {
    if (bindIds.length) await bindPackUsers(bindingPack.value.id, bindIds)
    if (unbindIds.length) await unbindPackUsers(bindingPack.value.id, unbindIds)
    bindDialogVisible.value = false
    await loadPacks()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '绑定保存失败')
  } finally {
    binding.value = false
  }
}

// ── 加载 ──
async function loadPacks() {
  loading.value = true
  try {
    packs.value = await listPermissionPacks()
  } catch {
    ElMessage.error('加载权限包列表失败')
    packs.value = []
  } finally {
    loading.value = false
  }
}

async function loadMenuTree() {
  try {
    const res: any = await get('/menus/all')
    menuTreeData.value = res.data || res || []
  } catch {
    // 回退到前端静态菜单配置
    try {
      const { MENU_CONFIG } = await import('@/config/menu-config')
      menuTreeData.value = MENU_CONFIG as unknown as any[]
    } catch {
      menuTreeData.value = []
    }
  }
}

function formatDateTime(v?: string | null) {
  if (!v) return '-'
  const d = new Date(v)
  if (isNaN(d.getTime())) return '-'
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

onMounted(() => {
  loadPacks()
  loadMenuTree()
})
</script>

<style scoped>
.permission-packs-page {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
}

.description {
  margin: 0;
  color: #909399;
  font-size: 13px;
}
</style>
