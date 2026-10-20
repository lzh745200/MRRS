<template>
  <el-dialog
    :model-value="modelValue"
    append-to-body
    title="登记报销"
    :width="DIALOG_SM"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form label-width="90px">
      <el-form-item label="金额(万元)" required>
        <el-input-number
          :model-value="form.amount"
          :min="0.0001"
          :precision="4"
          @update:model-value="emit('update:amount', $event)"
        />
      </el-form-item>
      <el-form-item label="日期" required>
        <el-date-picker
          :model-value="form.transaction_date"
          type="date"
          value-format="YYYY-MM-DD"
          @update:model-value="emit('update:transaction_date', $event)"
        />
      </el-form-item>
      <el-form-item label="用途" required>
        <el-input
          :model-value="form.purpose"
          type="textarea"
          :rows="2"
          maxlength="200"
          show-word-limit
          @update:model-value="emit('update:purpose', $event)"
        />
      </el-form-item>
      <el-form-item label="经办人"
        ><el-input :model-value="form.handler" @update:model-value="emit('update:handler', $event)"
      /></el-form-item>
      <el-form-item label="票据号"
        ><el-input
          :model-value="form.receipt_number"
          @update:model-value="emit('update:receipt_number', $event)"
      /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="emit('confirm')">提交</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 报销登记对话框（W5-T10 自 funds/Detail.vue 拆出）。
 *
 * 三必填校验、接口调用（POST /fund-budgets/transactions）、剩余可用额度刷新、
 * 成功后重载报销明细与详情仍全部在父组件 `submitExpense`；本组件只渲染字段并上抛改动。
 */
import { DIALOG_SM } from '@/config/dialog'

defineProps<{
  modelValue: boolean
  form: {
    amount: number | undefined
    transaction_date: string
    purpose: string
    handler: string
    receipt_number: string
  }
  submitting: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', visible: boolean): void
  (e: 'update:amount', value: number | undefined): void
  (e: 'update:transaction_date', value: string): void
  (e: 'update:purpose', value: string): void
  (e: 'update:handler', value: string): void
  (e: 'update:receipt_number', value: string): void
  (e: 'confirm'): void
}>()
</script>
