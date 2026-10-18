<template>
  <el-dialog
    :model-value="modelValue"
    append-to-body
    title="导出权限包"
    :width="DIALOG_SM"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
      不勾选任何角色将导出全部权限配置；勾选后仅导出所选角色及其用户绑定。
    </el-alert>
    <div v-loading="rolesLoading" style="max-height: 320px; overflow: auto">
      <el-checkbox-group
        :model-value="selectedRoles"
        @update:model-value="emit('update:selectedRoles', $event.map(String))"
      >
        <el-checkbox v-for="r in roleOptions" :key="r.name" :value="r.name">
          {{ r.label || r.name }}
        </el-checkbox>
      </el-checkbox-group>
      <div v-if="!rolesLoading && roleOptions.length === 0" class="empty-hint">
        未检测到自定义 RBAC 角色，可直接导出基础配置。
      </div>
    </div>
    <el-divider style="margin: 12px 0" />
    <el-form label-width="110px">
      <el-form-item label="加密密码">
        <el-input
          :model-value="password"
          type="password"
          show-password
          placeholder="可选；设置后导入需输入该密码"
          clearable
          @update:model-value="emit('update:password', $event)"
        />
      </el-form-item>
      <el-form-item label="机器码绑定">
        <el-switch
          :model-value="bindMachineCode"
          @update:model-value="emit('update:bindMachineCode', $event === true)"
        />
        <span class="form-hint">开启后仅本机可导入该权限包</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="exporting" @click="emit('export')">导出</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'

/**
 * 导出权限包对话框（W5-T10 自 UserManagement.vue 拆出）。
 *
 * 勾选角色 / 加密密码 / 机器码绑定三个表单值与导出动作全部上抛：
 * 角色列表请求（/rbac/roles）、导出接口调用与下载仍归父组件，纯展示零逻辑。
 */
defineProps<{
  modelValue: boolean
  rolesLoading: boolean
  roleOptions: { name: string; label?: string }[]
  selectedRoles: string[]
  password: string
  bindMachineCode: boolean
  exporting: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', visible: boolean): void
  (e: 'update:selectedRoles', names: string[]): void
  (e: 'update:password', value: string): void
  (e: 'update:bindMachineCode', value: boolean): void
  (e: 'export'): void
}>()
</script>
