<template>
  <el-dialog
    :model-value="modelValue"
    append-to-body
    title="重置密码"
    :width="DIALOG_SM"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="用户名">
        <el-input :value="username" disabled />
      </el-form-item>
      <el-form-item label="新密码">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-input
            :model-value="form.newPassword"
            type="password"
            placeholder="请输入新密码"
            show-password
            style="flex: 1"
            @update:model-value="emit('update:newPassword', $event)"
          />
          <el-button @click="emit('generate')">自动生成</el-button>
        </div>
      </el-form-item>
      <el-form-item v-if="form.newPassword" label="生成的密码">
        <el-input :value="form.newPassword" readonly>
          <template #append>
            <el-button @click="emit('copy')">复制</el-button>
          </template>
        </el-input>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="emit('confirm')">确认重置</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'

/**
 * 重置密码对话框（W5-T10 自 UserManagement.vue 拆出）。
 *
 * 表单对象/当前用户由父组件注入，自动生成、复制、确认重置三个动作上抛：
 * 密码策略校验、接口调用、剪贴板与弹窗提示仍归父组件，纯展示零逻辑。
 */
defineProps<{
  modelValue: boolean
  username?: string
  form: { newPassword: string }
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', visible: boolean): void
  (e: 'update:newPassword', value: string): void
  (e: 'generate'): void
  (e: 'copy'): void
  (e: 'confirm'): void
}>()
</script>
