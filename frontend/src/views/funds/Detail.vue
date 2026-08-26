<template>
  <div class="fund-detail-page">
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="goBack">返回列表</el-button>
        <h2 class="page-title">
          {{ isCreate ? '新增经费记录' : isEdit ? '编辑经费记录' : '经费详情' }}
        </h2>
      </div>
      <div v-if="!isEdit && !isCreate && canEditFund" class="header-actions">
        <el-button type="primary" @click="handleEdit"
          ><el-icon><Edit /></el-icon>编辑</el-button
        >
        <el-button
          v-if="canOperate && fundData.status === 'pending'"
          type="danger"
          @click="handleDelete"
          ><el-icon><Delete /></el-icon>删除</el-button
        >
      </div>
    </div>
    <div v-if="loading" class="loading-container">
      <el-icon class="loading-icon"><Loading /></el-icon><span>加载中...</span>
    </div>
    <template v-else>
      <!-- 查看模式 -->
      <template v-if="!isEdit">
        <!-- 工作流操作栏 -->
        <div v-if="canOperate && fundData.id" class="workflow-bar">
          <div class="workflow-status">
            当前状态：<el-tag :type="getStatusType(fundData.status)" size="large">{{
              getStatusText(fundData.status)
            }}</el-tag>
          </div>
          <div class="workflow-actions">
            <el-button
              v-if="fundData.status === 'pending'"
              type="success"
              @click="doWorkflow('approve')"
              >审批通过</el-button
            >
            <el-button
              v-if="fundData.status === 'pending'"
              type="danger"
              @click="doWorkflow('reject')"
              >驳回</el-button
            >
            <el-button
              v-if="fundData.status === 'approved'"
              type="primary"
              @click="doWorkflow('allocate')"
              >拨付</el-button
            >
            <el-button
              v-if="fundData.status === 'allocated'"
              type="warning"
              @click="doWorkflow('start_use')"
              >开始使用</el-button
            >
            <el-button
              v-if="fundData.status === 'in_use'"
              type="success"
              @click="doWorkflow('complete')"
              >完成使用</el-button
            >
            <el-button
              v-if="fundData.status === 'completed'"
              type="primary"
              @click="doWorkflow('audit')"
              >审计</el-button
            >
          </div>
        </div>

        <!-- 标签页 -->
        <el-tabs v-model="activeTab" type="border-card">
          <!-- 基本信息标签页 -->
          <el-tab-pane label="基本信息" name="basic">
            <div class="detail-card" style="margin-bottom: 0">
              <div class="card-header"><h3>基本信息</h3></div>
              <div class="card-body">
                <el-descriptions :column="3" border>
                  <el-descriptions-item label="经费编号">{{
                    fundData.code || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="名称">{{
                    fundData.name || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="经费类型"
                    ><el-tag>{{ getTypeName(fundData.type) }}</el-tag></el-descriptions-item
                  >
                  <el-descriptions-item label="经费来源">{{
                    getSourceName(fundData.fund_source || fundData.source)
                  }}</el-descriptions-item>
                  <el-descriptions-item label="关联项目">{{
                    fundData.project_name || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="日期">{{
                    fundData.date || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="申请人">{{
                    ds(fundData.applicant, 'name') || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="经办人">{{
                    ds(fundData.operator, 'name') || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="接收人">{{
                    ds(fundData.receiver, 'name') || '-'
                  }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </div>
            <div class="detail-card" style="margin-bottom: 0; margin-top: 20px">
              <div class="card-header"><h3>经费信息</h3></div>
              <div class="card-body">
                <el-descriptions :column="3" border>
                  <el-descriptions-item label="申请金额"
                    ><span class="amount-text"
                      >{{ formatMoney(fundData.amount) }} 万元</span
                    ></el-descriptions-item
                  >
                  <el-descriptions-item label="计划金额"
                    ><span class="amount-text"
                      >{{ formatMoney(fundData.planned_amount) }} 万元</span
                    ></el-descriptions-item
                  >
                  <el-descriptions-item label="批准金额"
                    ><span class="amount-text"
                      >{{ formatMoney(fundData.approved_amount) }} 万元</span
                    ></el-descriptions-item
                  >
                  <el-descriptions-item label="拨付金额"
                    ><span class="amount-text"
                      >{{ formatMoney(fundData.allocated_amount) }} 万元</span
                    ></el-descriptions-item
                  >
                  <el-descriptions-item label="已使用金额"
                    ><span class="amount-text"
                      >{{ formatMoney(fundData.used_amount) }} 万元</span
                    ></el-descriptions-item
                  >
                  <el-descriptions-item label="剩余金额"
                    ><span class="amount-text"
                      >{{ formatMoney(fundData.remaining_amount) }} 万元</span
                    ></el-descriptions-item
                  >
                  <el-descriptions-item label="用途" :span="3">{{
                    fundData.purpose || '无'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="使用说明" :span="3">{{
                    fundData.usage_description || '无'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="备注" :span="3">{{
                    fundData.remarks || '无'
                  }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </div>
          </el-tab-pane>

          <!-- 审批流程标签页 -->
          <el-tab-pane label="审批流程" name="approval">
            <div class="detail-card" style="margin-bottom: 0">
              <div class="card-header"><h3>审批信息</h3></div>
              <div class="card-body">
                <el-steps
                  v-if="approvalFlow.nodes.length"
                  :active="approvalActiveStep"
                  finish-status="success"
                  align-center
                >
                  <el-step
                    v-for="node in approvalFlow.nodes"
                    :key="node.status"
                    :title="node.label"
                    :description="node.description"
                    :status="node.current ? 'process' : node.reached ? 'success' : 'wait'"
                  />
                </el-steps>
                <el-descriptions :column="3" border style="margin-top: 16px">
                  <el-descriptions-item label="审批人">{{
                    approvalFlow.currentApprover || fundData.approved_by || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="审批日期">{{
                    formatDateTime(fundData.approval_date)
                  }}</el-descriptions-item>
                  <el-descriptions-item label="拨付日期">{{
                    formatDateTime(fundData.allocation_date)
                  }}</el-descriptions-item>
                  <el-descriptions-item label="拨付方式">{{
                    fundData.allocation_method || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="开始日期">{{
                    formatDateTime(fundData.start_date)
                  }}</el-descriptions-item>
                  <el-descriptions-item label="结束日期">{{
                    formatDateTime(fundData.end_date)
                  }}</el-descriptions-item>
                  <el-descriptions-item label="审计日期">{{
                    formatDateTime(fundData.audit_date)
                  }}</el-descriptions-item>
                  <el-descriptions-item label="审计结果">{{
                    fundData.audit_result || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="审计意见">{{
                    fundData.audit_opinion || '-'
                  }}</el-descriptions-item>
                  <el-descriptions-item label="创建时间">{{
                    formatDateTime(fundData.created_at)
                  }}</el-descriptions-item>
                  <el-descriptions-item label="更新时间" :span="2">{{
                    formatDateTime(fundData.updated_at)
                  }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </div>
          </el-tab-pane>

          <!-- 状态日志标签页 -->
          <el-tab-pane label="状态日志" name="statusHistory">
            <div class="detail-card" style="margin-bottom: 0">
              <div class="card-header"><h3>状态变更历史</h3></div>
              <div class="card-body">
                <el-timeline v-if="statusHistory.length">
                  <el-timeline-item
                    v-for="item in statusHistory"
                    :key="item.id"
                    :type="getStatusType(item.to_status)"
                    :timestamp="formatDateTime(item.operation_time)"
                  >
                    <div class="timeline-content">
                      <div class="timeline-title">
                        <el-tag :type="getStatusType(item.from_status)" size="small">{{
                          getStatusText(item.from_status)
                        }}</el-tag>
                        <span style="margin: 0 8px">→</span>
                        <el-tag :type="getStatusType(item.to_status)" size="small">{{
                          getStatusText(item.to_status)
                        }}</el-tag>
                      </div>
                      <div class="timeline-info">
                        操作人: {{ ds(item.operator_name, 'name') || '-' }}
                        <span v-if="item.remark" style="margin-left: 16px"
                          >备注: {{ item.remark }}</span
                        >
                      </div>
                    </div>
                  </el-timeline-item>
                </el-timeline>
                <div v-else style="font-size: 13px; color: #999">暂无状态变更记录</div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 字段变更标签页 -->
          <el-tab-pane label="修改记录" name="fieldChanges">
            <div class="detail-card" style="margin-bottom: 0">
              <div class="card-header"><h3>字段修改历史</h3></div>
              <div class="card-body">
                <el-table v-if="fieldChanges.length" :data="fieldChanges" stripe>
                  <el-table-column prop="field_name" label="字段" width="120" />
                  <el-table-column prop="old_value" label="旧值" show-overflow-tooltip>
                    <template #default="{ row }">
                      <span class="text-muted">{{ row.old_value || '-' }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="new_value" label="新值" show-overflow-tooltip>
                    <template #default="{ row }">
                      <span class="text-primary">{{ row.new_value || '-' }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="changed_by_name" label="修改人" width="120" />
                  <el-table-column prop="changed_at" label="修改时间" width="180">
                    <template #default="{ row }">
                      {{ formatDateTime(row.changed_at) }}
                    </template>
                  </el-table-column>
                </el-table>
                <div v-else style="font-size: 13px; color: #999">暂无字段修改记录</div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 操作日志标签页 -->
          <el-tab-pane label="操作日志" name="operationLogs">
            <div class="detail-card" style="margin-bottom: 0">
              <div class="card-header"><h3>操作日志</h3></div>
              <div class="card-body">
                <el-table v-if="operationLogs.length" :data="operationLogs" stripe>
                  <el-table-column prop="operation_type" label="操作类型" width="150">
                    <template #default="{ row }">
                      <el-tag size="small">{{ getOperationTypeLabel(row.operation_type) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="operation_detail" label="详情" show-overflow-tooltip>
                    <template #default="{ row }">
                      {{ formatOperationDetail(row.operation_detail) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="operator_name" label="操作人" width="120" />
                  <el-table-column prop="created_at" label="操作时间" width="180">
                    <template #default="{ row }">
                      {{ formatDateTime(row.created_at) }}
                    </template>
                  </el-table-column>
                </el-table>
                <div v-else style="font-size: 13px; color: #999">暂无操作日志</div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 附件管理标签页 -->
          <el-tab-pane label="附件管理" name="attachments">
            <div class="detail-card" style="margin-bottom: 0">
              <div class="card-header">
                <h3>相关附件</h3>
              </div>
              <div class="card-body">
                <el-upload
                  :show-file-list="false"
                  :before-upload="handleBeforeUpload"
                  :http-request="handleUploadAttachment"
                  multiple
                >
                  <el-button type="primary" :loading="uploadingAttachment">
                    <el-icon><Upload /></el-icon>上传附件
                  </el-button>
                  <span style="margin-left: 12px; font-size: 12px; color: #999">
                    支持格式：pdf、doc、docx、xls、xlsx、jpg、png、gif、bmp、txt、zip、rar
                  </span>
                </el-upload>

                <el-table
                  v-if="attachments.length"
                  :data="attachments"
                  stripe
                  style="margin-top: 16px"
                >
                  <el-table-column
                    prop="file_name"
                    label="文件名"
                    min-width="200"
                    show-overflow-tooltip
                  />
                  <el-table-column prop="category" label="分类" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag size="small">{{ getCategoryLabel(row.category) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="file_size" label="大小" width="100">
                    <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
                  </el-table-column>
                  <el-table-column prop="uploaded_by" label="上传人" width="100" />
                  <el-table-column prop="created_at" label="上传时间" width="160">
                    <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                  </el-table-column>
                  <el-table-column label="操作" width="180" fixed="right">
                    <template #default="{ row }">
                      <el-button link type="primary" @click="previewAttachment(row)"
                        >预览</el-button
                      >
                      <el-button link type="primary" @click="downloadAttachment(row)"
                        >下载</el-button
                      >
                      <el-popconfirm title="确定删除该附件吗？" @confirm="deleteAttachment(row)">
                        <template #reference>
                          <el-button link type="danger">删除</el-button>
                        </template>
                      </el-popconfirm>
                    </template>
                  </el-table-column>
                </el-table>
                <EmptyState v-else text="暂无附件" />
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="报销核销" name="expenses">
            <div class="expense-toolbar">
              <span class="remain-hint">
                剩余可用：<b>{{
                  formatMoney(
                    fundData.remaining_amount ??
                      Number(fundData.amount || 0) - Number(fundData.used_amount || 0)
                  )
                }}</b>
                万元
              </span>
              <el-button
                type="primary"
                size="small"
                :disabled="!['allocated', 'in_use', 'completed'].includes(fundData.status)"
                @click="expDialogVisible = true"
                >登记报销</el-button
              >
            </div>
            <el-table :data="expenses" size="small" border stripe>
              <el-table-column prop="transaction_date" label="日期" width="110" />
              <el-table-column prop="amount" label="金额(万元)" width="120" align="right" />
              <el-table-column prop="purpose" label="用途" min-width="180" show-overflow-tooltip />
              <el-table-column prop="handler" label="经办人" width="100" />
              <el-table-column prop="receipt_number" label="票据号" width="120" />
            </el-table>
            <EmptyState v-if="!expenses.length && !loadingExpenses" text="暂无报销记录" />
          </el-tab-pane>
        </el-tabs>
      </template>

      <!-- 编辑/创建模式 -->
      <template v-else>
        <div class="detail-card">
          <div class="card-header">
            <h3>{{ isCreate ? '填写经费信息' : '编辑经费信息' }}</h3>
          </div>
          <div class="card-body">
            <el-form ref="formRef" :model="formData" :rules="rules" label-width="120px">
              <el-row :gutter="24">
                <el-col :span="12"
                  ><el-form-item label="经费编号"
                    ><el-input v-model="formData.code" placeholder="选填" /></el-form-item
                ></el-col>
                <el-col :span="12"
                  ><el-form-item label="名称" prop="name"
                    ><el-input v-model="formData.name" placeholder="请输入经费名称" /></el-form-item
                ></el-col>
              </el-row>
              <el-row :gutter="24">
                <el-col :span="12">
                  <el-form-item label="经费类型" prop="type">
                    <el-select v-model="formData.type" placeholder="请选择类型" style="width: 100%">
                      <el-option label="项目经费" value="project" /><el-option
                        label="运营经费"
                        value="operation"
                      />
                      <el-option label="教育帮扶" value="education" /><el-option
                        label="基础设施"
                        value="infrastructure"
                      />
                      <el-option label="应急经费" value="emergency" /><el-option
                        label="其他"
                        value="other"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="经费来源">
                    <el-select
                      v-model="formData.fund_source"
                      placeholder="请选择来源"
                      clearable
                      style="width: 100%"
                    >
                      <el-option label="专项" value="military" /><el-option
                        label="政府"
                        value="government"
                      />
                      <el-option label="捐赠" value="donation" /><el-option
                        label="企业"
                        value="enterprise"
                      />
                      <el-option label="其他" value="other" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="24">
                <el-col :span="12"
                  ><el-form-item label="日期"
                    ><el-date-picker
                      v-model="formData.date"
                      type="date"
                      placeholder="选择日期"
                      value-format="YYYY-MM-DD"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col :span="12">
                  <el-form-item label="状态">
                    <el-select
                      v-model="formData.status"
                      placeholder="请选择状态"
                      clearable
                      style="width: 100%"
                    >
                      <el-option label="待审批" value="pending" /><el-option
                        label="已计划"
                        value="planned"
                      />
                      <el-option label="已批准" value="approved" /><el-option
                        label="已拨付"
                        value="allocated"
                      />
                      <el-option label="使用中" value="in_use" /><el-option
                        label="已完成"
                        value="completed"
                      />
                      <el-option label="已审计" value="audited" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="24">
                <el-col :span="8"
                  ><el-form-item label="金额(万元)" prop="amount"
                    ><el-input-number
                      v-model="formData.amount"
                      :min="0"
                      :precision="4"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col :span="8"
                  ><el-form-item label="计划金额"
                    ><el-input-number
                      v-model="formData.planned_amount"
                      :min="0"
                      :precision="4"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col :span="8"
                  ><el-form-item label="批准金额"
                    ><el-input-number
                      v-model="formData.approved_amount"
                      :min="0"
                      :precision="4"
                      style="width: 100%" /></el-form-item
                ></el-col>
              </el-row>
              <el-row :gutter="24">
                <el-col :span="8"
                  ><el-form-item label="拨付金额"
                    ><el-input-number
                      v-model="formData.allocated_amount"
                      :min="0"
                      :precision="4"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col :span="8"
                  ><el-form-item label="已用金额"
                    ><el-input-number
                      v-model="formData.used_amount"
                      :min="0"
                      :precision="4"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col :span="8"
                  ><el-form-item label="剩余金额"
                    ><el-input-number
                      v-model="formData.remaining_amount"
                      :min="0"
                      :precision="4"
                      style="width: 100%" /></el-form-item
                ></el-col>
              </el-row>
              <el-row :gutter="24">
                <el-col :span="12"
                  ><el-form-item label="关联项目"
                    ><el-input
                      v-model="formData.project_name"
                      placeholder="请输入关联项目名称" /></el-form-item
                ></el-col>
                <el-col :span="12"
                  ><el-form-item label="经办人"
                    ><el-input
                      v-model="formData.operator"
                      placeholder="请输入经办人" /></el-form-item
                ></el-col>
              </el-row>
              <el-row :gutter="24">
                <el-col :span="12"
                  ><el-form-item label="接收人"
                    ><el-input
                      v-model="formData.receiver"
                      placeholder="请输入接收人/单位" /></el-form-item
                ></el-col>
                <el-col :span="12"
                  ><el-form-item label="起止日期"
                    ><el-date-picker
                      v-model="formData.dateRange"
                      type="daterange"
                      range-separator="至"
                      start-placeholder="开始"
                      end-placeholder="结束"
                      value-format="YYYY-MM-DD"
                      style="width: 100%" /></el-form-item
                ></el-col>
              </el-row>
              <el-form-item label="用途"
                ><el-input
                  v-model="formData.purpose"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入经费用途"
              /></el-form-item>
              <el-form-item label="使用说明"
                ><el-input
                  v-model="formData.usage_description"
                  type="textarea"
                  :rows="2"
                  placeholder="请输入使用说明"
              /></el-form-item>
              <el-form-item label="备注"
                ><el-input
                  v-model="formData.remarks"
                  type="textarea"
                  :rows="2"
                  placeholder="请输入备注信息"
              /></el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="submitting" @click="handleSubmit">{{
                  isCreate ? '创建' : '保存'
                }}</el-button>
                <el-button @click="isCreate ? goBack() : cancelEdit()">取消</el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </template>

      <!-- 附件预览对话框 -->
      <el-dialog
        v-model="previewVisible"
        :title="previewTitle"
        width="80%"
        top="5vh"
        destroy-on-close
        @close="handlePreviewClose"
      >
        <iframe
          v-if="previewUrl"
          :src="previewUrl"
          style="width: 100%; height: 70vh; border: none"
        />
      </el-dialog>
    </template>
    <!-- 工作流操作对话框 -->
    <el-dialog
      v-model="wfDialogVisible"
      :title="wfDialogTitle"
      :width="DIALOG_SM"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px">
        <el-form-item v-if="wfAction === 'allocate'" label="拨付金额(万元)"
          ><el-input-number
            v-model="wfForm.allocated_amount"
            :min="0"
            :precision="4"
            style="width: 100%"
        /></el-form-item>
        <el-form-item v-if="wfAction === 'allocate'" label="拨付方式"
          ><el-input v-model="wfForm.allocation_method" placeholder="如：银行转账"
        /></el-form-item>
        <el-form-item v-if="wfAction === 'audit'" label="审计结果">
          <el-select
            v-model="wfForm.audit_result"
            placeholder="请选择审计结果"
            clearable
            style="width: 100%"
          >
            <el-option label="通过" value="通过" /><el-option
              label="不通过"
              value="不通过"
            /><el-option label="有保留意见" value="有保留意见" />
          </el-select>
        </el-form-item>
        <el-form-item label="意见/备注"
          ><el-input
            v-model="wfForm.opinion"
            type="textarea"
            :rows="3"
            placeholder="请输入意见或备注"
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="wfDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="wfSubmitting" @click="submitWorkflow">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="expDialogVisible" title="登记报销" :width="DIALOG_SM">
      <el-form label-width="90px">
        <el-form-item label="金额(万元)" required>
          <el-input-number
            v-model="expForm.amount"
            :min="0.0001"
            :precision="4"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="日期" required>
          <el-date-picker
            v-model="expForm.transaction_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="用途" required>
          <el-input
            v-model="expForm.purpose"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="经办人"
          ><el-input v-model="expForm.handler" style="width: 200px"
        /></el-form-item>
        <el-form-item label="票据号"
          ><el-input v-model="expForm.receipt_number" style="width: 200px"
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="expDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="expSubmitting" @click="submitExpense">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { logger } from '@/utils/logger'
import { useAuthStore } from '@/stores/auth'

import { ref, reactive, computed, onMounted, onUnmounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useDesensitize } from '@/composables/useDesensitize'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { ArrowLeft, Edit, Delete, Loading, Upload } from '@element-plus/icons-vue'
import { get, post, put, del, apiRequest } from '@/api/request'
import { fundApi } from '@/api/funds'

const { pushSafe } = useRouterSafe()
const { ds } = useDesensitize()
const route = useRoute()
const authStore = useAuthStore()
const loading = ref(true)
const submitting = ref(false)
const isEdit = ref(false)
const isCreate = ref(false)
const formRef = ref()

const isManager = computed(() => {
  const role = authStore.user?.role || ''
  // manager/approval_leader 历史角色已归一化为 admin
  return ['admin', 'super_admin'].includes(role)
})

// 经费操作权限：与后端 require_funds_operator_role 对齐——viewer 只读，user 及以上可操作
const canOperate = computed(() => {
  const role = authStore.user?.role || ''
  return role !== '' && role !== 'viewer'
})

// 判断当前用户是否可以编辑此经费
const canEditFund = computed(() => {
  if (!canOperate.value) return false
  if (isManager.value) return true
  // 普通用户：只能编辑自己创建的待审批/已驳回状态经费
  const editableStatuses = ['pending', 'rejected']
  return fundData.created_by === authStore.user?.id && editableStatuses.includes(fundData.status)
})

// 历史记录数据
const activeTab = ref('basic')
const statusHistory = ref<any[]>([])
const fieldChanges = ref<any[]>([])
const operationLogs = ref<any[]>([])
const attachments = ref<any[]>([])
const uploadingAttachment = ref(false)
const previewVisible = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')

// 审批流程当前步骤索引（el-steps active 语义：已完成步骤数）
const approvalActiveStep = computed(() => {
  const nodes = approvalFlow.value.nodes
  if (!nodes.length) return 0
  const idx = nodes.findIndex((n: any) => n.current)
  return idx >= 0 ? idx + 1 : nodes.filter((n: any) => n.reached).length
})

// 加载历史记录
async function loadStatusHistory() {
  if (!fundData.id) return
  try {
    const res: any = await get(`/funds/${fundData.id}/history/status`)
    // 后端返回 success_response(data=[...]) 数组形态（非 ok_list），兼容两种
    const data = Array.isArray(res) ? res : res?.data
    statusHistory.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    logger.error('加载状态历史失败', error)
  }
}

async function loadFieldChanges() {
  if (!fundData.id) return
  try {
    const res: any = await get(`/funds/${fundData.id}/history/fields`)
    const data = Array.isArray(res) ? res : res?.data
    fieldChanges.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    logger.error('加载字段变更历史失败', error)
  }
}

async function loadOperationLogs() {
  if (!fundData.id) return
  try {
    const res: any = await get(`/funds/${fundData.id}/history/operations`)
    const data = Array.isArray(res) ? res : res?.data
    operationLogs.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    logger.error('加载操作日志失败', error)
  }
}

// 审批流程（当前节点 + 状态机节点）
const approvalFlow = ref<{ currentStatus: string; currentApprover: string; nodes: any[] }>({
  currentStatus: '',
  currentApprover: '',
  nodes: [],
})

async function loadApprovalFlow() {
  if (!fundData.id) return
  try {
    const res: any = await get(`/funds/${fundData.id}/approval-flow`)
    const data = res?.data || res || {}
    approvalFlow.value = {
      currentStatus: data.current_status || data.currentStatus || '',
      currentApprover: data.current_approver || data.currentApprover || '',
      nodes: Array.isArray(data.nodes) ? data.nodes : [],
    }
  } catch (error) {
    logger.error('加载审批流程失败', error)
  }
}

// 加载所有历史记录（并行执行）
async function loadAllHistory() {
  await Promise.all([
    loadStatusHistory(),
    loadFieldChanges(),
    loadOperationLogs(),
    loadApprovalFlow(),
    loadAttachments(),
  ])
}

async function loadAttachments() {
  if (!fundData.id) return
  try {
    const res = await fundApi.listAttachments(fundData.id)
    attachments.value = res.items || []
  } catch (error) {
    logger.error('加载附件失败', error)
  }
}

function handleBeforeUpload(_file: File) {
  return true
}

async function handleUploadAttachment(options: any) {
  if (!fundData.id) return
  uploadingAttachment.value = true
  try {
    const formData = new FormData()
    formData.append('file', options.file)
    formData.append('category', 'other')
    await post(`/funds/${fundData.id}/attachments`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success('上传成功')
    await loadAttachments()
    // 后端会落 attachment_upload 操作日志，同步重载操作日志 tab
    await loadOperationLogs()
  } catch {
    ElMessage.error('上传失败')
  } finally {
    uploadingAttachment.value = false
  }
}

function previewAttachment(row: any) {
  // 使用认证请求获取 Blob，避免 Electron window.open 发送到外部浏览器（无 token）
  fundApi
    .getAttachmentBlob(row.id)
    .then((blob) => {
      const url = window.URL.createObjectURL(blob)
      previewUrl.value = url
      previewTitle.value = row.file_name || '附件预览'
      previewVisible.value = true
    })
    .catch(() => {
      ElMessage.error('预览加载失败')
    })
}

function handlePreviewClose() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

function downloadAttachment(row: any) {
  // 使用认证请求下载，兼容 Electron（window.open 会被拦截到外部浏览器）
  fundApi.downloadAttachment(row.id, row.file_name).catch(() => {
    ElMessage.error('下载失败')
  })
}

async function deleteAttachment(row: any) {
  try {
    await fundApi.deleteAttachment(row.id)
    // 成功静默：删除成功仅刷新
    await loadAttachments()
    // 后端会落 attachment_delete 操作日志，同步重载操作日志 tab
    await loadOperationLogs()
  } catch {
    ElMessage.error('删除失败')
  }
}

function getCategoryLabel(cat: string) {
  const labels: Record<string, string> = {
    contract: '合同',
    invoice: '发票',
    receipt: '收据',
    report: '报告',
    allocation_order: '分配令',
    other: '其他',
  }
  return labels[cat] || cat || '其他'
}

function formatFileSize(bytes: number) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const fundData = reactive<any>({
  id: null,
  name: '',
  date: null,
  type: '',
  code: '',
  fund_type: '',
  fund_source: '',
  amount: 0,
  planned_amount: 0,
  approved_amount: null,
  allocated_amount: 0,
  used_amount: 0,
  remaining_amount: 0,
  project_id: '',
  project_name: '',
  village_id: null,
  school_id: null,
  purpose: '',
  source: '',
  operator: '',
  applicant: '',
  application_date: null,
  approved_by: '',
  approval_date: null,
  allocation_date: null,
  allocation_method: '',
  receiver: '',
  usage_description: '',
  start_date: null,
  end_date: null,
  audit_date: null,
  audit_result: '',
  audit_opinion: '',
  status: 'pending',
  remarks: '',
  created_at: '',
  updated_at: '',
})

const formData = reactive({
  code: '',
  name: '',
  date: null as string | null,
  type: 'project',
  fund_source: '',
  amount: 0,
  planned_amount: 0,
  approved_amount: null as number | null,
  allocated_amount: 0,
  used_amount: 0,
  remaining_amount: 0,
  project_name: '',
  village_id: null as number | null,
  purpose: '',
  source: '',
  operator: '',
  receiver: '',
  usage_description: '',
  status: 'pending',
  remarks: '',
  dateRange: null as string[] | null,
})

const rules = {
  name: [{ required: true, message: '请输入经费名称', trigger: 'blur' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }],
}

const getTypeName = (t: string) =>
  ({
    project: '项目经费',
    operation: '运营经费',
    education: '教育帮扶',
    infrastructure: '基础设施',
    emergency: '应急经费',
    other: '其他',
  })[t] ||
  t ||
  '-'
const getSourceName = (s: string) =>
  ({
    military: '专项',
    government: '政府',
    donation: '捐赠',
    enterprise: '企业',
    other: '其他',
  })[s] ||
  s ||
  '-'
const getStatusType = (s: string): any =>
  ({
    pending: 'warning',
    planned: 'info',
    approved: 'primary',
    allocated: 'info',
    in_use: 'primary',
    completed: 'success',
    audited: 'success',
    rejected: 'danger',
  })[s] || 'info'
const getStatusText = (s: string) =>
  ({
    pending: '待审批',
    planned: '已计划',
    approved: '已批准',
    allocated: '已拨付',
    in_use: '使用中',
    completed: '已完成',
    audited: '已审计',
    rejected: '已驳回',
  })[s] ||
  s ||
  '-'
const formatMoney = (v: any) =>
  v == null
    ? '0'
    : Number(v).toLocaleString('zh-CN', {
        maximumFractionDigits: 4,
      })
const formatDateTime = (d?: string | null) => {
  if (!d) return '-'
  try {
    return String(d).split('T')[0]
  } catch {
    return String(d)
  }
}

// 操作日志辅助函数
const getOperationTypeLabel = (type: string): string => {
  const labels: Record<string, string> = {
    attachment_upload: '附件上传',
    attachment_delete: '附件删除',
    status_change: '状态变更',
    field_update: '字段更新',
    create: '创建',
    delete: '删除',
  }
  return labels[type] || type
}

const formatOperationDetail = (detail: string | object): string => {
  if (!detail) return '-'
  try {
    const obj = typeof detail === 'string' ? JSON.parse(detail) : detail
    return typeof obj === 'object' ? JSON.stringify(obj) : String(detail)
  } catch {
    return String(detail)
  }
}

// 工作流
const wfDialogVisible = ref(false)
const wfDialogTitle = ref('')
const wfAction = ref('')
const wfSubmitting = ref(false)
const wfForm = reactive({
  opinion: '',
  allocated_amount: 0,
  allocation_method: '',
  audit_result: '通过',
})
const wfLabels: Record<string, string> = {
  approve: '审批通过',
  reject: '驳回',
  allocate: '拨付',
  start_use: '开始使用',
  complete: '完成使用',
  audit: '审计',
}
function doWorkflow(action: string) {
  wfAction.value = action
  wfDialogTitle.value = wfLabels[action] || action
  wfForm.opinion = ''
  wfForm.allocated_amount = fundData.approved_amount || fundData.amount || 0
  wfForm.allocation_method = ''
  wfForm.audit_result = '通过'
  wfDialogVisible.value = true
}
async function submitWorkflow() {
  wfSubmitting.value = true
  try {
    const apiMap: Record<string, Function> = {
      approve: fundApi.approve,
      reject: fundApi.reject,
      allocate: fundApi.allocate,
      start_use: fundApi.startUse,
      complete: fundApi.complete,
      audit: fundApi.audit,
    }
    const fn = apiMap[wfAction.value]
    if (!fn) return
    if (wfAction.value === 'reject' && !wfForm.opinion.trim()) {
      ElMessage.warning('驳回时必须填写驳回原因')
      return
    }
    await fn(fundData.id, {
      opinion: wfForm.opinion || undefined,
      allocated_amount: wfAction.value === 'allocate' ? wfForm.allocated_amount : undefined,
      allocation_method: wfAction.value === 'allocate' ? wfForm.allocation_method : undefined,
      audit_result: wfAction.value === 'audit' ? wfForm.audit_result : undefined,
    })
    // 关键动作（审批/拨付/审计等）用带标题的通知
    ElNotification({
      title: wfDialogTitle.value,
      message: `${wfDialogTitle.value}操作成功`,
      type: 'success',
    })
    wfDialogVisible.value = false
    await loadFundDetail()
    // 工作流流转会落状态历史/操作日志/审批流节点，四个日志 tab 必须同步重载
    await loadAllHistory()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    ElMessage.error(typeof d === 'string' ? d : '操作失败')
  } finally {
    wfSubmitting.value = false
  }
}

// CRUD
// ── 报销核销（T021）：明细列表 + 录入，自动累计剩余可用 ──
const expenses = ref<any[]>([])
const loadingExpenses = ref(false)
const expDialogVisible = ref(false)
const expSubmitting = ref(false)
const expForm = reactive({
  amount: undefined as number | undefined,
  transaction_date: '',
  purpose: '',
  handler: '',
  receipt_number: '',
})

async function loadExpenses() {
  if (isCreate.value) return
  loadingExpenses.value = true
  try {
    const res = await apiRequest({
      method: 'GET',
      url: '/fund-budgets/transactions',
      params: { fund_id: fundData.id, page_size: 100 },
    })
    const data = (res as any)?.data ?? res
    expenses.value = Array.isArray(data) ? data : (data?.items ?? [])
  } catch (e) {
    logger.error('报销明细加载失败:', e)
    expenses.value = []
  } finally {
    loadingExpenses.value = false
  }
}

async function submitExpense() {
  if (!expForm.amount || expForm.amount <= 0) {
    ElMessage.warning('请填写报销金额')
    return
  }
  if (!expForm.purpose.trim()) {
    ElMessage.warning('请填写用途说明')
    return
  }
  if (!expForm.transaction_date) {
    ElMessage.warning('请选择报销日期')
    return
  }
  expSubmitting.value = true
  try {
    await apiRequest({
      method: 'POST',
      url: '/fund-budgets/transactions',
      data: { ...expForm, fund_id: fundData.id },
    })
    ElNotification({ title: '报销登记', message: '报销登记成功', type: 'success' })
    expDialogVisible.value = false
    Object.assign(expForm, {
      amount: undefined,
      transaction_date: '',
      purpose: '',
      handler: '',
      receipt_number: '',
    })
    await loadExpenses()
    await loadFundDetail()
  } catch (e: any) {
    const d = e?.response?.data?.detail
    ElMessage.error(typeof d === 'string' ? d : '报销登记失败')
  } finally {
    expSubmitting.value = false
  }
}

const loadFundDetail = async () => {
  if (isCreate.value) {
    loading.value = false
    return
  }
  const id = route.params.id as string
  if (!id) {
    loading.value = false
    ElMessage.error('无效的经费记录ID')
    pushSafe('/funds')
    return
  }
  loading.value = true
  try {
    const res = await get(`/funds/${id}`)
    Object.assign(fundData, res.data)
    syncFormData(res.data)
  } catch {
    ElMessage.error('加载经费详情失败')
    pushSafe('/funds')
    await loadExpenses()
  } finally {
    loading.value = false
  }
}
function syncFormData(d: any) {
  Object.assign(formData, {
    code: d.code || '',
    name: d.name || '',
    date: d.date || null,
    type: d.type || 'project',
    fund_source: d.fund_source || '',
    amount: d.amount || 0,
    planned_amount: d.planned_amount || 0,
    approved_amount: d.approved_amount,
    allocated_amount: d.allocated_amount || 0,
    used_amount: d.used_amount || 0,
    remaining_amount: d.remaining_amount || 0,
    project_name: d.project_name || '',
    village_id: d.village_id || null,
    purpose: d.purpose || '',
    source: d.source || '',
    operator: d.operator || '',
    receiver: d.receiver || '',
    usage_description: d.usage_description || '',
    status: d.status || 'pending',
    remarks: d.remarks || '',
    dateRange:
      d.start_date && d.end_date
        ? [String(d.start_date).split('T')[0], String(d.end_date).split('T')[0]]
        : null,
  })
}
const goBack = () => pushSafe('/funds')
const handleEdit = () => {
  isEdit.value = true
}
const cancelEdit = () => {
  isEdit.value = false
  syncFormData(fundData)
}
const handleSubmit = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
    submitting.value = true
    const payload: any = { ...formData }
    if (!payload.date) delete payload.date
    if (!payload.village_id) delete payload.village_id
    if (payload.dateRange?.length === 2) {
      payload.start_date = payload.dateRange[0]
      payload.end_date = payload.dateRange[1]
    }
    delete payload.dateRange
    Object.keys(payload).forEach((k) => {
      if (payload[k] === null || payload[k] === '') delete payload[k]
    })
    if (isCreate.value) {
      await post('/funds', payload)
      // 成功静默：创建成功仅刷新
      pushSafe('/funds')
    } else {
      await put(`/funds/${fundData.id}`, payload)
      // 成功静默：保存成功仅刷新
      isEdit.value = false
      await loadFundDetail()
      // 编辑会落字段变更（FundFieldChange）与操作日志，修改记录/操作日志 tab 同步重载
      await loadAllHistory()
    }
  } catch (error: any) {
    if (!error?.fields) {
      const detail = error?.response?.data?.detail || error?.response?.data?.message || ''
      ElMessage.error(detail ? `保存失败: ${detail}` : '保存失败，请检查输入')
    }
  } finally {
    submitting.value = false
  }
}
const handleDelete = async () => {
  try {
    await ElMessageBox.confirm('确定要删除这条经费记录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await del(`/funds/${fundData.id}`)
    // 成功静默：删除成功仅刷新
    pushSafe('/funds')
  } catch (e: any) {
    if (e !== 'cancel') logger.error('删除失败', e)
  }
}
const checkPageMode = () => {
  if (route.path.endsWith('/create')) {
    isCreate.value = true
    isEdit.value = true
  } else if (route.path.endsWith('/edit')) {
    isEdit.value = true
  }
}
onMounted(async () => {
  checkPageMode()
  // 并行加载数据，提高页面加载性能
  await loadFundDetail()
  await loadAllHistory()
})
// 路由变化时重新检测页面模式（如 /funds/5 → /funds/5/edit）
// 同一组件实例复用时 onMounted 不会重新触发，需 watch route.path
watch(
  () => route.path,
  () => {
    checkPageMode()
    if (!isCreate.value) loadFundDetail()
  }
)
onBeforeUnmount(() => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
})
onUnmounted(() => {
  // 清理资源
})
</script>

<style scoped>
.fund-detail-page {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
}
.header-actions {
  display: flex;
  gap: 12px;
}
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100px 0;
  color: var(--color-text-secondary);
}
.loading-icon {
  font-size: 32px;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
.detail-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
  overflow: hidden;
}
.card-header {
  padding: 16px 24px;
  background: linear-gradient(135deg, var(--color-primary-dark-1) 0%, var(--color-primary) 100%);
}
.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: white;
}
.card-body {
  padding: 24px;
}
.amount-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
}
.workflow-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--color-success-lightest);
  border: 1px solid #b3e19d;
  border-radius: 8px;
  padding: 16px 24px;
  margin-bottom: 20px;
}
.workflow-status {
  font-size: 15px;
  font-weight: 500;
}
.workflow-actions {
  display: flex;
  gap: 10px;
}
.attachment-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  padding: 6px 8px;
  border-radius: 4px;
}
.attachment-item:hover {
  background: var(--color-bg-hover);
}
.att-name {
  font-size: 13px;
  flex: 1;
}
.att-size {
  font-size: 12px;
  color: var(--color-text-secondary);
}
:deep(.el-descriptions__label) {
  font-weight: 500;
  background-color: var(--color-bg-hover);
}
:deep(.el-descriptions__content) {
  color: var(--color-text-primary);
}

/* 时间线样式 */
.timeline-content {
  padding: 8px 0;
}
.timeline-title {
  font-weight: 500;
  margin-bottom: 4px;
}
.timeline-info {
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* 标签页样式 */
:deep(.el-tabs--border-card) {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}
:deep(.el-tabs--border-card > .el-tabs__header) {
  background: var(--color-bg-hover);
  border-radius: 8px 8px 0 0;
}
:deep(.el-tabs--border-card > .el-tabs__header .el-tabs__item.is-active) {
  background: white;
  color: var(--color-primary-dark-1);
}

/* 文本样式 */
.text-muted {
  color: var(--color-info);
}
.text-primary {
  color: var(--color-primary-dark-1);
  font-weight: 500;
}
</style>
