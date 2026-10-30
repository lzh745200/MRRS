<template>
  <el-dialog
    :model-value="modelValue"
    append-to-body
    :title="title"
    :width="DIALOG_MD"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="用户名" prop="username">
        <el-input
          :model-value="form.username"
          placeholder="请输入用户名"
          :disabled="isEdit"
          @update:model-value="emit('update:username', $event)"
        />
      </el-form-item>
      <el-form-item label="姓名" prop="full_name">
        <el-input
          :model-value="form.full_name"
          placeholder="请输入姓名"
          @update:model-value="emit('update:full_name', $event)"
        />
      </el-form-item>
      <el-form-item v-if="!isEdit" label="初始密码" prop="password">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-input
            :model-value="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
            style="flex: 1"
            @update:model-value="emit('update:password', $event)"
          />
          <el-button @click="emit('generate-password')">自动生成</el-button>
        </div>
      </el-form-item>
      <el-form-item label="角色" prop="role">
        <el-select
          :model-value="form.role"
          placeholder="请选择角色"
          style="width: 100%"
          teleported
          fit-input-width
          @update:model-value="emit('update:role', $event)"
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
          :model-value="form.data_scope"
          placeholder="请选择数据范围"
          style="width: 100%"
          teleported
          fit-input-width
          @update:model-value="emit('update:data_scope', $event)"
        >
          <el-option
            v-for="scope in dataScopeOptions"
            :key="scope.value"
            :label="scope.label"
            :value="scope.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="所属组织" prop="organization_id">
        <el-tree-select
          :model-value="form.organization_id"
          :data="orgTreeOptions"
          :props="treeSelectProps"
          node-key="id"
          placeholder="请选择所属组织"
          check-strictly
          clearable
          filterable
          style="width: 100%"
          teleported
          fit-input-width
          @update:model-value="emit('update:organization_id', $event)"
        />
      </el-form-item>
      <el-form-item v-if="!isEdit" label="功能权限">
        <el-select
          :model-value="form.permissions"
          multiple
          placeholder="请选择该用户的功能权限（不选则使用角色默认权限）"
          style="width: 100%"
          collapse-tags
          collapse-tags-tooltip
          teleported
          fit-input-width
          @update:model-value="emit('update:permissions', $event)"
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
        <div class="form-item-tip">选择该用户可以使用的具体功能权限，未选择则使用角色默认权限</div>
      </el-form-item>
      <el-form-item label="部门">
        <el-input
          :model-value="form.department"
          placeholder="请输入部门"
          @update:model-value="emit('update:department', $event)"
        />
      </el-form-item>
      <el-form-item label="手机号" prop="phone">
        <el-input
          :model-value="form.phone"
          placeholder="请输入手机号"
          @update:model-value="emit('update:phone', $event)"
        />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input
          :model-value="form.email"
          placeholder="请输入邮箱"
          @update:model-value="emit('update:email', $event)"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-switch
          :model-value="form.is_active"
          active-text="启用"
          inactive-text="禁用"
          @update:model-value="emit('update:is_active', $event as boolean)"
        />
      </el-form-item>
    </el-form>

    <!-- 活跃会话管理 (仅编辑模式) -->
    <div v-if="isEdit" class="session-section">
      <el-divider content-position="left">活跃会话</el-divider>
      <div v-loading="sessionsLoading">
        <el-table v-if="sessions.length > 0" :data="sessions" border>
          <el-table-column prop="session_id" label="会话ID" min-width="180" show-overflow-tooltip />
          <el-table-column prop="ip_address" label="IP 地址" width="140" />
          <el-table-column prop="user_agent" label="设备" min-width="160" show-overflow-tooltip />
          <el-table-column prop="created_at" label="登录时间" width="170">
            <template #default="{ row }">
              {{ formatDateTimeLocale(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column fixed="right" label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button
                type="danger"
                :loading="revokingSession === row.session_id"
                @click="emit('revoke-session', row)"
              >
                强制登出
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <EmptyState v-else-if="!sessionsLoading" text="无活跃会话" :size="40" />
      </div>
      <div class="session-actions">
        <el-button type="warning" :loading="resetting2fa" @click="emit('reset-2fa')">
          重置 2FA
        </el-button>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="emit('submit')">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 用户新增/编辑对话框（W5-T10 自 UserManagement.vue 拆出）。
 *
 * 拆分边界（父组件保留不可搬走的逻辑）：
 *  - 表单数据 `formData`、校验规则 `rules`（含「管理员必须有组织」跨字段规则，闭包引用
 *    父组件的 formData）与提交逻辑（POST/PUT /users、密码策略、列表刷新）全部留在父组件；
 *  - 本组件只承载模板 + `el-form` 实例，`defineExpose({ validate })` 把 Element Plus 的
 *    `validate(cb)` 转发给父组件 —— 父组件的 `handleSubmit` 因此与拆分前逐字一致；
 *  - 字段写入一律走 `update:<字段>` 事件，不直接改 props（`vue/no-mutating-props`，
 *    也让“谁改表单”在父组件一处可审计）。
 *
 * 会话区块：列表/加载态/按钮 loading 由 props 注入，强制登出与 2FA 重置上抛，
 * 接口调用与提示仍在父组件（`revokeSession` / `handleReset2fa`）。
 */
import { ref } from 'vue'
import type { FormInstance } from 'element-plus'
import { DIALOG_MD } from '@/config/dialog'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { formatDateTimeLocale } from '@/utils/datetime'
import { ORG_TREE_SELECT_PROPS } from '@/utils/treeNormalizer'

interface UserFormModel {
  username: string
  full_name: string
  password: string
  role: string
  data_scope: string
  department: string
  phone: string
  email: string
  is_active: boolean
  organization_id: number | string | null
  permissions: string[]
}

/** el-tree-select 的字段映射（与组织树常量同源，避免 value 键再次漏配） */
const treeSelectProps = ORG_TREE_SELECT_PROPS

defineProps<{
  modelValue: boolean
  title: string
  isEdit: boolean
  form: UserFormModel
  rules: Record<string, any>
  roleOptions: { value: string; label: string }[]
  dataScopeOptions: { value: string; label: string }[]
  orgTreeOptions: any[]
  permissionGroups: { category: string; items: { code: string; name: string }[] }[]
  submitting: boolean
  sessions: any[]
  sessionsLoading: boolean
  revokingSession: string | null
  resetting2fa: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', visible: boolean): void
  (e: 'update:username', value: string): void
  (e: 'update:full_name', value: string): void
  (e: 'update:password', value: string): void
  (e: 'update:role', value: string): void
  (e: 'update:data_scope', value: string): void
  (e: 'update:organization_id', value: number | string | null): void
  (e: 'update:permissions', value: string[]): void
  (e: 'update:department', value: string): void
  (e: 'update:phone', value: string): void
  (e: 'update:email', value: string): void
  (e: 'update:is_active', value: boolean): void
  (e: 'generate-password'): void
  (e: 'revoke-session', row: any): void
  (e: 'reset-2fa'): void
  (e: 'submit'): void
}>()

const formRef = ref<FormInstance>()

/**
 * 把 Element Plus 表单校验转发给父组件（父组件 `handleSubmit` 的唯一入口）。
 * 无分支实现：`el-form` 由本组件模板固定渲染，实例必然存在（与拆分前
 * `if (!formRef.value) return` 的“存在即通过”语义一致）。
 */
function validate(callback: (valid: boolean, invalidFields?: any) => void) {
  return (formRef.value as FormInstance).validate(callback)
}

defineExpose({ validate })
</script>

<style lang="scss" scoped>
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
