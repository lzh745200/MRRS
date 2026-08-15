/**
 * 数据分析与帮扶村管理类型定义
 * Feature: data-analytics-enhancement
 * Requirements: 8.1-17.5, 19.1-19.6
 */

// ==================== 帮扶村基础类型 ====================

/**
 * 帮扶村实体
 */
export interface SupportedVillage {
  id: number
  sequenceNo?: number
  department: string
  supportUnit: string
  villageName: string
  villageId?: number

  // 地域属性 - 贵州省地区选择
  province?: string // 默认"贵州省"
  city?: string // 市州
  county?: string // 县市区
  township?: string // 乡镇
  regionScope?: string
  isThreeRegions: boolean
  isBorderArea: boolean
  isEthnicArea: boolean
  isRevolutionaryArea: boolean
  isKeyCounty: boolean

  // 振兴发展属性
  isRevitalizationTier?: boolean
  isProvincialDemo: boolean
  isHundredVillageDemo: boolean
  isTieredDevelopment: boolean

  // 跨域帮扶
  isCrossProvince: boolean
  isCrossCity: boolean

  // 协作与表彰
  isCrossUnitCooperation: boolean
  isInOverallPlan: boolean
  honors?: string

  // 帮扶经费
  transitionFundMilitaryTotal?: number
  transitionFundLocalTotal?: number

  // 地理坐标
  latitude?: number | null
  longitude?: number | null

  createdAt?: string
  updatedAt?: string
}

/**
 * 创建帮扶村请求
 */
export interface SupportedVillageCreate {
  sequenceNo?: number
  department: string
  supportUnit: string
  villageName: string
  villageId?: number
  // 地域属性 - 贵州省地区选择
  province?: string // 默认"贵州省"
  city?: string // 市州
  county?: string // 县市区
  township?: string // 乡镇
  regionScope?: string
  isThreeRegions?: number | undefined
  isBorderArea?: number | undefined
  isEthnicArea?: number | undefined
  isRevolutionaryArea?: number | undefined
  isKeyCounty?: number | undefined
  isRevitalizationTier?: boolean
  isProvincialDemo?: number | undefined
  isHundredVillageDemo?: number | undefined
  isTieredDevelopment?: boolean
  isCrossProvince?: boolean
  isCrossCity?: boolean
  isCrossUnitCooperation?: boolean
  isInOverallPlan?: boolean
  honors?: string
  transitionFundMilitaryTotal?: number
  transitionFundLocalTotal?: number
  latitude?: number | null
  longitude?: number | null
}

/**
 * 更新帮扶村请求
 */
export type SupportedVillageUpdate = Partial<SupportedVillageCreate>

// ==================== 年度数据类型 ====================

/**
 * 人口数据
 */
export interface VillagePopulation {
  id: number
  supportedVillageId: number
  year: number
  totalHouseholds: number
  totalPopulation: number
  residentPopulation: number
  unstablePovertyHouseholds: number
  unstablePovertyPopulation: number
  marginalPovertyHouseholds: number
  marginalPovertyPopulation: number
  suddenDifficultyHouseholds: number
  suddenDifficultyPopulation: number
  veteranVillageSecretary: number
  veteranVillageCommittee: number
  createdAt?: string
}

/**
 * 收入数据
 */
export interface VillageIncome {
  id: number
  supportedVillageId: number
  year: number
  perCapitaIncome: number
  countyPerCapitaIncome: number
  collectiveIncome: number
  createdAt?: string
}

/**
 * 力量投入数据
 * Requirements: 5.1, 5.2, 5.3
 */
export interface ForceInvestment {
  id: number
  supportedVillageId: number
  year: number
  seniorLeaderVisits: number // 上级领导干部到村(人次)
  unitSoldierVisits: number // 帮扶单位人员到村(人次)
  createdAt?: string
}

/**
 * 产业帮扶数据
 */
export interface IndustrySupport {
  id: number
  supportedVillageId: number
  year: number
  investment: number
  plannedInvestment: number
  plantingBreeding: number
  workshop: number
  ruralTourism: number
  otherIndustry: number
  createdAt?: string
}

/**
 * 基础设施数据
 */
export interface InfrastructureImprovement {
  id: number
  supportedVillageId: number
  year: number
  investment: number
  plannedInvestment: number
  roadKm: number
  housingRenovation: number
  waterFacilities: number
  culturalPlaza: number
  libraryCafe: number
  createdAt?: string
}

/**
 * 党建帮扶数据
 * Requirements: 8.1, 8.2
 */
export interface PartyBuildingSupport {
  id: number
  supportedVillageId: number
  year: number
  investment: number
  plannedInvestment: number
  pairedBranches: number // 结对帮扶村党支部(个)
  partyInstructors: number // 兼职党建指导员(人)
  jointActivities: number // 支部联建共促活动(次)
  civilizationActivities: number // 乡风文明建设活动(次)
  createdAt?: string
}

/**
 * 医疗帮扶数据
 */
export interface MedicalSupport {
  id: number
  supportedVillageId: number
  year: number
  investment: number
  plannedInvestment: number
  clinicsBuilt: number
  patientsServed: number
  createdAt?: string
}

/**
 * 消费帮扶数据
 */
export interface ConsumptionSupport {
  id: number
  supportedVillageId: number
  year: number
  villageProductsPurchase: number
  otherProductsPurchase: number
  salesCounters: number
  benefitedPopulation: number
  createdAt?: string
}

/**
 * 就业帮扶数据
 */
export interface EmploymentSupport {
  id: number
  supportedVillageId: number
  year: number
  hiredPopulation: number
  trainedPopulation: number
  recommendedEmployment: number
  createdAt?: string
}

/**
 * 教育帮扶数据
 */
export interface EducationSupport {
  id: number
  supportedVillageId: number
  year: number
  investment: number
  donatedSchools: number
  aidedExternalSchools: number
  educationActivities: number
  aidedStudents: number
  volunteerCounselors: number
  createdAt?: string
}

/**
 * 年度数据汇总
 * 注意：键名与后端 /supported-villages/{id}/yearly/{year} 返回的 section key 完全一致
 * （force-investment / party-building 为 kebab-case，非 camelCase）
 */
export interface VillageCommittee {
  overview?: string
  specialIndustry?: string
  collectiveIncomeDesc?: string
  collectiveIncomeAmount?: number
  members?: Array<{
    name: string
    position: string
    phone: string
    isVeteran: boolean
    remark: string
  }>
}

export interface YearlyDataSummary {
  year: number
  population?: VillagePopulation
  income?: VillageIncome
  'force-investment'?: ForceInvestment
  industry?: IndustrySupport
  infrastructure?: InfrastructureImprovement
  'party-building'?: PartyBuildingSupport
  medical?: MedicalSupport
  consumption?: ConsumptionSupport
  employment?: EmploymentSupport
  education?: EducationSupport
  committee?: VillageCommittee
}

// ==================== 查询和筛选类型 ====================

/**
 * 筛选条件
 */
export interface VillageFilters {
  keyword?: string
  department?: string
  supportUnit?: string
  county?: string
  regionScope?: string
  isThreeRegions?: number | undefined
  isBorderArea?: number | undefined
  isEthnicArea?: number | undefined
  isRevolutionaryArea?: number | undefined
  isKeyCounty?: number | undefined
  isProvincialDemo?: number | undefined
  isHundredVillageDemo?: number | undefined
  isTieredDevelopment?: boolean
  isRevitalizationTier?: boolean
  isCrossProvince?: boolean
  isCrossCity?: boolean
  isCrossUnitCooperation?: boolean
  isInOverallPlan?: boolean
  yearStart?: number
  yearEnd?: number
}

/**
 * 筛选选项
 */
export interface FilterOptions {
  departments: string[]
  supportUnits: string[]
  regionScopes: string[]
  isRevitalizationTier?: boolean
  years: number[]
}

/**
 * 聚合查询参数
 */
export interface AggregateQuery {
  yearStart?: number
  yearEnd?: number
  department?: string
  supportUnit?: string
  regionScope?: string
  isThreeRegions?: number | undefined
  isKeyCounty?: number | undefined
  groupBy?: string[]
  metrics?: string[]
}

/**
 * 钻取查询参数
 */
export interface DrillDownQuery {
  dimension: 'department' | 'support_unit' | 'region' | 'year' | 'province'
  value: string
  targetDimension: 'department' | 'support_unit' | 'region' | 'year'
  filters?: Record<string, unknown>
}

/**
 * 钻取结果项
 */
export interface DrillDownItem {
  name: string
  value: number
  dimension: string
  totalPopulation?: number
}

/**
 * 钻取结果
 */
export interface DrillDownResult {
  items: DrillDownItem[]
  total: number
  dimension: string
  sourceDimension: string
  sourceValue: string
}

// ==================== 报表导出类型 ====================

/**
 * 导出格式
 */
export type ExportFormat = 'excel' | 'pdf'

/**
 * 数据板块
 */
export type DataSection =
  | 'population'
  | 'income'
  | 'industry'
  | 'infrastructure'
  | 'education'
  | 'medical'
  | 'consumption'
  | 'employment'
  | 'partyBuilding'
  | 'forceInvestment'

/**
 * 导出查询参数
 */
export interface ExportQuery {
  year: number
  format: ExportFormat
  villageIds?: number[]
  includeSections?: DataSection[]
}

/**
 * 导出响应
 */
export interface ExportResponse {
  fileUrl: string
  fileName: string
  fileSize: number
  expiresAt: string
}

// ==================== 报表订阅类型 ====================

/**
 * 报表类型
 */
export type ReportType =
  | 'comprehensive'
  | 'population'
  | 'income'
  | 'industry'
  | 'infrastructure'
  | 'education'

/**
 * 发送频率
 */
export type SubscriptionFrequency = 'daily' | 'weekly' | 'monthly' | 'quarterly'

/**
 * 报表订阅
 */
export interface ReportSubscription {
  id: number
  userId: number
  name: string
  reportType: ReportType
  format: ExportFormat
  year?: number
  villageIds?: number[]
  includeSections?: DataSection[]
  frequency: SubscriptionFrequency
  sendDay: number
  sendTime: string
  email: string
  isActive: boolean
  lastSentAt?: string
  nextSendAt?: string
  createdAt?: string
  updatedAt?: string
}

/**
 * 创建订阅请求
 */
export interface ReportSubscriptionCreate {
  name: string
  reportType: ReportType
  format?: ExportFormat
  year?: number
  villageIds?: number[]
  includeSections?: DataSection[]
  frequency?: SubscriptionFrequency
  sendDay?: number
  sendTime?: string
  email: string
}

/**
 * 更新订阅请求
 */
export type ReportSubscriptionUpdate = Partial<ReportSubscriptionCreate> & {
  isActive?: boolean
}

// ==================== 统计汇总类型 ====================

/**
 * 村庄统计
 */
export interface VillageStatistics {
  totalVillages: number
  threeRegionsCount: number
  keyCountyCount: number
  provincialDemoCount: number
  crossProvinceCount: number
}

/**
 * 人口统计
 */
export interface PopulationStatistics {
  totalPopulation: number
  totalHouseholds: number
  povertyHouseholds: number
}

/**
 * 收入统计
 */
export interface IncomeStatistics {
  avgPerCapitaIncome: number
  totalCollectiveIncome: number
}

/**
 * 投入统计
 */
export interface InvestmentStatistics {
  industry: number
  infrastructure: number
  infrastructureRoadKm: number
  education: number
  educationAidedStudents: number
}

/**
 * 汇总统计结果
 */
export interface SummaryStatistics {
  year: number
  villages: VillageStatistics
  population: PopulationStatistics
  income: IncomeStatistics
  investment: InvestmentStatistics
}

// ==================== 对比分析类型 ====================

/**
 * 对比指标
 */
export type CompareMetric = 'population' | 'income' | 'industry' | 'infrastructure' | 'education'

/**
 * 村庄对比数据
 */
export interface VillageCompareData {
  id: number
  name: string
  department: string
  supportUnit: string
  data: Record<CompareMetric, Record<string, number>>
}

/**
 * 村庄对比结果
 */
export interface VillageCompareResult {
  year: number
  villages: VillageCompareData[]
  metrics: CompareMetric[]
}

/**
 * 年份对比数据
 */
export interface YearCompareData {
  year: number
  data: Record<CompareMetric, Record<string, number>>
}

/**
 * 年份对比结果
 */
export interface YearCompareResult {
  village: {
    id: number
    name: string
    department: string
    supportUnit: string
  }
  years: YearCompareData[]
  metrics: CompareMetric[]
}

// ==================== 分页响应类型 ====================

// 使用 api.ts 中定义的 PaginatedResponse
import type { PaginatedResponse } from './api'

/**
 * 帮扶村列表响应
 */
export type SupportedVillageListResponse = PaginatedResponse<SupportedVillage>

/**
 * 订阅列表响应
 */
export type ReportSubscriptionListResponse = PaginatedResponse<ReportSubscription>
