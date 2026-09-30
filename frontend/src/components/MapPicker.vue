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
import { ElMessage } from 'element-plus'
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

/**
 * 输入框内的坐标。
 *
 * 类型含 string/'' 的原因：el-input **不消费** `v-model.number` 的 modelModifiers
 * （修饰符只对原生元素生效），用户清空得 ''、输入非数字得字符串。
 * 因此内部按"可能是脏值"处理，仅在 onInputChange 校验通过后才转成 number 外发。
 */
const innerLng = ref<number | string>(props.modelValue?.lng ?? props.longitude ?? 107.52)
const innerLat = ref<number | string>(props.modelValue?.lat ?? props.latitude ?? 26.26)
const dialogVisible = ref(false)
const pickedLng = ref<number | null>(null)
const pickedLat = ref<number | null>(null)
const pickerMapRef = ref<InstanceType<typeof OfflineMap> | null>(null)

/** 归一化外部坐标：非有限数字（null/undefined/NaN）→ 空串（清空输入） */
function normalizeCoord(val: number | null | undefined): number | '' {
  return typeof val === 'number' && Number.isFinite(val) ? val : ''
}

/** 脏值（''、字符串、NaN）→ null；否则返回有限数字 */
function toFiniteNumber(raw: number | string): number | null {
  if (raw === '' || raw === null || raw === undefined) return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

/** 经纬度范围校验（fail-closed：非法值不外发） */
function inRange(v: number | null, min: number, max: number): boolean {
  return v !== null && v >= min && v <= max
}

watch(
  () => props.modelValue,
  (val) => {
    if (val && Number.isFinite(val.lng) && Number.isFinite(val.lat)) {
      innerLng.value = val.lng
      innerLat.value = val.lat
      return
    }
    // 父组件清空（null/undefined/脏值）→ 内部坐标必须同步清空，
    // 否则输入框仍显示上一个对象的坐标，且下一次 change 会把旧坐标原样发回。
    innerLng.value = ''
    innerLat.value = ''
  }
)
watch(
  () => props.latitude,
  (val) => {
    innerLat.value = normalizeCoord(val)
  }
)
watch(
  () => props.longitude,
  (val) => {
    innerLng.value = normalizeCoord(val)
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
  const lng = toFiniteNumber(innerLng.value)
  const lat = toFiniteNumber(innerLat.value)
  // 非法/超范围坐标一律不外发（父组件按 number 消费，脏值会变成 NaN 或越界坐标入库）
  if (!inRange(lng, -180, 180) || !inRange(lat, -90, 90)) {
    ElMessage.warning('经纬度格式不正确：经度 -180~180，纬度 -90~90')
    return
  }
  // toFiniteNumber 返回 number | null；inRange 通过后已保证非空，
  // 但 TS 无法跨函数收窄，故在赋值/外发前显式断言为非空。
  if (lng == null || lat == null) return
  innerLng.value = lng
  innerLat.value = lat
  emit('update:modelValue', { lng, lat })
  emit('update:latitude', lat)
  emit('update:longitude', lng)
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
  const lng = pickedLng.value
  const lat = pickedLat.value
  // 地图点击坐标同样要过有限性校验（convertFromPixel 在极端视图下可能给出 NaN）
  if (lng === null || lat === null || !Number.isFinite(lng) || !Number.isFinite(lat)) return
  innerLng.value = lng
  innerLat.value = lat
  onInputChange()
  dialogVisible.value = false
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
