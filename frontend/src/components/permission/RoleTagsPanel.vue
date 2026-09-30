<template>
  <div class="role-tags-panel">
    <el-alert type="info" :closable="false" style="margin-bottom: 16px">
      为用户分配 RBAC 角色。角色包含一组预定义的权限。 用户会继承所分配角色的所有权限。
    </el-alert>

    <!-- 当前已分配的角色 -->
    <div class="section">
      <h4>已分配角色</h4>
      <!-- 加载失败（403/网络/5xx）必须与"无角色"可区分：保留上一次已知值并显式告警，
           否则管理员会把"读不到"误判成"没有角色"，进而重复分配/漏撤销 -->
      <el-alert
        v-if="loadFailed"
        type="warning"
        :closable="false"
        show-icon
        class="load-failed-hint"
      >
        角色数据加载失败，当前显示可能不是最新状态，请稍后重试。
      </el-alert>
      <div v-else-if="assignedRoles.length === 0" class="empty-hint">暂未分配任何 RBAC 角色</div>
      <el-tag
        v-for="role in assignedRoles"
        :key="role.id"
        closable
        :type="role.is_system ? 'primary' : 'success'"
        size="large"
        style="margin: 4px"
        @close="removeRole(role)"
      >
        {{ role.name }}
        <el-tooltip v-if="role.description" :content="role.description" placement="top">
          <el-icon style="margin-left: 4px"><InfoFilled /></el-icon>
        </el-tooltip>
        <span v-if="role.is_system" style="margin-left: 4px; opacity: 0.7"> (系统) </span>
      </el-tag>
    </div>

    <el-divider />

    <!-- 可分配的角色 -->
    <div class="section">
      <h4>可选角色</h4>
      <div v-if="availableRoles.length === 0" class="empty-hint">暂无可分配的角色</div>
      <el-select
        v-model="selectedRoleId"
        placeholder="选择要分配的角色"
        filterable
        style="width: 320px"
        @change="assignRole"
      >
        <el-option
          v-for="role in availableRoles"
          :key="role.id"
          :label="`${role.name}${role.description ? ' - ' + role.description : ''}`"
          :value="role.id"
        />
      </el-select>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { get, post, apiRequest } from '@/api/request'
import { logger } from '@/utils/logger'

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
  userId: number
  allRoles?: RbacRole[]
}>()

const emit = defineEmits<{
  assigned: []
  removed: []
}>()

const assignedRoles = ref<RbacRole[]>([])
const selectedRoleId = ref('')
/** 已分配角色加载失败标记（用于把失败与"无角色"区分开） */
const loadFailed = ref(false)

const availableRoles = computed(() => {
  if (!props.allRoles) return []
  const assignedIds = new Set(assignedRoles.value.map((r) => r.id))
  return props.allRoles.filter((r) => r.is_active !== false && !assignedIds.has(r.id))
})

async function loadAssignedRoles() {
  try {
    const res: any = await get(`/rbac/user/${props.userId}/roles`)
    const data = res?.data ?? res
    // 载荷必须是数组：非数组（对象/字符串/0）会在模板 .map 处渲染期抛错
    if (!Array.isArray(data)) {
      throw new Error('角色列表载荷格式不正确')
    }
    assignedRoles.value = data as RbacRole[]
    loadFailed.value = false
  } catch (err) {
    // 绝不静默清空：403/网络/5xx 与"无角色"必须可区分（保留旧值 + 显式告警）
    loadFailed.value = true
    logger.error('[RoleTagsPanel] 已分配角色加载失败:', err)
  }
}

async function assignRole(roleId: string) {
  if (!roleId) return
  try {
    await post('/rbac/assign/role', {
      user_id: props.userId,
      role_id: roleId,
    })
    selectedRoleId.value = ''
    await loadAssignedRoles()
    emit('assigned')
    ElMessage.success('角色分配成功')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '角色分配失败')
  }
}

async function removeRole(role: RbacRole) {
  // 撤销角色是不可逆的授权变更，必须先二次确认；系统角色额外提示影响面
  try {
    await ElMessageBox.confirm(
      role.is_system
        ? `「${role.name}」是系统角色，撤销可能影响该用户既有权限。确认移除？`
        : `确认移除角色「${role.name}」？`,
      '移除角色',
      { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' }
    )
  } catch {
    return // 用户取消（ElMessageBox 以 reject 表达取消）
  }
  try {
    await apiRequest({
      method: 'DELETE',
      url: '/rbac/revoke/role',
      data: { user_id: props.userId, role_id: role.id },
    })
    await loadAssignedRoles()
    emit('removed')
    ElMessage.success(`角色「${role.name}」已移除`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '角色移除失败')
  }
}

// 暴露加载方法供父组件调用
defineExpose({ loadAssignedRoles, assignedRoles })
</script>

<style scoped lang="scss">
.role-tags-panel {
  .section h4 {
    margin: 0 0 8px 0;
  }
  .empty-hint {
    color: var(--el-text-color-placeholder);
    font-size: 13px;
  }
}
</style>
