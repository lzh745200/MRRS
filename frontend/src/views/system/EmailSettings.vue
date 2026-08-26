<template>
  <div class="email-settings-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">邮件设置</span>
        </div>
      </template>

      <el-descriptions title="SMTP 配置（只读）" :column="2" border>
        <el-descriptions-item label="SMTP 服务器">{{ config.smtpHost }}</el-descriptions-item>
        <el-descriptions-item label="端口">{{ config.smtpPort }}</el-descriptions-item>
        <el-descriptions-item label="发件人名称">{{ config.senderName }}</el-descriptions-item>
        <el-descriptions-item label="SSL">
          <el-tag :type="config.smtpSsl ? 'success' : 'info'">
            {{ config.smtpSsl ? '已启用' : '未启用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="配置状态">
          <el-tag :type="config.configured ? 'success' : 'warning'">
            {{ config.configured ? '已配置' : '未配置' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="!config.configured"
        type="info"
        title="邮件服务未配置"
        description="请在后端 .env 文件中设置 SMTP_HOST、SMTP_USER、SMTP_PASSWORD 等环境变量以启用邮件功能。"
        show-icon
        :closable="false"
        style="margin-top: 20px"
      />
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span class="title">邮件发送日志</span>
        </div>
      </template>
      <EmptyState text="邮件日志功能需配置SMTP后生效" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { reactive } from 'vue'

// 显示当前配置状态（只读）
const config = reactive({
  smtpHost: 'smtp.example.com',
  smtpPort: 465,
  senderName: '乡村振兴管理系统',
  smtpSsl: true,
  configured: false,
})
</script>

<style lang="scss" scoped>
.email-settings-page {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
</style>
