<template>
  <div class="map-picker">
    <div class="picker-inputs">
      <el-row :gutter="12">
        <el-col :span="10">
          <el-input
            v-model.number="innerLng"
            placeholder="经度 (如 107.52)"
            :disabled="disabled"
            @change="onInputChange"
          >
            <template #prepend>经度</template>
          </el-input>
        </el-col>
        <el-col :span="10">
          <el-input
            v-model.number="innerLat"
            placeholder="纬度 (如 26.26)"
            :disabled="disabled"
            @change="onInputChange"
          >
            <template #prepend>纬度</template>
          </el-input>
        </el-col>
        <el-col :span="4">
          <el-button :icon="Location" :disabled="disabled" @click="pickFromMap">选取</el-button>
        </el-col>
      </el-row>
    </div>
    <el-dialog
      v-model="dialogVisible"
      append-to-body
      title="在地图上选取坐标 — 点击地图即可选点"
      width="850px"
      destroy-on-close
      @opened="onDialogOpened"
    >
      <OfflineMap
        ref="pickerMapRef"
        height="480px"
        :markers="mapMarkers"
        @marker-click="onMapClick"
        @region-click="onMapClick"
      />
      <div v-if="pickedLng != null" class="picked-info">
        <el-tag type="warning" size="large"
          >已选坐标: {{ pickedLng.toFixed(6) }}, {{ pickedLat!.toFixed(6) }}</el-tag
        >
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="pickedLng == null" @click="confirmPick"
          >确认选择</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue'
import { Location } from '@element-plus/icons-vue'
import OfflineMap from '@/components/map/OfflineMap.vue'

const props = defineProps<{
  modelValue?: { lng: number; lat: number }
  latitude?: number | null
  longitude?: number | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: { lng: number; lat: number }): void
  (e: 'update:latitude', val: number | null): void
  (e: 'update:longitude', val: number | null): void
}>()

const innerLng = ref(props.modelValue?.lng ?? props.longitude ?? 107.52)
const innerLat = ref(props.modelValue?.lat ?? props.latitude ?? 26.26)
const dialogVisible = ref(false)
const pickedLng = ref<number | null>(null)
const pickedLat = ref<number | null>(null)
const pickerMapRef = ref<InstanceType<typeof OfflineMap> | null>(null)

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      innerLng.value = val.lng
      innerLat.value = val.lat
    }
  }
)
watch(
  () => props.latitude,
  (val) => {
    if (val !== undefined && val !== null) innerLat.value = val
  }
)
watch(
  () => props.longitude,
  (val) => {
    if (val !== undefined && val !== null) innerLng.value = val
  }
)

// 地图上的已选坐标标记（仅用户点击地图后才显示）
const mapMarkers = computed(() => {
  if (pickedLng.value == null || pickedLat.value == null) {
    return []
  }
  return [
    {
      lng: pickedLng.value,
      lat: pickedLat.value,
      name: '',
      type: 'default',
    },
  ]
})

function onInputChange() {
  emit('update:modelValue', { lng: innerLng.value, lat: innerLat.value })
  emit('update:latitude', innerLat.value)
  emit('update:longitude', innerLng.value)
}

function pickFromMap() {
  pickedLng.value = null
  pickedLat.value = null
  dialogVisible.value = true
}

function onDialogOpened() {
  // 对话框打开后，ECharts 需要 resize 以正确渲染
  nextTick(() => {
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'))
    }, 200)
  })
}

// 点击地图任意位置 → 选中坐标
function onMapClick(marker: { name?: string; lng?: number | null; lat?: number | null }) {
  if (marker.lng != null && marker.lat != null) {
    pickedLng.value = marker.lng
    pickedLat.value = marker.lat
  }
}

function confirmPick() {
  if (pickedLng.value !== null && pickedLat.value !== null) {
    innerLng.value = pickedLng.value
    innerLat.value = pickedLat.value
    onInputChange()
    dialogVisible.value = false
  }
}
</script>

<style scoped>
.map-picker {
  width: 100%;
}
.picker-inputs {
  margin-bottom: 8px;
}
.picked-info {
  text-align: center;
  margin-top: 10px;
}
</style>
