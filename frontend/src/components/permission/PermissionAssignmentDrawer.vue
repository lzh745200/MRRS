<template>
  <el-drawer
    v-model="visible"
    :title="`权限配置 - ${user?.username || ''}`"
    size="680px"
    direction="rtl"
    @close="handleClose"
  >
    <el-tabs v-model="activeTab" type="border-card">
      <!-- Tab 1: 角色分配 -->
      <el-tab-pane label="角色分配" name="roles">
        <RoleTagsPanel
          ref="rolePanelRef"
          :user-id="user?.id!"
          :all-roles="allRoles"
          @assigned="refreshPermissions"
          @removed="refreshPermissions"
        />
      </el-tab-pane>

      <!-- Tab 2: 权限配置 -->
      <el-tab-pane label="权限配置" name="permissions">
        <el-alert
          v-if="permissionsLoadFailed"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        >
          权限数据加载失败，请关闭面板后重试。保存操作已被禁用。
        </el-alert>
        <PermissionTreePanel :permissions="currentPermissions" @change="onPermissionsChange" />
        <div style="margin-top: 16px; text-align: right">
          <el-button
            type="primary"
            :loading="savingPermissions"
            :disabled="permissionsLoadFailed || savingPermissions"
            @click="savePermissions"
          >
            保存权限
          </el-button>
        </div>
      </el-tab-pane>

      <!-- Tab 3: 菜单可见性 -->
      <el-tab-pane label="菜单可见性" name="menus">
        <MenuVisibilityPanel
          v-if="user"
          :user-id="user.id"
          :username="user.username"
          :role="user.role"
          :role-default-keys="roleDefaultKeys"
          :is-customized="isMenuCustomized"
          :current-menu-keys="currentMenuKeys"
          @saved="refreshMenuConfig"
        />
      </el-tab-pane>

      <!-- Tab 4: 遗留角色 -->
      <el-tab-pane label="系统角色" name="legacy">
        <div class="legacy-section">
          <el-alert type="warning" :closable="false" style="margin-bottom: 16px">
            系统角色为向后兼容保留。新权限配置请使用"角色分配"和"权限配置"。
          </el-alert>

          <el-form label-width="100px" :model="legacyForm">
            <el-form-item label="系统角色">
              <el-select v-model="legacyForm.role" placeholder="选择系统角色" style="width: 240px">
                <el-option label="超级管理员" value="super_admin" />
                <el-option label="管理员" value="admin" />
                <el-option label="普通用户" value="user" />
                <el-option label="访客" value="viewer" />
              </el-select>
            </el-form-item>
            <el-form-item label="数据范围">
              <el-select v-model="legacyForm.data_scope" style="width: 240px">
                <el-option label="全部数据" value="all" />
                <el-option label="本组织及子组织" value="org_children" />
                <el-option label="本组织" value="org" />
                <el-option label="仅自己" value="self" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingLegacy" @click="saveLegacyRole">
                保存
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { get, post, put } from '@/api/request'
import PermissionTreePanel from './PermissionTreePanel.vue'
import RoleTagsPanel from './RoleTagsPanel.vue'
import MenuVisibilityPanel from './MenuVisibilityPanel.vue'

interface UserInfo {
  id: number
  username: string
  full_name?: string
  role?: string
  data_scope?: string
  permissions?: string
  allowed_menus?: string | null
}

interface RbacRole {
  id: string
  name: string
  description?: string
  is_system?: boolean
  is_active?: boolean
  priority?: number
  permissions?: string[]
}

const props = defineProps<{
  modelValue: boolean
  user: UserInfo | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const activeTab = ref('roles')
const savingPermissions = ref(false)
const savingLegacy = ref(false)

const rolePanelRef = ref()
const permissionsLoadFailed = ref(false)
const currentPermissions = ref<string[]>([])
const allRoles = ref<RbacRole[]>([])
const roleDefaultKeys = ref<string[]>([])
const currentMenuKeys = ref<string[]>([])
const isMenuCustomized = ref(false)

const legacyForm = ref({
  role: '',
  data_scope: '',
})

// ── 加载数据 ──

async function loadAllRoles() {
  try {
    const res = await get('/rbac/roles')
    allRoles.value = (res.data || res || []) as RbacRole[]
  } catch {
    allRoles.value = []
  }
}

async function loadCurrentPermissions() {
  if (!props.user?.id) return
  try {
    const res = await get(`/rbac/user/${props.user.id}/permissions`)
    const payload = res.data || res
    const perms = payload?.permissions || payload || []
    currentPermissions.value = Array.isArray(perms) ? perms : []
    permissionsLoadFailed.value = false
  } catch {
    permissionsLoadFailed.value = true
    currentPermissions.value = [] // 清空过期数据，防止前一个用户权限残留
  }
}

async function loadMenuConfig() {
  if (!props.user?.id) return
  try {
    const res = await get(`/menus/user-menus/${props.user.id}`)
    const data = res.data || res
    if (data) {
      currentMenuKeys.value = data.menu_keys || []
      isMenuCustomized.value = data.is_customized || false
      roleDefaultKeys.value = data.role_default_keys || []
    }
  } catch {
    currentMenuKeys.value = []
  }
}

function refreshPermissions() {
  loadCurrentPermissions()
}

function refreshMenuConfig() {
  loadMenuConfig()
}

function onPermissionsChange(perms: string[]) {
  currentPermissions.value = perms
}

// ── 保存操作 ──

async function savePermissions() {
  if (!props.user?.id || permissionsLoadFailed.value) return
  savingPermissions.value = true
  try {
    // 原子性保存：后端在单个事务内完成撤销+授予
    const res = await post('/rbac/save-permissions', {
      user_id: props.user.id,
      permissions: currentPermissions.value,
    })
    if (!visible.value) return // 抽屉已关闭，中止后续操作

    // 后端 /rbac/save-permissions 裸返回 {success, granted, revoked, skipped, failed, message}
    // （无 envelope data 键），res 即结果对象
    const data = res || {}
    if (!data.success) {
      const detail = data.message || data.detail || '权限保存失败'
      ElMessage.error(String(detail))
      return
    }

    const granted = (data.granted as string[]) || []
    const revoked = (data.revoked as string[]) || []
    const skipped = (data.skipped as string[]) || []
    const failed = (data.failed as string[]) || []

    if (failed.length === 0) {
      const parts: string[] = ['权限保存成功']
      if (granted.length > 0) parts.push(`(授予 ${granted.length} 项)`)
      if (revoked.length > 0) parts.push(`(撤销 ${revoked.length} 项)`)
      if (skipped.length > 0) parts.push(`(${skipped.length} 项已存在，已跳过)`)
      ElMessage.success(parts.join(' '))
    } else {
      ElMessage.warning(`权限保存部分失败: ${failed.join(', ')}`)
    }
    emit('saved')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '权限保存失败')
  } finally {
    savingPermissions.value = false
  }
}

async function saveLegacyRole() {
  if (!props.user?.id) return
  savingLegacy.value = true
  try {
    await put(`/users/${props.user.id}/permissions`, {
      role: legacyForm.value.role,
      data_scope: legacyForm.value.data_scope,
    })
    ElMessage.success('系统角色保存成功')
    emit('saved')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    savingLegacy.value = false
  }
}

function handleClose() {
  visible.value = false
}

// ── 监听用户变化 ──

watch(
  () => props.user,
  async (user) => {
    if (user) {
      legacyForm.value = {
        role: user.role || 'user',
        data_scope: user.data_scope || 'org',
      }
      await Promise.all([loadAllRoles(), loadCurrentPermissions(), loadMenuConfig()])
      // 加载已分配角色
      setTimeout(() => rolePanelRef.value?.loadAssignedRoles?.(), 200)
    }
  },
  { immediate: true }
)

// 暴露给父组件
defineExpose({
  refreshAll: () => {
    loadCurrentPermissions()
    loadMenuConfig()
  },
})
</script>

<style scoped lang="scss">
.legacy-section {
  padding: 8px 0;
}
</style>
