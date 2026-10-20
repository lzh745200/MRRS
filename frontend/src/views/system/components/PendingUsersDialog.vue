<template>
  <el-dialog
    :model-value="modelValue"
    append-to-body
    title="待审核用户"
    :width="DIALOG_MD"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-table v-if="users.length > 0" :data="users" border>
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="full_name" label="姓名" min-width="100" />
      <el-table-column prop="role" label="角色" width="110" />
      <el-table-column prop="organization_name" label="所属组织" min-width="140" />
      <el-table-column label="状态" width="90">
        <template #default>
          <el-tag type="warning">待审核</el-tag>
        </template>
      </el-table-column>
      <el-table-column fixed="right" label="操作" width="110" align="center">
        <template #default="{ row }">
          <el-button text type="primary" @click="emit('approve', row)">通过审核</el-button>
        </template>
      </el-table-column>
    </el-table>
    <EmptyState v-else description="暂无待审核用户" />
  </el-dialog>
</template>

<script setup lang="ts">
import { DIALOG_MD } from '@/config/dialog'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'

/**
 * 待审核用户对话框（W5-T10 自 UserManagement.vue 拆出）。
 *
 * 列表与开关状态由父组件持有；审核动作上抛（接口调用与列表刷新仍归父组件）。
 * 2026-10-14 接通：此前按钮只拉数据、无弹窗消费，本组件即该弹窗的消费方。
 */
defineProps<{
  modelValue: boolean
  users: any[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', visible: boolean): void
  (e: 'approve', row: any): void
}>()
</script>
