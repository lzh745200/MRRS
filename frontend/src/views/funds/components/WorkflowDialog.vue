<template>
  <el-dialog
    :model-value="modelValue"
    append-to-body
    :title="title"
    :width="DIALOG_SM"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form label-width="100px">
      <el-form-item v-if="action === 'allocate'" label="拨付金额(万元)"
        ><el-input-number
          :model-value="form.allocated_amount"
          :min="0"
          :precision="4"
          style="width: 100%"
          @update:model-value="emit('update:allocated_amount', $event)"
      /></el-form-item>
      <el-form-item v-if="action === 'allocate'" label="拨付方式"
        ><el-input
          :model-value="form.allocation_method"
          placeholder="如：银行转账"
          @update:model-value="emit('update:allocation_method', $event)"
      /></el-form-item>
      <el-form-item v-if="action === 'audit'" label="审计结果">
        <el-select
          :model-value="form.audit_result"
          placeholder="请选择审计结果"
          clearable
          style="width: 100%"
          @update:model-value="emit('update:audit_result', $event)"
        >
          <el-option label="通过" value="通过" /><el-option
            label="不通过"
            value="不通过"
          /><el-option label="有保留意见" value="有保留意见" />
        </el-select>
      </el-form-item>
      <el-form-item label="意见/备注"
        ><el-input
          :model-value="form.opinion"
          type="textarea"
          :rows="3"
          placeholder="请输入意见或备注"
          @update:model-value="emit('update:opinion', $event)"
      /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="emit('confirm')">确认</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 经费工作流操作对话框（W5-T10 自 funds/Detail.vue 拆出）。
 *
 * 六状态流转（审批/驳回/拨付/开始使用/完成使用/审计）共用本弹窗，
 * `action` 决定显示哪些字段。状态机本体、载荷组装（`submitWorkflow`）、
 * 成功后重载详情与四个日志 tab 全部留在父组件；本组件只做字段渲染与事件上抛。
 */
import { DIALOG_SM } from '@/config/dialog'

defineProps<{
  modelValue: boolean
  title: string
  action: string
  form: {
    opinion: string
    allocated_amount: number | undefined
    allocation_method: string
    audit_result: string
  }
  submitting: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', visible: boolean): void
  (e: 'update:opinion', value: string): void
  (e: 'update:allocated_amount', value: number | undefined): void
  (e: 'update:allocation_method', value: string): void
  (e: 'update:audit_result', value: string): void
  (e: 'confirm'): void
}>()
</script>
