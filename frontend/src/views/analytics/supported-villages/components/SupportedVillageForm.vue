<template>
  <!-- 单根包裹（display:contents）：避免 transition 内多根导致 setAttribute('0') 崩溃 -->
  <div style="display: contents">
    <el-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      :disabled="mode === 'view'"
      label-width="120px"
    >
      <!-- 基本信息 -->
      <el-divider content-position="left">基本信息</el-divider>
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="序号" prop="sequenceNo">
            <el-input-number v-model="formData.sequenceNo" :min="1" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="部门单位" prop="department">
            <el-input v-model="formData.department" placeholder="请输入部门单位" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="帮扶单位" prop="supportUnit">
            <el-input v-model="formData.supportUnit" placeholder="请输入帮扶单位" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="帮扶村名称" prop="villageName">
            <el-input v-model="formData.villageName" placeholder="请输入帮扶村名称" />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 地域属性 - 贵州省地区选择 -->
      <el-divider content-position="left">地域属性</el-divider>
      <el-row :gutter="20">
        <el-col :span="24">
          <el-form-item label="所在地区">
            <GuizhouRegionSelector
              v-model="regionValue"
              :disabled="mode === 'view'"
              :show-township="true"
            />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="地区范围" prop="regionScope">
            <el-input v-model="formData.regionScope" placeholder="请输入地区范围" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-form-item label="三区三州">
            <el-switch v-model="formData.isThreeRegions" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="边疆地区">
            <el-switch v-model="formData.isBorderArea" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="民族地区">
            <el-switch v-model="formData.isEthnicArea" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-form-item label="革命地区">
            <el-switch v-model="formData.isRevolutionaryArea" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="重点帮扶县">
            <el-switch v-model="formData.isKeyCounty" />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 振兴发展属性 -->
      <el-divider content-position="left">振兴发展属性</el-divider>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-form-item label="振兴梯队">
            <el-switch v-model="formData.isRevitalizationTier" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="省级示范">
            <el-switch v-model="formData.isProvincialDemo" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="百村示范">
            <el-switch v-model="formData.isHundredVillageDemo" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-form-item label="梯次振兴">
            <el-switch v-model="formData.isTieredDevelopment" />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 跨域帮扶 -->
      <el-divider content-position="left">跨域帮扶</el-divider>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-form-item label="跨省帮扶">
            <el-switch v-model="formData.isCrossProvince" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="跨市帮扶">
            <el-switch v-model="formData.isCrossCity" />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 协作与表彰 -->
      <el-divider content-position="left">协作与表彰</el-divider>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-form-item label="跨单位协作">
            <el-switch v-model="formData.isCrossUnitCooperation" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="纳入总盘子">
            <el-switch v-model="formData.isInOverallPlan" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row>
        <el-col :span="24">
          <el-form-item label="获得表彰" prop="honors">
            <el-input
              v-model="formData.honors"
              type="textarea"
              :rows="3"
              placeholder="请输入获得的国家或省级表彰"
            />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <!-- 地理位置（独立区域）-->
    <el-divider content-position="left">地理位置</el-divider>
    <el-row style="margin-bottom: 16px">
      <el-col :span="24">
        <label class="funding-label">坐标设置</label>
        <MapPicker
          v-model:latitude="formData.latitude"
          v-model:longitude="formData.longitude"
          :disabled="mode === 'view'"
        />
      </el-col>
    </el-row>

    <!-- 帮扶经费（独立区域，不受 form disabled 影响）-->
    <el-divider content-position="left">帮扶经费</el-divider>
    <div class="funding-section" :class="{ 'funding-section--disabled': mode === 'view' }">
      <!-- 单行紧凑布局：选择年度 + 专项投入 + 地方投入 + 按钮 -->
      <el-row :gutter="12" style="margin-bottom: 16px" align="bottom">
        <el-col :span="5">
          <label class="funding-label">选择年度</label>
          <el-select
            v-model="selectedFundingYear"
            placeholder="年度"
            style="width: 100%"
            filterable
            allow-create
            teleported
            :popper-options="{ strategy: 'fixed' }"
            :disabled="mode === 'view'"
            @change="onFundingYearChange"
          >
            <el-option v-for="y in availableFundingYears" :key="y" :label="`${y}年`" :value="y" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <label class="funding-label">专项投入（万元）</label>
          <el-input-number
            v-model="currentMilitaryInput"
            :min="0"
            :precision="2"
            :controls="true"
            controls-position="right"
            style="width: 100%"
            placeholder="专项投入"
            :disabled="mode === 'view'"
          />
        </el-col>
        <el-col :span="6">
          <label class="funding-label">地方投入（万元）</label>
          <el-input-number
            v-model="currentLocalInput"
            :min="0"
            :precision="2"
            :controls="true"
            controls-position="right"
            style="width: 100%"
            placeholder="地方投入"
            :disabled="mode === 'view'"
          />
        </el-col>
        <el-col :span="7">
          <el-button v-if="mode !== 'view'" type="primary" @click="addOrUpdateFunding">
            {{ hasFundingYear(selectedFundingYear) ? '更新' : '添加' }}
          </el-button>
          <el-popconfirm
            v-if="hasFundingYear(selectedFundingYear) && mode !== 'view'"
            title="确定删除该年度经费？"
            width="180"
            @confirm="removeFundingByYear(selectedFundingYear)"
          >
            <template #reference>
              <el-button type="danger" plain>删除</el-button>
            </template>
          </el-popconfirm>
        </el-col>
      </el-row>

      <!-- 年度汇总表 -->
      <el-table
        v-if="transitionFundingRows.length > 0"
        :data="transitionFundingRows"
        border
        stripe
        size="small"
        style="margin-bottom: 16px"
      >
        <el-table-column label="年度" width="90" align="center">
          <template #default="{ row }">{{ row.year }}年</template>
        </el-table-column>
        <el-table-column label="专项投入（万元）" align="right">
          <template #default="{ row }">
            <span class="funding-number">{{ (row.militaryInvestment || 0).toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="地方投入（万元）" align="right">
          <template #default="{ row }">
            <span class="funding-number">{{ (row.localInvestment || 0).toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="年度合计（万元）" width="150" align="right">
          <template #default="{ row }">
            <span class="funding-number funding-number--total">
              {{ ((row.militaryInvestment || 0) + (row.localInvestment || 0)).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column v-if="mode !== 'view'" label="操作" width="130" align="center">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="editFundingYear(row.year)"
              >编辑</el-button
            >
            <el-popconfirm
              title="确定删除该年度经费？"
              width="180"
              @confirm="removeFundingByYear(row.year)"
            >
              <template #reference>
                <el-button type="danger" size="small" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else
        description="暂无帮扶经费数据，请选择年度添加"
        :image-size="60"
        style="margin-bottom: 16px"
      />

      <!-- 合计行 -->
      <el-descriptions v-if="transitionFundingRows.length > 0" :column="2" border size="small">
        <el-descriptions-item label="专项合计（万元）" align="right">
          <strong>{{ transitionMilitaryTotal.toFixed(2) }}</strong>
        </el-descriptions-item>
        <el-descriptions-item label="地方合计（万元）" align="right">
          <strong>{{ transitionLocalTotal.toFixed(2) }}</strong>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 保存/取消 — 页面最底部 -->
    <div class="form-actions" style="margin-top: 24px">
      <template v-if="mode !== 'view'">
        <el-button type="primary" @click="handleSubmit">保存</el-button>
        <el-button @click="handleCancel">取消</el-button>
      </template>
      <template v-else>
        <el-button @click="handleCancel">关闭</el-button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { logger } from '@/utils/logger'
import { getYearOptions } from '@/utils/yearOptions'

/**
 * 帮扶村表单组件
 *
 * Feature: supported-village-enhancement
 * Requirements: 1.3, 23.1, 16.1, 16.2, 16.3
 */
import { ref, reactive, watch, computed, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { SupportedVillage, SupportedVillageCreate } from '@/types/analytics'
import GuizhouRegionSelector from '@/components/common/GuizhouRegionSelector.vue'
import type { RegionValue } from '@/components/common/GuizhouRegionSelector.vue'
import MapPicker from '@/components/MapPicker.vue'
import { DEFAULT_PROVINCE } from '@/data/guizhouRegion'
import { getTransitionFunding, saveTransitionFunding } from '@/api/supportedVillage'

const props = defineProps<{
  village?: SupportedVillage | null
  mode: 'create' | 'edit' | 'view'
}>()

const emit = defineEmits<{
  submit: [data: SupportedVillageCreate]
  cancel: []
}>()

const formRef = ref<FormInstance>()

const formData = reactive<SupportedVillageCreate>({
  sequenceNo: undefined,
  department: '',
  supportUnit: '',
  villageName: '',
  // 地域属性 - 贵州省地区选择
  province: DEFAULT_PROVINCE,
  city: '',
  county: '',
  township: '',
  regionScope: '',
  isThreeRegions: 0,
  isBorderArea: 0,
  isEthnicArea: 0,
  isRevolutionaryArea: 0,
  isKeyCounty: 0,
  isRevitalizationTier: false,
  isProvincialDemo: 0,
  isHundredVillageDemo: 0,
  isTieredDevelopment: false,
  isCrossProvince: false,
  isCrossCity: false,
  isCrossUnitCooperation: false,
  isInOverallPlan: false,
  honors: '',
  transitionFundMilitaryTotal: 0,
  transitionFundLocalTotal: 0,
  latitude: null,
  longitude: null,
})

const rules: FormRules = {
  department: [{ required: true, message: '请输入部门单位', trigger: 'blur' }],
  supportUnit: [{ required: true, message: '请输入帮扶单位', trigger: 'blur' }],
  villageName: [{ required: true, message: '请输入帮扶村名称', trigger: 'blur' }],
}

// 帮扶经费按年度数据
const transitionFundingRows = ref<
  Array<{
    year: number
    militaryInvestment: number
    localInvestment: number
  }>
>([])

const transitionMilitaryTotal = computed(() =>
  transitionFundingRows.value.reduce((s, r) => s + (r.militaryInvestment || 0), 0)
)
const transitionLocalTotal = computed(() =>
  transitionFundingRows.value.reduce((s, r) => s + (r.localInvestment || 0), 0)
)

// 可选年度范围：2021 ~ 当前年份+10（滚动窗口，见 utils/yearOptions）
const availableFundingYears = computed(() => getYearOptions({ start: 2021, descending: false }))

const selectedFundingYear = ref(new Date().getFullYear())
const currentMilitaryInput = ref(0)
const currentLocalInput = ref(0)

function hasFundingYear(year: number) {
  return transitionFundingRows.value.some((r) => r.year === year)
}

function onFundingYearChange(year: number) {
  const existing = transitionFundingRows.value.find((r) => r.year === year)
  if (existing) {
    currentMilitaryInput.value = existing.militaryInvestment
    currentLocalInput.value = existing.localInvestment
  } else {
    currentMilitaryInput.value = 0
    currentLocalInput.value = 0
  }
}

function validateFundingYear(): number | null {
  const year = Number(selectedFundingYear.value)
  if (isNaN(year) || !Number.isInteger(year) || year < 2000) {
    ElMessage.warning('请输入有效年度（如 2024）')
    return null
  }
  return year
}

function upsertFundingRow(year: number) {
  const existing = transitionFundingRows.value.find((r) => r.year === year)
  if (existing) {
    existing.militaryInvestment = currentMilitaryInput.value
    existing.localInvestment = currentLocalInput.value
  } else {
    transitionFundingRows.value.push({
      year,
      militaryInvestment: currentMilitaryInput.value,
      localInvestment: currentLocalInput.value,
    })
    transitionFundingRows.value.sort((a, b) => a.year - b.year)
  }
}

function advanceToNextYear(year: number) {
  const nextYear = year + 1
  if (availableFundingYears.value.includes(nextYear)) {
    selectedFundingYear.value = nextYear
  }
  onFundingYearChange(selectedFundingYear.value)
}

function addOrUpdateFunding() {
  const year = validateFundingYear()
  if (year === null) return
  upsertFundingRow(year)
  advanceToNextYear(year)
}

function removeFundingByYear(year: number) {
  const isSelected = selectedFundingYear.value === year
  const idx = transitionFundingRows.value.findIndex((r) => r.year === year)
  if (idx >= 0) {
    transitionFundingRows.value.splice(idx, 1)
  }
  // 仅当删除的年度是当前选中年度时才重置输入
  if (isSelected) {
    currentMilitaryInput.value = 0
    currentLocalInput.value = 0
  }
}

function editFundingYear(year: number) {
  selectedFundingYear.value = year
  onFundingYearChange(year)
}

async function loadTransitionFunding() {
  if (!props.village?.id) return
  try {
    const resp = await getTransitionFunding(props.village.id)
    const items = (resp as any)?.data || resp || []
    transitionFundingRows.value = items
      .map((item: any) => ({
        year: item.year,
        militaryInvestment: Number(item.militaryInvestment || 0),
        localInvestment: Number(item.localInvestment || 0),
      }))
      .sort((a: { year: number }, b: { year: number }) => a.year - b.year)
  } catch {
    /* 无数据时保持默认值 */
  }
}

/** 区域值双向绑定：flat formData ↔ RegionValue 对象 */
const regionValue = computed<RegionValue>({
  get: () => ({
    city: formData.city || undefined,
    county: formData.county || undefined,
    township: formData.township || undefined,
  }),
  set: (val: RegionValue) => {
    formData.city = val.city || ''
    formData.county = val.county || ''
    formData.township = val.township || ''
  },
})

// 监听 village 变化，填充表单
watch(
  () => props.village,
  (village) => {
    if (village) {
      Object.assign(formData, {
        sequenceNo: village.sequenceNo,
        department: village.department,
        supportUnit: village.supportUnit,
        villageName: village.villageName,
        // 地域属性
        province: village.province || DEFAULT_PROVINCE,
        city: village.city || '',
        county: village.county || '',
        township: village.township || '',
        regionScope: village.regionScope || '',
        // 布尔字段强制转换，确保正确显示
        isThreeRegions: Boolean(village.isThreeRegions),
        isBorderArea: Boolean(village.isBorderArea),
        isEthnicArea: Boolean(village.isEthnicArea),
        isRevolutionaryArea: Boolean(village.isRevolutionaryArea),
        isKeyCounty: Boolean(village.isKeyCounty),
        isRevitalizationTier: Boolean(village.isRevitalizationTier),
        isProvincialDemo: Boolean(village.isProvincialDemo),
        isHundredVillageDemo: Boolean(village.isHundredVillageDemo),
        isTieredDevelopment: Boolean(village.isTieredDevelopment),
        isCrossProvince: Boolean(village.isCrossProvince),
        isCrossCity: Boolean(village.isCrossCity),
        isCrossUnitCooperation: Boolean(village.isCrossUnitCooperation),
        isInOverallPlan: Boolean(village.isInOverallPlan),
        honors: village.honors || '',
        transitionFundMilitaryTotal: (village as any).transitionFundMilitaryTotal || 0,
        transitionFundLocalTotal: (village as any).transitionFundLocalTotal || 0,
        latitude: village.latitude ?? null,
        longitude: village.longitude ?? null,
      })

      // 加载过渡期经费按年度数据
      if (village.id) {
        loadTransitionFunding()
      }
    }
  },
  { immediate: true }
)

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
    // 同步更新总额字段
    formData.transitionFundMilitaryTotal = transitionMilitaryTotal.value
    formData.transitionFundLocalTotal = transitionLocalTotal.value

    // 构建过渡期经费按年度数据
    const fundingItems = transitionFundingRows.value.map((r) => ({
      year: r.year,
      militaryInvestment: r.militaryInvestment || 0,
      localInvestment: r.localInvestment || 0,
      totalInvestment: (r.militaryInvestment || 0) + (r.localInvestment || 0),
    }))

    // 编辑模式：先保存年度经费，再提交表单更新
    if (props.village?.id) {
      try {
        await saveTransitionFunding(props.village.id, { items: fundingItems })
      } catch (err: any) {
        logger.error('[SupportedVillageForm] 保存过渡资金失败', err)
        ElMessage.error(err?.response?.data?.detail || '过渡资金保存失败，请重试')
        return // 年度经费保存失败 → 阻止提交
      }
    }

    // 创建模式：将年度经费数据一并传递给父组件
    // 父组件 Detail.vue 在创建村记录后负责调用 saveTransitionFunding
    emit('submit', {
      ...formData,
      ...(props.mode === 'create' ? { _transitionFundingItems: fundingItems } : {}),
    })
  } catch (error) {
    logger.error('表单验证失败:', error)
  }
}

onMounted(() => {
  // 过渡期经费数据加载已移至 watch 中，确保 village 变化时自动加载
})

function handleCancel() {
  emit('cancel')
}
</script>

<style scoped lang="scss">
.form-actions {
  margin-top: 24px;
  text-align: right;
}

// 帮扶经费独立区域
.funding-section {
  padding: 0 4px;

  &--disabled {
    opacity: 0.85;
  }
}

.funding-label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #606266;
  line-height: 1.4;
}

.funding-number {
  font-variant-numeric: tabular-nums;
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;

  &--total {
    font-weight: 700;
    color: #1b4332;
  }
}
</style>
