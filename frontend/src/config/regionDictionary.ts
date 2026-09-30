/**
 * 区域字典配置
 */
export const PROVINCES = [
  { label: '北京市', value: '110000' },
  { label: '天津市', value: '120000' },
  { label: '河北省', value: '130000' },
  { label: '山西省', value: '140000' },
  { label: '内蒙古自治区', value: '150000' },
  { label: '辽宁省', value: '210000' },
  { label: '吉林省', value: '220000' },
  { label: '黑龙江省', value: '230000' },
  { label: '上海市', value: '310000' },
  { label: '江苏省', value: '320000' },
  { label: '浙江省', value: '330000' },
  { label: '安徽省', value: '340000' },
  { label: '福建省', value: '350000' },
  { label: '江西省', value: '360000' },
  { label: '山东省', value: '370000' },
  { label: '河南省', value: '410000' },
  { label: '湖北省', value: '420000' },
  { label: '湖南省', value: '430000' },
  { label: '广东省', value: '440000' },
  { label: '广西壮族自治区', value: '450000' },
  { label: '海南省', value: '460000' },
  { label: '重庆市', value: '500000' },
  { label: '四川省', value: '510000' },
  { label: '贵州省', value: '520000' },
  { label: '云南省', value: '530000' },
  { label: '西藏自治区', value: '540000' },
  { label: '陕西省', value: '610000' },
  { label: '甘肃省', value: '620000' },
  { label: '青海省', value: '630000' },
  { label: '宁夏回族自治区', value: '640000' },
  { label: '新疆维吾尔自治区', value: '650000' },
]

export const HELP_TYPES = [
  { label: '产业帮扶', value: 'industry' },
  { label: '教育帮扶', value: 'education' },
  { label: '医疗帮扶', value: 'medical' },
  { label: '基础设施', value: 'infrastructure' },
  { label: '党建帮扶', value: 'party_building' },
  { label: '消费帮扶', value: 'consumption' },
  { label: '就业帮扶', value: 'employment' },
  { label: '其他', value: 'other' },
]

export const INDUSTRY_PROJECT_TYPES = [
  { label: '种植业', value: 'planting' },
  { label: '养殖业', value: 'breeding' },
  { label: '加工业', value: 'processing' },
  { label: '旅游业', value: 'tourism' },
  { label: '电子商务', value: 'ecommerce' },
  { label: '其他', value: 'other' },
]

export const INFRASTRUCTURE_PROJECT_TYPES = [
  { label: '道路建设', value: 'road' },
  { label: '水利设施', value: 'water' },
  { label: '电力设施', value: 'power' },
  { label: '通讯设施', value: 'communication' },
  { label: '文化设施', value: 'culture' },
  { label: '体育设施', value: 'sports' },
  { label: '其他', value: 'other' },
]

export const PARTY_BUILDING_ACTIVITY_TYPES = [
  { label: '主题党日', value: 'theme_day' },
  { label: '组织生活会', value: 'org_meeting' },
  { label: '党课教育', value: 'party_lesson' },
  { label: '志愿服务', value: 'volunteer' },
  { label: '其他', value: 'other' },
]

export const MEDICAL_ACTIVITY_TYPES = [
  { label: '义诊', value: 'clinic' },
  { label: '健康讲座', value: 'health_lecture' },
  { label: '医疗培训', value: 'medical_training' },
  { label: '药品捐赠', value: 'medicine_donation' },
  { label: '其他', value: 'other' },
]

export const EDUCATION_ACTIVITY_TYPES = [
  { label: '支教', value: 'teaching' },
  { label: '捐资助学', value: 'scholarship' },
  { label: '学校建设', value: 'school_construction' },
  { label: '教学设备', value: 'teaching_equipment' },
  { label: '其他', value: 'other' },
]

/**
 * 区域属性判定结果。
 *
 * 只包含**确有判定依据**的字段：province（行政区划代码 → 中文标签）。
 * 三区三州 / 边疆地区 / 民族地区 / 革命老区 / 重点帮扶县 等标记没有可离线核定的
 * 权威数据源（本文件只有省市县名称字典），因此**一律不返回**——历史实现回填
 * false 会被调用方写回表单，静默清空用户手工填写或后端回填的真实标记。
 */
export interface RegionAttributes {
  /** 省份中文标签（由行政区划代码或标签本身解析；无法解析时为空串） */
  province: string
}

export function detectRegionAttributes(
  province?: string,
  _city?: string,
  _county?: string
): RegionAttributes {
  // 兼容旧版三参数调用：市/县级属性无权威字典可查，仅从省份值反查标签
  const provinceObj = PROVINCES.find((p) => p.value === province || p.label === province)
  return { province: provinceObj?.label || province || '' }
}
