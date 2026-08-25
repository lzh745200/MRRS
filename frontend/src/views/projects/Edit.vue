<template>
  <div class="project-edit-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/projects' }">项目管理</el-breadcrumb-item>
        <el-breadcrumb-item>
          {{ isEditMode ? '编辑项目' : '新建项目' }}
        </el-breadcrumb-item>
      </el-breadcrumb>
      <h2 class="page-title">{{ isEditMode ? '编辑项目' : '新建项目' }}</h2>
    </div>

    <!-- 项目表单卡片 -->
    <el-card class="form-card" shadow="hover">
      <el-form
        ref="projectFormRef"
        :model="projectForm"
        :rules="formRules as any"
        label-width="120px"
        class="project-form"
      >
        <el-divider content-position="left">基本信息</el-divider>

        <!-- 项目基本信息 -->
        <div class="form-row">
          <el-form-item v-if="isEditMode" label="项目编号" prop="id">
            <el-input v-model="projectForm.id" readonly />
          </el-form-item>
          <el-form-item label="项目名称" prop="name">
            <el-input
              v-model="projectForm.name"
              placeholder="请输入项目名称"
              clearable
              maxlength="100"
              show-word-limit
            />
          </el-form-item>
          <el-form-item label="项目类型" prop="projectType">
            <el-select v-model="projectForm.projectType" placeholder="请选择项目类型" clearable>
              <el-option label="基础设施建设" value="infrastructure"></el-option>
              <el-option label="产业发展" value="industry"></el-option>
              <el-option label="教育支持" value="education"></el-option>
              <el-option label="医疗保障" value="medical"></el-option>
              <el-option label="文化建设" value="culture"></el-option>
              <el-option label="其他" value="other"></el-option>
            </el-select>
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="帮扶村" prop="villageId">
            <el-select
              v-model="projectForm.villageId"
              placeholder="请选择帮扶村"
              filterable
              clearable
            >
              <el-option
                v-for="village in villages"
                :key="village.id"
                :label="village.name"
                :value="village.id"
              ></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="项目状态" prop="status">
            <el-select v-model="projectForm.status" placeholder="请选择项目状态" clearable>
              <!-- 与后端 ProjectStatus 枚举保持一致 -->
              <el-option label="草稿" value="draft"></el-option>
              <el-option label="待审批" value="pending"></el-option>
              <el-option label="已审批" value="approved"></el-option>
              <el-option label="进行中" value="in_progress"></el-option>
              <el-option label="已完成" value="completed"></el-option>
              <el-option label="已取消" value="cancelled"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="紧急程度" prop="urgencyLevel">
            <el-select v-model="projectForm.urgencyLevel" placeholder="请选择紧急程度" clearable>
              <el-option label="一般" value="normal"></el-option>
              <el-option label="重要" value="important"></el-option>
              <el-option label="紧急" value="urgent"></el-option>
            </el-select>
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="负责人" prop="responsiblePerson">
            <el-input
              v-model="projectForm.responsiblePerson"
              placeholder="请输入负责人姓名"
              clearable
              maxlength="50"
            />
          </el-form-item>
          <el-form-item label="联系电话" prop="contactPhone">
            <el-input
              v-model="projectForm.contactPhone"
              placeholder="请输入联系电话"
              clearable
              maxlength="20"
            />
          </el-form-item>
          <el-form-item label="合同编号" prop="contractNumber">
            <el-input
              v-model="projectForm.contractNumber"
              placeholder="请输入合同编号"
              clearable
              maxlength="50"
            />
          </el-form-item>
        </div>

        <el-divider content-position="left">时间规划</el-divider>

        <div class="form-row">
          <el-form-item label="开始日期" prop="startDate">
            <el-date-picker
              v-model="projectForm.startDate"
              type="date"
              placeholder="请选择开始日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
            />
          </el-form-item>
          <el-form-item label="结束日期" prop="endDate">
            <el-date-picker
              v-model="projectForm.endDate"
              type="date"
              placeholder="请选择结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
            />
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="实际完成率" prop="completionRate">
            <el-input-number
              v-model="projectForm.completionRate"
              :min="0"
              :max="100"
              :step="1"
              placeholder="请输入实际完成率"
            />
            <span class="input-suffix">%</span>
          </el-form-item>
          <el-form-item label="是否延期" prop="isDelayed">
            <el-switch v-model="projectForm.isDelayed" active-text="是" inactive-text="否" />
          </el-form-item>
          <el-form-item v-if="projectForm.isDelayed" label="延期原因" prop="delayReason">
            <el-input
              v-model="projectForm.delayReason"
              placeholder="请输入延期原因"
              type="textarea"
              :rows="2"
              maxlength="200"
              show-word-limit
            />
          </el-form-item>
        </div>

        <el-divider content-position="left">资金信息</el-divider>

        <div class="form-row">
          <el-form-item label="资金投入(万元)" prop="fundAmount">
            <el-input-number
              v-model="projectForm.fundAmount"
              :min="0"
              :precision="4"
              :step="0.0001"
              placeholder="请输入资金投入"
              :prefix-icon="Wallet"
            />
          </el-form-item>
          <el-form-item label="资金来源" prop="fundSource">
            <el-select v-model="projectForm.fundSource" placeholder="请选择资金来源" clearable>
              <el-option label="上级拨付" value="superior_allocation"></el-option>
              <el-option label="本级预算投入" value="local_budget"></el-option>
              <el-option label="财政专项资金" value="financial"></el-option>
              <el-option label="社会捐赠" value="donation"></el-option>
              <el-option label="自筹资金" value="self_raised"></el-option>
              <el-option label="其他" value="other"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="已拨付资金(万元)" prop="allocatedFund">
            <el-input-number
              v-model="projectForm.allocatedFund"
              :min="0"
              :precision="4"
              :step="0.0001"
              placeholder="请输入已拨付资金"
              :prefix-icon="Wallet"
            />
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="资金使用进度" prop="fundUsageProgress">
            <el-input-number
              v-model="projectForm.fundUsageProgress"
              :min="0"
              :max="100"
              :step="1"
              placeholder="请输入资金使用进度"
            />
            <span class="input-suffix">%</span>
          </el-form-item>
          <el-form-item label="资金负责人" prop="fundManager">
            <el-input
              v-model="projectForm.fundManager"
              placeholder="请输入资金负责人"
              clearable
              maxlength="50"
            />
          </el-form-item>
          <el-form-item label="资金使用计划" prop="fundUsagePlan">
            <el-select
              v-model="projectForm.fundUsagePlan"
              placeholder="请选择资金使用计划"
              clearable
            >
              <el-option label="一次性拨付" value="one_time"></el-option>
              <el-option label="分阶段拨付" value="staged"></el-option>
              <el-option label="按需拨付" value="as_needed"></el-option>
            </el-select>
          </el-form-item>
        </div>

        <!-- 资金拨付去向信息 -->
        <el-divider content-position="left">资金拨付去向信息</el-divider>

        <div class="fund-transfer-section">
          <div class="transfer-block">
            <h4 class="transfer-title">拨款方信息</h4>
            <div class="form-row">
              <el-form-item label="账户名称" prop="payerAccountName">
                <el-input
                  v-model="projectForm.payerAccountName"
                  placeholder="请输入拨款账户名称"
                  clearable
                  maxlength="200"
                />
              </el-form-item>
              <el-form-item label="卡号" prop="payerAccountNumber">
                <el-input
                  v-model="projectForm.payerAccountNumber"
                  placeholder="请输入拨款卡号"
                  clearable
                  maxlength="50"
                />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="开户行" prop="payerBank">
                <el-input
                  v-model="projectForm.payerBank"
                  placeholder="请输入拨款开户行"
                  clearable
                  maxlength="200"
                />
              </el-form-item>
              <el-form-item label="经办人" prop="payerHandler">
                <el-input
                  v-model="projectForm.payerHandler"
                  placeholder="请输入经办人"
                  clearable
                  maxlength="50"
                />
              </el-form-item>
              <el-form-item label="联系方式" prop="payerContact">
                <el-input
                  v-model="projectForm.payerContact"
                  placeholder="请输入联系方式"
                  clearable
                  maxlength="50"
                />
              </el-form-item>
            </div>
          </div>

          <div class="transfer-block">
            <h4 class="transfer-title">收款方信息</h4>
            <div class="form-row">
              <el-form-item label="账户名称" prop="payeeAccountName">
                <el-input
                  v-model="projectForm.payeeAccountName"
                  placeholder="请输入收款单位账户名称"
                  clearable
                  maxlength="200"
                />
              </el-form-item>
              <el-form-item label="卡号" prop="payeeAccountNumber">
                <el-input
                  v-model="projectForm.payeeAccountNumber"
                  placeholder="请输入收款卡号"
                  clearable
                  maxlength="50"
                />
              </el-form-item>
              <el-form-item label="开户行" prop="payeeBank">
                <el-input
                  v-model="projectForm.payeeBank"
                  placeholder="请输入收款开户行"
                  clearable
                  maxlength="200"
                />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="经办人" prop="payeeHandler">
                <el-input
                  v-model="projectForm.payeeHandler"
                  placeholder="请输入经办人"
                  clearable
                  maxlength="50"
                />
              </el-form-item>
              <el-form-item label="联系方式" prop="payeeContact">
                <el-input
                  v-model="projectForm.payeeContact"
                  placeholder="请输入联系方式"
                  clearable
                  maxlength="50"
                />
              </el-form-item>
            </div>
          </div>
        </div>

        <!-- 地域属性 -->
        <el-divider content-position="left">地域属性</el-divider>

        <div class="form-row">
          <el-form-item label="三区三州">
            <el-switch
              v-model="projectForm.isThreeRegionsThreeStates"
              active-text="是"
              inactive-text="否"
            />
          </el-form-item>
          <el-form-item label="边疆地区">
            <el-switch v-model="projectForm.isBorderArea" active-text="是" inactive-text="否" />
          </el-form-item>
          <el-form-item label="民族地区">
            <el-switch v-model="projectForm.isEthnicArea" active-text="是" inactive-text="否" />
          </el-form-item>
        </div>
        <div class="form-row">
          <el-form-item label="革命地区">
            <el-switch
              v-model="projectForm.isRevolutionaryArea"
              active-text="是"
              inactive-text="否"
            />
          </el-form-item>
          <el-form-item label="重点帮扶县">
            <el-switch v-model="projectForm.isKeyCounty" active-text="是" inactive-text="否" />
          </el-form-item>
        </div>

        <!-- 振兴属性 -->
        <el-divider content-position="left">振兴属性</el-divider>

        <div class="form-row">
          <el-form-item label="振兴梯队">
            <el-switch v-model="projectForm.isRevitalizationTier" />
          </el-form-item>
          <el-form-item label="省级乡村振兴示范">
            <el-switch v-model="projectForm.isProvincialDemo" active-text="是" inactive-text="否" />
          </el-form-item>
          <el-form-item label="百村示范创建">
            <el-switch
              v-model="projectForm.isHundredVillageDemo"
              active-text="是"
              inactive-text="否"
            />
          </el-form-item>
        </div>
        <div class="form-row">
          <el-form-item label="梯次振兴发展">
            <el-switch
              v-model="projectForm.isTieredDevelopment"
              active-text="是"
              inactive-text="否"
            />
          </el-form-item>
        </div>

        <el-divider content-position="left">项目详情</el-divider>

        <div class="form-row">
          <el-form-item label="项目描述" prop="description">
            <el-input
              v-model="projectForm.description"
              type="textarea"
              :rows="4"
              placeholder="请详细描述项目情况、背景、目标等"
              maxlength="1000"
              show-word-limit
            />
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="预期效益" prop="expectedBenefits">
            <el-input
              v-model="projectForm.expectedBenefits"
              type="textarea"
              :rows="3"
              placeholder="请描述项目预期产生的经济效益、社会效益等"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="项目成果" prop="achievements">
            <el-input
              v-model="projectForm.achievements"
              type="textarea"
              :rows="3"
              placeholder="请描述项目已取得的成果"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="项目标签" prop="tags">
            <el-checkbox-group v-model="projectForm.tags">
              <el-checkbox value="示范项目">示范项目</el-checkbox>
              <el-checkbox value="扶贫项目">扶贫项目</el-checkbox>
              <el-checkbox value="民生项目">民生项目</el-checkbox>
              <el-checkbox value="产业项目">产业项目</el-checkbox>
              <el-checkbox value="重点项目">重点项目</el-checkbox>
              <el-checkbox value="新建项目">新建项目</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="备注" prop="remarks">
            <el-input
              v-model="projectForm.remarks"
              type="textarea"
              :rows="2"
              placeholder="其他需要说明的事项"
              maxlength="200"
              show-word-limit
            />
          </el-form-item>
        </div>

        <!-- 附件上传 -->
        <el-divider content-position="left">附件管理</el-divider>

        <div class="attachment-section">
          <el-tabs v-model="activeFileTab" type="border-card">
            <el-tab-pane
              v-for="cat in fileCategories"
              :key="cat.value"
              :label="cat.label"
              :name="cat.value"
            >
              <el-upload
                class="upload-demo"
                drag
                action=""
                :auto-upload="false"
                :multiple="cat.value === 'photo'"
                :limit="cat.value === 'photo' ? 50 : 20"
                :accept="cat.value === 'photo' ? 'image/*' : undefined"
                :on-change="(file: any) => handleFileChange(file, cat.value)"
                :on-exceed="handleExceed"
                :show-file-list="false"
              >
                <el-icon class="el-icon--upload"><Upload /></el-icon>
                <div class="el-upload__text">拖拽文件到此处或<em>点击上传</em></div>
                <template #tip>
                  <div class="el-upload__tip">
                    {{
                      cat.value === 'photo'
                        ? '支持批量上传图片，最多50张，单张不超过50MB'
                        : '支持上传文档、图片等，最多20个文件，单个不超过50MB'
                    }}
                  </div>
                </template>
              </el-upload>

              <!-- 待上传文件列表 -->
              <div v-if="pendingFiles[cat.value]?.length" class="pending-files">
                <h5>待上传文件</h5>
                <div
                  v-for="(pf, idx) in pendingFiles[cat.value]"
                  :key="idx"
                  class="file-item pending"
                >
                  <span class="file-name">{{ pf.name }}</span>
                  <span class="file-size">{{ formatFileSize(pf.size) }}</span>
                  <el-button
                    type="danger"
                    link
                    size="small"
                    @click="removePendingFile(cat.value, idx)"
                    >删除</el-button
                  >
                </div>
              </div>

              <!-- 已上传文件列表 -->
              <div v-if="uploadedFiles[cat.value]?.length" class="uploaded-files">
                <h5>已上传文件</h5>
                <div v-if="cat.value === 'photo'" class="photo-gallery">
                  <div v-for="uf in uploadedFiles[cat.value]" :key="uf.id" class="photo-item">
                    <img
                      :src="getThumbnailUrl(uf)"
                      :alt="uf.filename"
                      class="photo-thumb"
                      @click="previewImage(uf)"
                    />
                    <div class="photo-info">
                      <span class="file-name">{{ uf.filename }}</span>
                      <span class="photo-actions">
                        <el-button type="primary" link size="small" @click="handleDownloadFile(uf)"
                          >下载</el-button
                        >
                        <el-button type="danger" link size="small" @click="handleDeleteFile(uf)"
                          >删除</el-button
                        >
                      </span>
                    </div>
                  </div>
                </div>
                <div v-else>
                  <div
                    v-for="uf in uploadedFiles[cat.value]"
                    :key="uf.id"
                    class="file-item uploaded"
                  >
                    <span class="file-name">{{ uf.filename }}</span>
                    <span class="file-size">{{ formatFileSize(uf.file_size) }}</span>
                    <span class="file-date">{{ uf.created_at?.slice(0, 10) }}</span>
                    <el-button type="primary" link size="small" @click="handleDownloadFile(uf)"
                      >下载</el-button
                    >
                    <el-button type="danger" link size="small" @click="handleDeleteFile(uf)"
                      >删除</el-button
                    >
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>

        <!-- 操作按钮 -->
        <div class="form-actions">
          <el-button @click="handleCancel">
            <el-icon><ArrowLeft /></el-icon>
            返回列表
          </el-button>
          <el-button type="primary" @click="handleSave('projectFormRef')">
            <el-icon><Check /></el-icon>
            {{ isEditMode ? '保存修改' : '创建项目' }}
          </el-button>
          <el-button v-if="!isEditMode" type="success" @click="handleSaveAndContinue">
            <el-icon><Check /></el-icon>
            保存并继续创建
          </el-button>
        </div>
      </el-form>
    </el-card>

    <!-- 图片预览对话框 -->
    <el-dialog
      v-model="previewVisible"
      title="图片预览"
      width="80%"
      top="5vh"
      destroy-on-close
      @close="handlePreviewClose"
    >
      <img
        v-if="previewUrl"
        :src="previewUrl"
        style="width: 100%; max-height: 75vh; object-fit: contain"
        alt="预览图片"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'
import { getErrorMessage } from '@/utils/getErrorMessage'

import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useDirtyGuard } from '@/composables/useDirtyGuard'
import { ElMessage, ElMessageBox, ElForm } from 'element-plus'
import { Upload, ArrowLeft, Check, Wallet } from '@element-plus/icons-vue'

import { projectApi } from '@/api/projects'
import { get } from '@/api/request'
import { AuthStorage } from '@/utils/authStorage'

// 文件分类定义
const fileCategories = [
  { label: '项目研究论证', value: 'research' },
  { label: '项目立项', value: 'approval' },
  { label: '项目组织实施', value: 'implementation' },
  { label: '项目验收', value: 'acceptance' },
  { label: '项目照片', value: 'photo' },
]
const activeFileTab = ref('research')

const { pushSafe } = useRouterSafe()
const route = useRoute()

// 表单引用
const projectFormRef = ref<InstanceType<typeof ElForm> | null>(null)

// 判断是编辑模式还是新建模式
const isEditMode = computed(() => {
  return !!route.params.id
})

// 加载状态
const loading = ref(false)
// 保存失败的详细原因（供外层提示，替代笼统的“保存失败，请稍后重试”）
const saveErrorMessage = ref('')

// 文件列表
const fileList = ref<any[]>([])

// 待上传 & 已上传文件分类存储
const pendingFiles = reactive<Record<string, File[]>>({
  research: [],
  approval: [],
  implementation: [],
  acceptance: [],
  photo: [],
})
const uploadedFiles = reactive<Record<string, any[]>>({
  research: [],
  approval: [],
  implementation: [],
  acceptance: [],
  photo: [],
})

// 图片缩略图 Blob URL 映射（key = file.id），用于认证模式下 <img :src> 加载
const thumbnailUrls = reactive<Record<number | string, string>>({})

// 村庄数据（从帮扶村管理模块动态加载）
const villages = ref<{ id: number | string; name: string; county?: string }[]>([])

// 加载帮扶村下拉选项
async function loadVillageOptions() {
  try {
    const res = await get('/supported-villages/options/dropdown')
    const items = res.data?.items || []
    villages.value = items.map((v: any) => ({
      id: v.id,
      name: v.county ? `${v.name}（${v.county}）` : v.name,
    }))
  } catch (error) {
    logger.warn('加载帮扶村列表失败:', error)
    villages.value = []
  }
}

// 项目表单数据
const projectForm = reactive({
  id: '',
  name: '',
  projectType: '',
  status: 'draft',
  villageId: '',
  villageName: '',
  fundAmount: 0,
  fundSource: 'financial',
  allocatedFund: 0,
  fundUsageProgress: 0,
  startDate: '',
  endDate: '',
  completionRate: 0,
  responsiblePerson: '',
  contactPhone: '',
  contractNumber: '',
  urgencyLevel: 'normal',
  fundManager: '',
  fundUsagePlan: 'one_time',
  // 资金拨付去向
  payerAccountName: '',
  payerAccountNumber: '',
  payerBank: '',
  payerHandler: '',
  payerContact: '',
  payeeAccountName: '',
  payeeAccountNumber: '',
  payeeBank: '',
  payeeHandler: '',
  payeeContact: '',
  isDelayed: false,
  delayReason: '',
  description: '',
  expectedBenefits: '',
  achievements: '',
  tags: [] as string[],
  remarks: '',
  // 地域属性
  isThreeRegionsThreeStates: false,
  isBorderArea: false,
  isEthnicArea: false,
  isRevolutionaryArea: false,
  isKeyCounty: false,
  // 振兴属性
  isRevitalizationTier: false,
  isProvincialDemo: false,
  isHundredVillageDemo: false,
  isTieredDevelopment: false,
  createTime: '',
  updateTime: '',
})

// Dirty guard: warn before leaving with unsaved changes
const isDirty = ref(false)
watch(
  () => projectForm,
  () => {
    isDirty.value = true
  },
  { deep: true }
)
useDirtyGuard(isDirty)

// 表单验证规则
const formRules = reactive({
  name: [
    { required: true, message: '请输入项目名称', trigger: ['blur', 'change'] },
    {
      min: 2,
      max: 100,
      message: '项目名称长度在 2 到 100 个字符',
      trigger: ['blur', 'change'],
    },
  ],
  projectType: [{ required: true, message: '请选择项目类型', trigger: 'change' }],
  villageId: [{ required: true, message: '请选择帮扶村', trigger: 'change' }],
  status: [{ required: true, message: '请选择项目状态', trigger: 'change' }],
  startDate: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  endDate: [
    { required: true, message: '请选择结束日期', trigger: 'change' },
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (value && projectForm.startDate && new Date(value) < new Date(projectForm.startDate)) {
          callback(new Error('结束日期不能早于开始日期'))
        } else {
          callback()
        }
      },
      trigger: 'change',
    },
  ],
  fundAmount: [
    { required: true, message: '请输入资金投入', trigger: ['blur', 'change'] },
    {
      type: 'number',
      min: 0,
      message: '资金投入必须大于或等于0',
      trigger: ['blur', 'change'],
    },
  ],
  fundSource: [{ required: true, message: '请选择资金来源', trigger: 'change' }],
  responsiblePerson: [
    { required: true, message: '请输入负责人', trigger: ['blur', 'change'] },
    {
      min: 1,
      max: 50,
      message: '负责人名称长度在 1 到 50 个字符',
      trigger: ['blur', 'change'],
    },
  ],
  contactPhone: [
    {
      pattern: /^1[3-9]\d{9}$|^(0\d{2,3}-\d{7,8})$/,
      message: '请输入正确的手机号码或固定电话',
      trigger: ['blur', 'change'],
    },
  ],
  completionRate: [
    {
      type: 'number',
      min: 0,
      max: 100,
      message: '完成率必须在0-100之间',
      trigger: ['blur', 'change'],
    },
  ],
  allocatedFund: [
    {
      validator: (_rule: unknown, value: number, callback: (error?: Error) => void) => {
        if (value > projectForm.fundAmount) {
          callback(new Error('已拨付资金不能大于总资金投入'))
        } else {
          callback()
        }
      },
      trigger: ['blur', 'change'],
    },
  ],
  payerAccountNumber: [
    {
      pattern: /^[0-9\s-]{10,30}$/,
      message: '请输入正确的银行卡号（10-30位数字）',
      trigger: ['blur', 'change'],
    },
  ],
  payeeAccountNumber: [
    {
      pattern: /^[0-9\s-]{10,30}$/,
      message: '请输入正确的银行卡号（10-30位数字）',
      trigger: ['blur', 'change'],
    },
  ],
})

// 处理文件超出数量
function handleExceed(_files: File[], _fileList: any[]) {
  ElMessage.warning('文件数量超出限制，已自动过滤多余的文件')
}

// 处理文件选择（放入待上传队列）
function handleFileChange(uploadFile: any, category: string) {
  if (uploadFile?.raw) {
    pendingFiles[category].push(uploadFile.raw)
  }
}

// 移除待上传文件
function removePendingFile(category: string, idx: number) {
  pendingFiles[category].splice(idx, 1)
}

// 格式化文件大小
function formatFileSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(2) + ' MB'
}

// 获取文件下载/预览URL（仅用于 fetch 请求，不直接用于 <img :src>，因为需要认证头）
function getFileUrl(file: any): string {
  if (file.download_url) return file.download_url
  const rawId = route.params.id as string
  const projectId = isNaN(Number(rawId)) ? rawId : Number(rawId)
  return projectApi.getFileDownloadUrl(projectId, file.id)
}

// 获取缩略图 URL（优先使用已加载的 Blob URL，回退到空字符串）
function getThumbnailUrl(file: any): string {
  return thumbnailUrls[file.id] || ''
}

// 异步加载单个图片缩略图的 Blob URL
async function loadThumbnail(file: any) {
  try {
    const url = getFileUrl(file)
    const token = AuthStorage.getToken()
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) return
    const blob = await response.blob()
    // 如果该文件已有旧的 Blob URL，先释放
    if (thumbnailUrls[file.id]) URL.revokeObjectURL(thumbnailUrls[file.id])
    thumbnailUrls[file.id] = URL.createObjectURL(blob)
  } catch {
    // 缩略图加载失败不提示错误，静默处理
  }
}

// 为所有 photo 分类的文件预加载缩略图
async function loadAllThumbnails() {
  const photoFiles = uploadedFiles.photo || []
  await Promise.all(photoFiles.map((f) => loadThumbnail(f)))
}

// 释放所有缩略图 Blob URL
function revokeAllThumbnails() {
  for (const key of Object.keys(thumbnailUrls)) {
    URL.revokeObjectURL(thumbnailUrls[key])
    delete thumbnailUrls[key]
  }
}

// 预览图片（使用认证 blob 方式，兼容 Electron）
const previewVisible = ref(false)
const previewUrl = ref('')

async function previewImage(file: any) {
  try {
    const url = getFileUrl(file)
    const token = AuthStorage.getToken()
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error('Preview failed')
    const blob = await response.blob()
    // Revoke previous blob URL if any
    if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = URL.createObjectURL(blob)
    previewVisible.value = true
  } catch (e) {
    logger.error('预览图片失败:', e)
    ElMessage.error('预览图片失败')
  }
}

function handlePreviewClose() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

// 下载已上传文件（认证 fetch → blob → 触发浏览器下载）
async function handleDownloadFile(file: any) {
  try {
    const url = getFileUrl(file)
    const token = AuthStorage.getToken()
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error('Download failed')
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = file.filename || file.name || 'download'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(objectUrl)
  } catch (e) {
    logger.error('下载文件失败:', e)
    ElMessage.error(getErrorMessage(e, '文件下载失败，请稍后重试'))
  }
}

// 删除已上传文件
async function handleDeleteFile(file: any) {
  try {
    await ElMessageBox.confirm('确定要删除该文件吗？', '确认', {
      type: 'warning',
    })
    const rawId = route.params.id as string
    const projectId = isNaN(Number(rawId)) ? rawId : Number(rawId)
    await projectApi.deleteFile(projectId, file.id)
    // 从列表中移除
    const cat = file.category as string
    uploadedFiles[cat] = uploadedFiles[cat].filter((f: any) => f.id !== file.id)
    // 释放被删除文件的缩略图 Blob URL
    if (thumbnailUrls[file.id]) {
      URL.revokeObjectURL(thumbnailUrls[file.id])
      delete thumbnailUrls[file.id]
    }
    ElMessage.success('文件已删除')
  } catch (e: any) {
    if (e !== 'cancel') logger.error('删除文件失败:', e)
  }
}

// 上传所有待上传文件
async function uploadAllPendingFiles(projectId: number | string) {
  let totalUploaded = 0
  for (const cat of Object.keys(pendingFiles)) {
    const files = pendingFiles[cat]
    if (!files || files.length === 0) continue
    try {
      const result = await projectApi.uploadFiles(projectId, cat, files)
      if (result?.files) {
        uploadedFiles[cat] = [...(uploadedFiles[cat] || []), ...result.files]
        // 如果是 photo 分类，异步加载新上传图片的缩略图
        if (cat === 'photo') {
          result.files.forEach((f: any) => loadThumbnail(f))
        }
        totalUploaded += result.files.length
      }
      // 清空已上传的待上传队列
      pendingFiles[cat] = []
    } catch (e) {
      logger.error(`上传${cat}分类文件失败:`, e)
      ElMessage.error(getErrorMessage(e, `部分文件上传失败（${cat}），请稍后重试`))
    }
  }
  return totalUploaded
}

// 加载项目已上传文件列表
async function loadProjectFiles(projectId: number | string) {
  try {
    const result = await projectApi.listFiles(projectId)
    // 清空并重新填充各分类
    for (const cat of Object.keys(uploadedFiles)) {
      uploadedFiles[cat] = []
    }
    if (result?.grouped) {
      for (const [cat, files] of Object.entries(result.grouped)) {
        uploadedFiles[cat] = files as any[]
      }
    }
    // 异步预加载 photo 分类的缩略图
    loadAllThumbnails()
  } catch (e) {
    logger.warn('加载项目附件列表失败:', e)
  }
}

// 加载项目数据
async function loadProjectData() {
  if (!isEditMode.value) return

  const rawId = route.params.id as string
  if (!rawId) {
    ElMessage.error('无效的项目 ID')
    pushSafe('/projects')
    return
  }
  // 同时支持数字 ID 和字符串 ID（如离线模式 offline-xxx）
  const projectId: number | string = isNaN(Number(rawId)) ? rawId : Number(rawId)

  loading.value = true
  try {
    const resp = await projectApi.getById(projectId)
    const data = resp
    if (!data) {
      ElMessage.error('未找到项目数据')
      pushSafe('/projects')
      return
    }

    // 后端字段 → 前端表单字段映射
    Object.assign(projectForm, {
      id: String(data.id ?? rawId),
      name: data.name || '',
      projectType: data.type || '',
      status: data.status || 'draft',
      villageId: data.village_id ? Number(data.village_id) : '',
      villageName: '',
      fundAmount: Number(data.budget) || 0,
      fundSource: data.fund_source || '',
      allocatedFund: Number(data.invested_amount) || 0,
      fundUsageProgress: data.budget
        ? Math.round(((Number(data.invested_amount) || 0) / Number(data.budget)) * 100)
        : 0,
      startDate: data.start_date ? String(data.start_date) : '',
      endDate: data.end_date ? String(data.end_date) : '',
      completionRate: data.progress || 0,
      responsiblePerson: data.responsible_person || '',
      contactPhone: data.contact_phone || '',
      contractNumber: data.contract_number || '',
      urgencyLevel: data.urgency_level || 'normal',
      fundManager: data.fund_manager || '',
      fundUsagePlan: data.fund_usage_plan || 'one_time',
      payerAccountName: data.payer_account_name || '',
      payerAccountNumber: data.payer_account_number || '',
      payerBank: data.payer_bank || '',
      payerHandler: data.payer_handler || '',
      payerContact: data.payer_contact || '',
      payeeAccountName: data.payee_account_name || '',
      payeeAccountNumber: data.payee_account_number || '',
      payeeBank: data.payee_bank || '',
      payeeHandler: data.payee_handler || '',
      payeeContact: data.payee_contact || '',
      isDelayed: !!data.is_delayed,
      delayReason: data.delay_reason || '',
      description: data.description || '',
      expectedBenefits: data.expected_benefits || '',
      achievements: data.achievements || '',
      tags: data.tags ? String(data.tags).split(',').filter(Boolean) : [],
      remarks: data.remarks || '',
      createTime: data.created_at || '',
      updateTime: data.updated_at || '',
    })

    // 加载已上传的附件列表
    await loadProjectFiles(projectId)
  } catch (error) {
    logger.error('加载项目数据失败:', error)
    ElMessage.error(getErrorMessage(error, '数据加载失败，请稍后重试'))
    pushSafe('/projects')
  } finally {
    loading.value = false
  }
}

// 生成项目编号
function generateProjectId(): string {
  const timestamp = Date.now().toString().slice(-6)
  const random = Math.floor(Math.random() * 1000)
    .toString()
    .padStart(3, '0')
  return `PRO${timestamp}${random}`
}

// 保存项目数据
async function saveProjectData(): Promise<number | string | false> {
  loading.value = true
  let projectId: number | string

  try {
    // 所有字段的公共payload
    const commonPayload: any = {
      name: projectForm.name,
      type: projectForm.projectType,
      description: projectForm.description,
      budget: projectForm.fundAmount,
      start_date: projectForm.startDate || undefined,
      end_date: projectForm.endDate || undefined,
      status: projectForm.status,
      responsible_person: projectForm.responsiblePerson,
      contact_phone: projectForm.contactPhone,
      urgency_level: projectForm.urgencyLevel,
      contract_number: projectForm.contractNumber || undefined,
      fund_manager: projectForm.fundManager || undefined,
      fund_usage_plan: projectForm.fundUsagePlan,
      fund_source: projectForm.fundSource || undefined,
      payer_account_name: projectForm.payerAccountName || undefined,
      payer_account_number: projectForm.payerAccountNumber || undefined,
      payer_bank: projectForm.payerBank || undefined,
      payer_handler: projectForm.payerHandler || undefined,
      payer_contact: projectForm.payerContact || undefined,
      payee_account_name: projectForm.payeeAccountName || undefined,
      payee_account_number: projectForm.payeeAccountNumber || undefined,
      payee_bank: projectForm.payeeBank || undefined,
      payee_handler: projectForm.payeeHandler || undefined,
      payee_contact: projectForm.payeeContact || undefined,
      is_delayed: projectForm.isDelayed,
      delay_reason: projectForm.isDelayed ? projectForm.delayReason : undefined,
      expected_benefits: projectForm.expectedBenefits || undefined,
      achievements: projectForm.achievements || undefined,
      tags: projectForm.tags.length > 0 ? projectForm.tags.join(',') : undefined,
      remarks: projectForm.remarks || undefined,
    }

    if (isEditMode.value) {
      // 编辑模式 - 调用更新 API
      const rawId = route.params.id as string
      projectId = isNaN(Number(rawId)) ? rawId : Number(rawId)
      await projectApi.update(projectId, {
        ...commonPayload,
        village_id: projectForm.villageId ? Number(projectForm.villageId) : undefined,
        progress: projectForm.completionRate,
      })
    } else {
      // 新建模式 - 调用创建 API
      const code = generateProjectId()
      const result = await projectApi.create({
        ...commonPayload,
        code: code,
        village_id: projectForm.villageId ? Number(projectForm.villageId) : undefined,
        // 新建同样提交进度（此前仅编辑提交，且后端创建模型缺该字段 → 进度始终为0）
        progress: projectForm.completionRate,
      })
      projectId = (result as any)?.id || (result as any)?.data?.id
      if (!projectId) {
        logger.warn('创建项目后未获取到项目ID，跳过附件上传')
        return false
      }
    }

    // 上传所有待上传附件
    const hasPending = Object.values(pendingFiles).some((arr) => arr.length > 0)
    if (hasPending && projectId) {
      const uploaded = await uploadAllPendingFiles(projectId)
      if (uploaded > 0) {
        ElMessage.success(`已成功上传 ${uploaded} 个附件`)
      }
    }
  } catch (error) {
    logger.error('保存项目数据失败:', error)
    saveErrorMessage.value = getErrorMessage(error, '保存失败，请稍后重试')
    return false
  } finally {
    loading.value = false
  }

  return projectId
}

// 处理保存
async function handleSave(_formName: string) {
  if (!projectFormRef.value) return

  const formInstance = projectFormRef.value!

  await formInstance.validate(async (valid: boolean) => {
    if (!valid) {
      ElMessage.warning('请完善必填信息')
      return
    }

    const result = await saveProjectData()
    if (result !== false) {
      ElMessage.success(isEditMode.value ? '项目更新成功' : '项目创建成功')
      pushSafe('/projects')
    } else {
      ElMessage.error(saveErrorMessage.value || '保存失败，请稍后重试')
      saveErrorMessage.value = ''
    }
  })
}

// 处理保存并继续创建
async function handleSaveAndContinue() {
  if (!projectFormRef.value) return

  const formInstance = projectFormRef.value as any

  await formInstance.validate(async (valid: boolean) => {
    if (!valid) {
      ElMessage.warning('请完善必填信息')
      return
    }

    const result = await saveProjectData()
    if (result !== false) {
      ElMessage.success('项目创建成功')

      // 重置表单
      resetForm()

      // 滚动到页面顶部
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      ElMessage.error(saveErrorMessage.value || '保存失败，请稍后重试')
      saveErrorMessage.value = ''
    }
  })
}

// 重置表单
function resetForm() {
  if (projectFormRef.value) {
    projectFormRef.value.resetFields()
  }

  Object.keys(projectForm).forEach((key) => {
    const formKey = key as keyof typeof projectForm
    if (
      formKey === 'status' ||
      formKey === 'fundSource' ||
      formKey === 'urgencyLevel' ||
      formKey === 'fundUsagePlan'
    ) {
      projectForm[formKey] =
        formKey === 'status'
          ? 'draft'
          : formKey === 'fundSource'
            ? 'financial'
            : formKey === 'urgencyLevel'
              ? 'normal'
              : 'one_time'
    } else if (formKey === 'tags') {
      projectForm[formKey] = []
    } else if (formKey === 'isDelayed') {
      projectForm[formKey] = false
    } else if (typeof projectForm[formKey] === 'number') {
      // 直接使用any类型断言来避免类型错误
      ;(projectForm as any)[formKey] = 0
    } else {
      // 直接使用any类型断言来避免类型错误
      ;(projectForm as any)[formKey] = ''
    }
  })

  fileList.value = []
}

// 处理取消
function handleCancel() {
  ElMessageBox.confirm('当前页面有未保存的内容，确定要离开吗？', '确认离开', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(() => {
      pushSafe('/projects')
    })
    .catch(() => {
      // 取消操作，留在当前页面
    })
}

// 组件挂载
onMounted(async () => {
  // 先加载帮扶村下拉选项
  await loadVillageOptions()
  if (isEditMode.value) {
    await loadProjectData()
  }
})

// 组件卸载时清理 blob URL
onUnmounted(() => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  // 清理所有缩略图 Blob URL
  revokeAllThumbnails()
})
</script>

<style scoped lang="scss">
.project-edit-container {
  min-height: 100vh;
  padding: 20px;
  background-color: var(--color-bg-hover);
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: bold;
  color: var(--color-navy);
  margin: 12px 0 0 0;
}

.form-card {
  margin-bottom: 20px;
}

.project-form {
  padding: 20px 0;
}

.form-row {
  display: flex;
  flex-wrap: wrap;
  margin-bottom: 20px;
  gap: 20px;
}

.form-row:last-child {
  margin-bottom: 0;
}

.el-form-item {
  flex: 1;
  min-width: 300px;
  margin-bottom: 0;
}

.el-form-item--large .el-form-item__label {
  font-size: 14px;
  font-weight: 500;
}

.el-form-item__content {
  min-width: 0;
}

.input-suffix {
  margin-left: 8px;
  color: var(--color-text-regular);
}

.upload-demo {
  width: 100%;
}

.upload-demo .el-upload-dragger {
  width: 100%;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 30px;
  justify-content: center;
  padding: 20px 0;
  border-top: 1px solid var(--color-border-light);
}

.form-actions .el-button {
  padding: 12px 24px;
  font-size: 16px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .form-row {
    flex-direction: column;
    gap: 16px;
  }

  .el-form-item {
    min-width: 100%;
  }
}

@media (max-width: 768px) {
  .project-edit-container {
    padding: 12px;
  }

  .form-card {
    padding: 16px;
  }

  .project-form {
    padding: 16px 0;
  }

  .el-form-item {
    min-width: 100%;
  }

  .form-actions {
    flex-direction: column;
  }

  .form-actions .el-button {
    width: 100%;
  }
}

/* 自定义样式增强 */
.el-divider--horizontal {
  margin: 30px 0 20px 0;
}

.el-divider__text {
  font-size: 16px;
  font-weight: bold;
  color: var(--color-navy);
  background-color: var(--color-bg-hover);
  padding: 0 20px;
}

.el-select,
.el-input,
.el-date-editor {
  width: 100%;
}
/* 数字输入框（完成率/金额等）定宽，避免被 flex 拉伸过长 */
.el-input-number {
  width: 160px;
}

.el-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.el-checkbox {
  margin-right: 0;
}

.el-switch {
  --el-switch-on-color: var(--color-primary);
  --el-switch-off-color: #dcdfe6;
  --el-switch-on-text-color: var(--color-text-inverse);
  --el-switch-off-text-color: var(--color-text-inverse);
  --el-switch-core-height: 32px;
  --el-switch-button-size: 28px;
}

.el-upload-list {
  margin-top: 12px;
}

/* 加载状态 */
:deep(.el-form-item__error) {
  margin-top: 4px;
  font-size: 12px;
}

/* 动画效果 */
.el-button,
.el-select,
.el-input,
.el-date-editor,
.el-input-number,
.el-upload-dragger {
  transition: all 0.3s ease;
}

.el-button:hover,
.el-select:hover,
.el-input:hover,
.el-date-editor:hover,
.el-input-number:hover,
.el-upload-dragger:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
</style>
