<template>
  <el-card class="table-card">
    <template #header>
      <div class="card-header">
        <div class="title-area">
          <span class="title">用户列表</span>
          <el-badge v-if="isAdmin && pendingCount > 0" :value="pendingCount" class="pending-badge">
            <el-button type="warning" @click="emit('open-pending')">待审核用户</el-button>
          </el-badge>
        </div>
        <div v-if="isAdmin" v-permission="['admin', 'super_admin']" class="header-actions">
          <el-button type="primary" @click="emit('add')">
            <el-icon><Plus /></el-icon>
            新增用户
          </el-button>
          <el-dropdown @command="onPermCommand">
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
        <el-button link type="primary" style="margin-left: 8px" @click="emit('clear-org-filter')">
          清除筛选
        </el-button>
      </template>
    </el-alert>

    <el-table v-loading="loading" :data="users" border>
      <el-table-column type="index" label="序号" width="60" align="center" />
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="full_name" label="姓名" min-width="100">
        <template #default="{ row }">
          {{ desensitize(row.full_name, 'name') }}
        </template>
      </el-table-column>
      <el-table-column prop="role" label="角色" width="130">
        <template #default="{ row }">
          <el-tag :type="roleTagType(row.role)">{{ roleName(row.role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="data_scope" label="数据范围" width="120">
        <template #default="{ row }">
          {{ dataScopeName(row.data_scope) }}
        </template>
      </el-table-column>
      <el-table-column label="权限包" width="130">
        <template #default="{ row }">
          <el-tag v-if="row.permission_pack_id" type="warning">
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
          {{ desensitize(row.phone, 'phone') }}
        </template>
      </el-table-column>
      <el-table-column prop="machine_code" label="机器码" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.machine_code" type="success">
            <el-icon><Key /></el-icon>
            已绑定
          </el-tag>
          <el-tag v-else type="info">未绑定</el-tag>
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
            <el-button text type="primary" @click="emit('edit', row)">编辑</el-button>
            <el-button text type="warning" @click="emit('reset-password', row)">重置密码</el-button>
            <el-button text type="success" @click="emit('role-permission', row)"
              >角色/权限</el-button
            >
            <el-button text type="danger" @click="emit('delete', row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      :current-page="page"
      :page-size="size"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      class="pagination"
      @update:current-page="emit('update:page', $event)"
      @update:page-size="emit('update:size', $event)"
      @size-change="emit('size-change')"
      @current-change="emit('page-change')"
    />
  </el-card>
</template>

<script setup lang="ts">
import { Plus, Key, ArrowDown } from '@element-plus/icons-vue'

/**
 * 用户列表卡片（W5-T10 自 UserManagement.vue 拆出）。
 *
 * 纯展示 + 事件上抛：数据、分页状态、角色/范围文案映射、脱敏函数都由父组件注入，
 * 本组件不持有任何业务状态、不发请求 —— 拆分前后 DOM 与交互完全一致。
 */
defineProps<{
  /** 表格数据 */
  users: any[]
  /** 表格 loading */
  loading: boolean
  /** 是否管理员（控制操作列与头部按钮） */
  isAdmin: boolean
  /** 待审核用户数（>0 且管理员时显示角标） */
  pendingCount: number
  /** 组织预筛选 id（非空时显示提示条） */
  orgFilterId: number | null
  /** 权限包 id → 名称映射 */
  packNameMap: Record<number, string>
  /** 当前页 / 每页条数 / 总数 */
  page: number
  size: number
  total: number
  /** 角色标签样式与文案映射（返回 el-tag 允许的 type 联合，未知角色由父组件兜底） */
  roleTagType: (role: string) => 'primary' | 'success' | 'warning' | 'info' | 'danger'
  roleName: (role: string) => string
  dataScopeName: (scope: string) => string
  /** 姓名/手机号脱敏展示（与 useDesensitize().ds 同源，由父组件注入） */
  desensitize: (
    value: string | number | null | undefined,
    type: 'phone' | 'idCard' | 'name' | 'bankCard' | 'email' | 'address' | 'amount' | 'militaryID'
  ) => string
}>()

const emit = defineEmits<{
  (e: 'update:page', page: number): void
  (e: 'update:size', size: number): void
  (e: 'size-change'): void
  (e: 'page-change'): void
  (e: 'add'): void
  (e: 'open-pending'): void
  (e: 'perm-command', command: string): void
  (e: 'clear-org-filter'): void
  (e: 'edit', row: any): void
  (e: 'reset-password', row: any): void
  (e: 'role-permission', row: any): void
  (e: 'delete', row: any): void
}>()

/** 权限包下拉命令上抛（export/import 的业务分支由父组件处理） */
function onPermCommand(command: string) {
  emit('perm-command', command)
}
</script>

<style lang="scss" scoped>
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
</style>
