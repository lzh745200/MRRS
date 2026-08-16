<template>
  <div class="comprehensive-entry">
    <div class="page-header">
      <h2 class="page-title">综合数据录入</h2>
      <p class="page-desc">整合16个帮扶数据板块，分步骤录入完整数据</p>
    </div>

    <!-- 步骤条 -->
    <div class="steps-card">
      <el-steps :active="currentStep" finish-status="success" align-center>
        <el-step title="基础信息" description="部门单位与帮扶村信息" />
        <el-step title="投入情况" description="经费与力量投入数据" />
        <el-step title="专项帮扶" description="产业/基建/党建/医疗等" />
        <el-step title="荣誉与协作" description="表彰、跨单位协作" />
        <el-step title="关联与附件" description="关联数据与文件上传" />
      </el-steps>
    </div>

    <!-- 步骤内容 -->
    <div class="step-content">
      <!-- 步骤1: 基础信息 -->
      <div v-show="currentStep === 0" class="step-panel">
        <el-form :model="formData.basicInfo" label-width="140px" class="entry-form">
          <h3 class="form-section-title">部门与单位信息</h3>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="部门单位" required>
                <el-input v-model="formData.basicInfo.department" placeholder="请输入部门单位" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="具体帮扶单位" required>
                <el-input v-model="formData.basicInfo.supportUnit" placeholder="请输入帮扶单位" />
              </el-form-item>
            </el-col>
          </el-row>

          <h3 class="form-section-title">帮扶村信息</h3>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="帮扶村名称" required>
                <el-input v-model="formData.basicInfo.villageName" placeholder="请输入帮扶村名称" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="帮扶类型" required>
                <el-select v-model="formData.basicInfo.helpType" placeholder="请选择">
                  <el-option
                    v-for="t in helpTypes"
                    :key="t.value"
                    :label="t.label"
                    :value="t.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="省份" required>
                <el-select
                  v-model="formData.basicInfo.province"
                  placeholder="请选择"
                  @change="onRegionChange"
                >
                  <el-option
                    v-for="p in provinces"
                    :key="p.value"
                    :label="p.label"
                    :value="p.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="市/州" required>
                <el-input
                  v-model="formData.basicInfo.city"
                  placeholder="请输入市/州"
                  @change="onRegionChange"
                />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="县/区" required>
                <el-input
                  v-model="formData.basicInfo.county"
                  placeholder="请输入县/区"
                  @change="onRegionChange"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="乡镇">
                <el-input v-model="formData.basicInfo.township" placeholder="请输入乡镇" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="振兴梯队">
                <el-switch v-model="formData.basicInfo.isRevitalizationTier" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="纳入总盘子">
                <el-switch v-model="formData.basicInfo.includedInOverallPlan" />
              </el-form-item>
            </el-col>
          </el-row>

          <h3 class="form-section-title">地区属性（智能识别）</h3>
          <el-row :gutter="20">
            <el-col :span="6"
              ><el-form-item label="三区三州"
                ><el-switch v-model="formData.basicInfo.isThreeRegionsThreeStates" /></el-form-item
            ></el-col>
            <el-col :span="6"
              ><el-form-item label="边疆地区"
                ><el-switch v-model="formData.basicInfo.isBorderArea" /></el-form-item
            ></el-col>
            <el-col :span="6"
              ><el-form-item label="民族地区"
                ><el-switch v-model="formData.basicInfo.isEthnicArea" /></el-form-item
            ></el-col>
            <el-col :span="6"
              ><el-form-item label="革命地区"
                ><el-switch v-model="formData.basicInfo.isRevolutionaryArea" /></el-form-item
            ></el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="6"
              ><el-form-item label="重点帮扶县"
                ><el-switch v-model="formData.basicInfo.isKeyCounty" /></el-form-item
            ></el-col>
          </el-row>

          <h3 class="form-section-title">村委会介绍</h3>
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="村委会基本情况">
                <el-input
                  v-model="formData.committeeInfo.overview"
                  type="textarea"
                  :rows="6"
                  placeholder="请输入村委会基本情况，包括村委会招牌时间、办公条件、组织架构等"
                  maxlength="500"
                  show-word-limit
                />
              </el-form-item>
            </el-col>
          </el-row>

          <h4 class="form-subsection-title">村委会人员信息</h4>
          <div
            v-for="(member, idx) in formData.committeeInfo.members"
            :key="'member' + idx"
            class="dynamic-row"
          >
            <el-row :gutter="12">
              <el-col :span="4">
                <el-form-item label="姓名">
                  <el-input v-model="member.name" placeholder="姓名" maxlength="20" />
                </el-form-item>
              </el-col>
              <el-col :span="4">
                <el-form-item label="职务">
                  <el-select v-model="member.position" placeholder="请选择" allow-create filterable>
                    <el-option label="村支书" value="村支书" />
                    <el-option label="村主任" value="村主任" />
                    <el-option label="副主任" value="副主任" />
                    <el-option label="委员" value="委员" />
                    <el-option label="文书" value="文书" />
                    <el-option label="民兵连长" value="民兵连长" />
                    <el-option label="其他" value="其他" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="5">
                <el-form-item label="联系方式">
                  <el-input v-model="member.phone" placeholder="手机号" maxlength="20" />
                </el-form-item>
              </el-col>
              <el-col :span="3">
                <el-form-item label="退役人员">
                  <el-switch v-model="member.isVeteran" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="备注">
                  <el-input v-model="member.remark" placeholder="备注" maxlength="50" />
                </el-form-item>
              </el-col>
              <el-col :span="2">
                <el-button
                  type="danger"
                  circle
                  class="dynamic-row-remove-btn"
                  @click="formData.committeeInfo.members.splice(idx, 1)"
                  >×</el-button
                >
              </el-col>
            </el-row>
          </div>
          <el-button type="primary" plain @click="addCommitteeMember">+ 添加村委会成员</el-button>

          <el-row :gutter="20" class="form-row-mt-lg">
            <el-col :span="24">
              <el-form-item label="村特色产业情况">
                <el-input
                  v-model="formData.committeeInfo.specialIndustry"
                  type="textarea"
                  :rows="5"
                  placeholder="请描述村特色产业情况，包括产业类型、规模、带动效果等"
                  maxlength="500"
                  show-word-limit
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="村集体收入情况">
                <el-input
                  v-model="formData.committeeInfo.collectiveIncomeDesc"
                  type="textarea"
                  :rows="6"
                  placeholder="请描述村集体收入来源、结构等"
                  maxlength="300"
                  show-word-limit
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="村集体收入(万元)">
                <el-input-number
                  v-model="formData.committeeInfo.collectiveIncomeAmount"
                  :min="0"
                  :precision="2"
                  :controls="false"
                  placeholder="请输入村集体收入"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <h3 class="form-section-title">人口与经济数据</h3>
          <el-row :gutter="20" class="form-row-mb">
            <el-col :span="6"
              ><el-form-item label="起始年份"
                ><el-input-number v-model="popYearStart" :min="2000" :max="2099" /></el-form-item
            ></el-col>
            <el-col :span="6"
              ><el-form-item label="结束年份"
                ><el-input-number v-model="popYearEnd" :min="2000" :max="2099" /></el-form-item
            ></el-col>
          </el-row>
          <div v-for="yr in yearRange" :key="yr" class="year-data-row">
            <el-divider content-position="left">{{ yr }}年</el-divider>
            <el-row :gutter="20">
              <el-col :span="8"
                ><el-form-item :label="`总人口`"
                  ><el-input-number
                    v-model="getPopData(yr).totalPopulation"
                    :min="0"
                    :controls="false" /></el-form-item
              ></el-col>
              <el-col :span="8"
                ><el-form-item :label="`户数`"
                  ><el-input-number
                    v-model="getPopData(yr).households"
                    :min="0"
                    :controls="false" /></el-form-item
              ></el-col>
              <el-col :span="8"
                ><el-form-item :label="`脱贫人口`"
                  ><el-input-number
                    v-model="getPopData(yr).povertyAlleviatedPopulation"
                    :min="0"
                    :controls="false" /></el-form-item
              ></el-col>
            </el-row>
            <el-row :gutter="20" class="form-row-mt">
              <el-col :span="8"
                ><el-form-item :label="`人均收入(元)`"
                  ><el-input-number
                    v-model="getPopData(yr).perCapitaIncome"
                    :min="0"
                    :controls="false" /></el-form-item
              ></el-col>
              <el-col :span="8"
                ><el-form-item :label="`集体经济(万)`"
                  ><el-input-number
                    v-model="getPopData(yr).collectiveEconomyIncome"
                    :min="0"
                    :precision="2"
                    :controls="false" /></el-form-item
              ></el-col>
            </el-row>
          </div>
        </el-form>
      </div>

      <!-- 步骤2: 投入情况 -->
      <div v-show="currentStep === 1" class="step-panel">
        <el-form label-width="140px" class="entry-form">
          <h3 class="form-section-title">经费投入</h3>
          <el-row :gutter="20" class="form-row-mb">
            <el-col :span="6"
              ><el-form-item label="起始年份"
                ><el-input-number v-model="investYearStart" :min="2000" :max="2099" /></el-form-item
            ></el-col>
            <el-col :span="6"
              ><el-form-item label="结束年份"
                ><el-input-number v-model="investYearEnd" :min="2000" :max="2099" /></el-form-item
            ></el-col>
          </el-row>
          <div v-for="yr in investYearRange" :key="'inv' + yr" class="year-data-row">
            <el-divider content-position="left">{{ yr }}年</el-divider>
            <el-row :gutter="20">
              <el-col :span="6"
                ><el-form-item label="专项投入(万)"
                  ><el-input-number
                    v-model="getInvestData(yr).militaryInvestment"
                    :min="0"
                    :precision="2"
                    :controls="false" /></el-form-item
              ></el-col>
              <el-col :span="6"
                ><el-form-item label="协调地方(万)"
                  ><el-input-number
                    v-model="getInvestData(yr).localInvestment"
                    :min="0"
                    :precision="2"
                    :controls="false" /></el-form-item
              ></el-col>
              <el-col :span="6"
                ><el-form-item label="领导到村(人次)"
                  ><el-input-number
                    v-model="getInvestData(yr).leaderVisits"
                    :min="0"
                    :controls="false" /></el-form-item
              ></el-col>
              <el-col :span="6"
                ><el-form-item label="人员到村(人次)"
                  ><el-input-number
                    v-model="getInvestData(yr).soldierVisits"
                    :min="0"
                    :controls="false" /></el-form-item
              ></el-col>
            </el-row>
          </div>
          <div class="auto-calc">
            <el-descriptions title="投入汇总（自动计算）" :column="4" border>
              <el-descriptions-item label="专项投入合计"
                >{{ totalMilitaryInvest.toFixed(2) }}万</el-descriptions-item
              >
              <el-descriptions-item label="地方投入合计"
                >{{ totalLocalInvest.toFixed(2) }}万</el-descriptions-item
              >
              <el-descriptions-item label="总投入"
                >{{ (totalMilitaryInvest + totalLocalInvest).toFixed(2) }}万</el-descriptions-item
              >
              <el-descriptions-item label="到村总人次">{{ totalVisits }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-form>
      </div>

      <!-- 步骤3: 专项帮扶 -->
      <div v-show="currentStep === 2" class="step-panel">
        <el-tabs v-model="helpTab" type="border-card">
          <el-tab-pane label="产业帮扶" name="industry">
            <el-form label-width="120px" class="wide-form">
              <el-row :gutter="20">
                <el-col :span="8"
                  ><el-form-item label="投入(万)"
                    ><el-input-number
                      v-model="formData.industryHelp.investment"
                      :min="0"
                      :precision="2"
                      :controls="false" /></el-form-item
                ></el-col>
                <el-col :span="10"
                  ><el-form-item label="项目类型"
                    ><el-select
                      v-model="formData.industryHelp.projectType"
                      placeholder="请选择项目类型"
                      ><el-option
                        v-for="t in industryTypes"
                        :key="t.value"
                        :label="t.label"
                        :value="t.value" /></el-select></el-form-item
                ></el-col>
                <el-col :span="6"
                  ><el-form-item label="项目数量"
                    ><el-input-number
                      v-model="formData.industryHelp.projectCount"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
              <el-row :gutter="20" class="form-row-mt">
                <el-col :span="8"
                  ><el-form-item label="带动就业"
                    ><el-input-number
                      v-model="formData.industryHelp.employmentDriven"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="基础设施" name="infrastructure">
            <el-form label-width="120px" class="wide-form">
              <el-row :gutter="20">
                <el-col :span="8"
                  ><el-form-item label="投入(万)"
                    ><el-input-number
                      v-model="formData.infrastructureHelp.investment"
                      :min="0"
                      :precision="2"
                      :controls="false" /></el-form-item
                ></el-col>
                <el-col :span="10"
                  ><el-form-item label="项目类型"
                    ><el-select
                      v-model="formData.infrastructureHelp.projectType"
                      placeholder="请选择项目类型"
                      ><el-option
                        v-for="t in infraTypes"
                        :key="t.value"
                        :label="t.label"
                        :value="t.value" /></el-select></el-form-item
                ></el-col>
                <el-col :span="6"
                  ><el-form-item label="项目数量"
                    ><el-input-number
                      v-model="formData.infrastructureHelp.projectCount"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
              <el-row :gutter="20" class="form-row-mt">
                <el-col :span="8"
                  ><el-form-item label="受益人数"
                    ><el-input-number
                      v-model="formData.infrastructureHelp.beneficiaries"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="党建帮扶" name="party">
            <el-form label-width="120px" class="wide-form">
              <el-row :gutter="20">
                <el-col :span="8"
                  ><el-form-item label="投入(万)"
                    ><el-input-number
                      v-model="formData.partyBuildingHelp.investment"
                      :min="0"
                      :precision="2"
                      :controls="false" /></el-form-item
                ></el-col>
                <el-col :span="10"
                  ><el-form-item label="活动类型"
                    ><el-select
                      v-model="formData.partyBuildingHelp.activityType"
                      placeholder="请选择活动类型"
                      ><el-option
                        v-for="t in partyTypes"
                        :key="t.value"
                        :label="t.label"
                        :value="t.value" /></el-select></el-form-item
                ></el-col>
                <el-col :span="6"
                  ><el-form-item label="活动数量"
                    ><el-input-number
                      v-model="formData.partyBuildingHelp.activityCount"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="医疗帮扶" name="medical">
            <el-form label-width="120px" class="wide-form">
              <el-row :gutter="20">
                <el-col :span="8"
                  ><el-form-item label="投入(万)"
                    ><el-input-number
                      v-model="formData.medicalHelp.investment"
                      :min="0"
                      :precision="2"
                      :controls="false" /></el-form-item
                ></el-col>
                <el-col :span="10"
                  ><el-form-item label="活动类型"
                    ><el-select
                      v-model="formData.medicalHelp.activityType"
                      placeholder="请选择活动类型"
                      ><el-option
                        v-for="t in medicalTypes"
                        :key="t.value"
                        :label="t.label"
                        :value="t.value" /></el-select></el-form-item
                ></el-col>
                <el-col :span="6"
                  ><el-form-item label="活动数量"
                    ><el-input-number
                      v-model="formData.medicalHelp.activityCount"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
              <el-row :gutter="20" class="form-row-mt">
                <el-col :span="8"
                  ><el-form-item label="受益人数"
                    ><el-input-number
                      v-model="formData.medicalHelp.beneficiaries"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="消费帮扶" name="consumption">
            <el-form label-width="130px" class="wide-form">
              <el-row :gutter="20">
                <el-col :span="8"
                  ><el-form-item label="采购金额(万)"
                    ><el-input-number
                      v-model="formData.consumptionHelp.purchaseAmount"
                      :min="0"
                      :precision="2"
                      :controls="false" /></el-form-item
                ></el-col>
                <el-col :span="10"
                  ><el-form-item label="产品类型"
                    ><el-input
                      v-model="formData.consumptionHelp.productType"
                      placeholder="如：农产品" /></el-form-item
                ></el-col>
                <el-col :span="6"
                  ><el-form-item label="帮销金额(万)"
                    ><el-input-number
                      v-model="formData.consumptionHelp.salesAmount"
                      :min="0"
                      :precision="2"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="就业帮扶" name="employment">
            <el-form label-width="140px" class="wide-form">
              <el-row :gutter="20">
                <el-col :span="8"
                  ><el-form-item label="帮助就业"
                    ><el-input-number
                      v-model="formData.employmentHelp.employedCount"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
                <el-col :span="8"
                  ><el-form-item label="技能培训(人次)"
                    ><el-input-number
                      v-model="formData.employmentHelp.trainedCount"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
                <el-col :span="8"
                  ><el-form-item label="劳务输出"
                    ><el-input-number
                      v-model="formData.employmentHelp.laborExportCount"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="教育帮扶" name="education">
            <el-form label-width="120px" class="wide-form">
              <el-row :gutter="20">
                <el-col :span="8"
                  ><el-form-item label="投入(万)"
                    ><el-input-number
                      v-model="formData.educationHelp.investment"
                      :min="0"
                      :precision="2"
                      :controls="false" /></el-form-item
                ></el-col>
                <el-col :span="10"
                  ><el-form-item label="活动类型"
                    ><el-select
                      v-model="formData.educationHelp.activityType"
                      placeholder="请选择活动类型"
                      ><el-option
                        v-for="t in educationTypes"
                        :key="t.value"
                        :label="t.label"
                        :value="t.value" /></el-select></el-form-item
                ></el-col>
                <el-col :span="6"
                  ><el-form-item label="活动数量"
                    ><el-input-number
                      v-model="formData.educationHelp.activityCount"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
              <el-row :gutter="20" class="form-row-mt">
                <el-col :span="8"
                  ><el-form-item label="受助学生数"
                    ><el-input-number
                      v-model="formData.educationHelp.aidedStudents"
                      :min="0"
                      :controls="false" /></el-form-item
                ></el-col>
              </el-row>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 步骤4: 荣誉与协作 -->
      <div v-show="currentStep === 3" class="step-panel">
        <el-form label-width="140px" class="entry-form">
          <h3 class="form-section-title">表彰情况</h3>
          <div v-for="(honor, idx) in formData.honors" :key="idx" class="dynamic-row">
            <el-row :gutter="16">
              <el-col :span="4"
                ><el-form-item label="级别"
                  ><el-select v-model="honor.level"
                    ><el-option label="国家级" value="国家级" /><el-option
                      label="省级"
                      value="省级" /><el-option label="市级" value="市级" /><el-option
                      label="其他"
                      value="其他" /></el-select></el-form-item
              ></el-col>
              <el-col :span="10"
                ><el-form-item label="表彰名称"
                  ><el-input v-model="honor.honorName" placeholder="请输入表彰名称" /></el-form-item
              ></el-col>
              <el-col :span="4"
                ><el-form-item label="年份"
                  ><el-input-number
                    v-model="honor.year"
                    :min="2000"
                    :max="2099"
                    :controls="false" /></el-form-item
              ></el-col>
              <el-col :span="4"
                ><el-form-item label="获得者"
                  ><el-input
                    v-model="honor.recipient"
                    placeholder="请输入获得者姓名" /></el-form-item
              ></el-col>
              <el-col :span="2"
                ><el-button
                  type="danger"
                  circle
                  class="dynamic-row-remove-btn"
                  @click="formData.honors.splice(idx, 1)"
                  >×</el-button
                ></el-col
              >
            </el-row>
          </div>
          <el-button type="primary" plain @click="addHonor">+ 添加表彰记录</el-button>

          <h3 class="form-section-title">跨单位协作</h3>
          <el-row :gutter="20">
            <el-col :span="8"
              ><el-form-item label="跨大单位"
                ><el-switch v-model="formData.collaboration.isCrossUnit" /></el-form-item
            ></el-col>
            <el-col :span="8"
              ><el-form-item label="跨省"
                ><el-switch v-model="formData.collaboration.isCrossProvince" /></el-form-item
            ></el-col>
            <el-col :span="8"
              ><el-form-item label="跨市"
                ><el-switch v-model="formData.collaboration.isCrossCity" /></el-form-item
            ></el-col>
          </el-row>
          <el-form-item label="协作内容描述">
            <el-input
              v-model="formData.collaboration.description"
              type="textarea"
              :rows="5"
              placeholder="请描述协作内容"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>
        </el-form>
      </div>

      <!-- 步骤5: 关联与附件 -->
      <div v-show="currentStep === 4" class="step-panel">
        <el-form label-width="140px" class="entry-form">
          <h3 class="form-section-title">关联学校与经费</h3>
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="关联学校">
                <el-input
                  v-model="relatedSchoolText"
                  placeholder="请输入关联学校名称，多个用逗号分隔"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="关联经费记录">
                <el-input
                  v-model="relatedFundText"
                  placeholder="请输入关联经费记录ID，多个用逗号分隔"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <h3 class="form-section-title">附件上传</h3>
          <el-upload
            class="upload-area"
            drag
            multiple
            :auto-upload="false"
            :file-list="fileList"
            @change="handleFileChange"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持图片和文档格式，单个文件不超过20MB</div>
            </template>
          </el-upload>
        </el-form>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div class="action-bar">
      <el-button v-if="currentStep > 0" @click="goPrevStep">上一步</el-button>
      <el-button v-if="currentStep < 4" type="primary" @click="goNextStep">下一步</el-button>
      <el-button type="primary" @click="handleSaveDraft">保存草稿</el-button>
      <el-button v-if="currentStep === 4" type="success" @click="handleSubmit">提交审核</el-button>
      <span v-if="lastSavedAt" class="auto-save-hint">自动保存于 {{ lastSavedAt }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { post } from '@/api/request'
import {
  PROVINCES,
  HELP_TYPES,
  INDUSTRY_PROJECT_TYPES,
  INFRASTRUCTURE_PROJECT_TYPES,
  PARTY_BUILDING_ACTIVITY_TYPES,
  MEDICAL_ACTIVITY_TYPES,
  EDUCATION_ACTIVITY_TYPES,
  detectRegionAttributes,
} from '@/config/regionDictionary'
import type {
  PopulationEconomicData,
  InvestmentData,
  HonorRecord,
  VillageCommitteeMember,
} from '@/types/helpProject'

const DRAFT_STORAGE_KEY = 'comprehensive_entry_draft'
const AUTO_SAVE_INTERVAL = 30_000 // 30秒自动保存
let autoSaveTimer: ReturnType<typeof setInterval> | null = null
const lastSavedAt = ref('')

const currentStep = ref(0)
const helpTab = ref('industry')

const provinces = PROVINCES
const helpTypes = HELP_TYPES
const industryTypes = INDUSTRY_PROJECT_TYPES
const infraTypes = INFRASTRUCTURE_PROJECT_TYPES
const partyTypes = PARTY_BUILDING_ACTIVITY_TYPES
const medicalTypes = MEDICAL_ACTIVITY_TYPES
const educationTypes = EDUCATION_ACTIVITY_TYPES

const currentYear = new Date().getFullYear()

const popYearStart = ref(currentYear - 5)
const popYearEnd = ref(currentYear)
const yearRange = computed(() => {
  const arr: number[] = []
  for (let y = popYearStart.value; y <= popYearEnd.value; y++) arr.push(y)
  return arr
})

const investYearStart = ref(currentYear - 4)
const investYearEnd = ref(currentYear)
const investYearRange = computed(() => {
  const arr: number[] = []
  for (let y = investYearStart.value; y <= investYearEnd.value; y++) arr.push(y)
  return arr
})

const formData = reactive({
  basicInfo: {
    department: '',
    supportUnit: '',
    villageName: '',
    province: '',
    city: '',
    county: '',
    township: '',
    isThreeRegionsThreeStates: false,
    isBorderArea: false,
    isEthnicArea: false,
    isRevolutionaryArea: false,
    isKeyCounty: false,
    isRevitalizationTier: false,
    helpStartYear: currentYear,
    helpType: '',
    includedInOverallPlan: false,
  },
  populationData: yearRange.value.map((y) => ({
    year: y,
    totalPopulation: 0,
    households: 0,
    povertyAlleviatedPopulation: 0,
    perCapitaIncome: 0,
    collectiveEconomyIncome: 0,
  })) as PopulationEconomicData[],
  investmentData: investYearRange.value.map((y) => ({
    year: y,
    militaryInvestment: 0,
    localInvestment: 0,
    leaderVisits: 0,
    soldierVisits: 0,
  })) as InvestmentData[],
  industryHelp: {
    investment: 0,
    projectType: '',
    projectCount: 0,
    employmentDriven: 0,
    year: currentYear,
  },
  infrastructureHelp: {
    investment: 0,
    projectType: '',
    projectCount: 0,
    beneficiaries: 0,
    year: currentYear,
  },
  partyBuildingHelp: {
    investment: 0,
    activityType: '',
    activityCount: 0,
    year: currentYear,
  },
  medicalHelp: {
    investment: 0,
    activityType: '',
    activityCount: 0,
    beneficiaries: 0,
    year: currentYear,
  },
  consumptionHelp: {
    purchaseAmount: 0,
    productType: '',
    salesAmount: 0,
    year: currentYear,
  },
  employmentHelp: {
    employedCount: 0,
    trainedCount: 0,
    laborExportCount: 0,
    year: currentYear,
  },
  educationHelp: {
    investment: 0,
    activityType: '',
    activityCount: 0,
    aidedStudents: 0,
    year: currentYear,
  },
  honors: [] as HonorRecord[],
  collaboration: {
    isCrossUnit: false,
    isCrossProvince: false,
    isCrossCity: false,
    collaboratingUnits: [] as string[],
    description: '',
  },
  committeeInfo: {
    overview: '',
    members: [] as VillageCommitteeMember[],
    specialIndustry: '',
    collectiveIncomeDesc: '',
    collectiveIncomeAmount: 0,
  },
})

const relatedSchoolText = ref('')
const relatedFundText = ref('')
const fileList = ref<any[]>([])

const getPopData = (year: number) => {
  return formData.populationData.find((d) => d.year === year) || formData.populationData[0]
}

const getInvestData = (year: number) => {
  return formData.investmentData.find((d) => d.year === year) || formData.investmentData[0]
}

const totalMilitaryInvest = computed(() =>
  formData.investmentData.reduce((s, d) => s + d.militaryInvestment, 0)
)
const totalLocalInvest = computed(() =>
  formData.investmentData.reduce((s, d) => s + d.localInvestment, 0)
)
const totalVisits = computed(() =>
  formData.investmentData.reduce((s, d) => s + d.leaderVisits + d.soldierVisits, 0)
)

const onRegionChange = () => {
  const { province, city, county } = formData.basicInfo
  if (province && city && county) {
    const attrs = detectRegionAttributes(province, city, county)
    formData.basicInfo.isThreeRegionsThreeStates = attrs.isThreeRegionsThreeStates
    formData.basicInfo.isBorderArea = attrs.isBorderArea
    formData.basicInfo.isEthnicArea = attrs.isEthnicArea
    formData.basicInfo.isRevolutionaryArea = attrs.isRevolutionaryArea
    formData.basicInfo.isKeyCounty = attrs.isKeyCounty
  }
}

const addHonor = () => {
  formData.honors.push({
    level: '省级',
    honorName: '',
    year: currentYear,
    recipient: '',
  })
}

const addCommitteeMember = () => {
  formData.committeeInfo.members.push({
    name: '',
    position: '',
    phone: '',
    isVeteran: false,
    remark: '',
  })
}

watch(yearRange, (newRange) => {
  for (const y of newRange) {
    if (!formData.populationData.find((d) => d.year === y)) {
      formData.populationData.push({
        year: y,
        totalPopulation: 0,
        households: 0,
        povertyAlleviatedPopulation: 0,
        perCapitaIncome: 0,
        collectiveEconomyIncome: 0,
      })
    }
  }
  formData.populationData = formData.populationData.filter((d) => newRange.includes(d.year))
  formData.populationData.sort((a, b) => a.year - b.year)
})

watch(investYearRange, (newRange) => {
  for (const y of newRange) {
    if (!formData.investmentData.find((d) => d.year === y)) {
      formData.investmentData.push({
        year: y,
        militaryInvestment: 0,
        localInvestment: 0,
        leaderVisits: 0,
        soldierVisits: 0,
      })
    }
  }
  formData.investmentData = formData.investmentData.filter((d) => newRange.includes(d.year))
  formData.investmentData.sort((a, b) => a.year - b.year)
})

const handleFileChange = (_file: any) => {
  // 文件处理逻辑
}

// ==================== 自动保存草稿 ====================
function saveDraftToLocal() {
  try {
    const draft = {
      formData: JSON.parse(JSON.stringify(formData)),
      currentStep: currentStep.value,
      popYearStart: popYearStart.value,
      popYearEnd: popYearEnd.value,
      investYearStart: investYearStart.value,
      investYearEnd: investYearEnd.value,
      relatedSchoolText: relatedSchoolText.value,
      relatedFundText: relatedFundText.value,
      savedAt: new Date().toISOString(),
    }
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft))
    lastSavedAt.value = new Date().toLocaleTimeString()
  } catch {
    // localStorage 写满或不可用，静默忽略
  }
}

function loadDraftFromLocal() {
  try {
    const raw = localStorage.getItem(DRAFT_STORAGE_KEY)
    if (!raw) return
    const draft = JSON.parse(raw)
    if (!draft?.formData?.basicInfo) return

    // 检查草稿是否超过7天
    if (draft.savedAt) {
      const savedDate = new Date(draft.savedAt)
      const diffDays = (Date.now() - savedDate.getTime()) / (1000 * 60 * 60 * 24)
      if (diffDays > 7) {
        localStorage.removeItem(DRAFT_STORAGE_KEY)
        return
      }
    }

    Object.assign(formData.basicInfo, draft.formData.basicInfo)
    Object.assign(formData.committeeInfo, draft.formData.committeeInfo)
    Object.assign(formData.industryHelp, draft.formData.industryHelp)
    Object.assign(formData.infrastructureHelp, draft.formData.infrastructureHelp)
    Object.assign(formData.partyBuildingHelp, draft.formData.partyBuildingHelp)
    Object.assign(formData.medicalHelp, draft.formData.medicalHelp)
    Object.assign(formData.consumptionHelp, draft.formData.consumptionHelp)
    Object.assign(formData.employmentHelp, draft.formData.employmentHelp)
    Object.assign(formData.educationHelp, draft.formData.educationHelp)
    Object.assign(formData.collaboration, draft.formData.collaboration)
    if (draft.formData.honors) formData.honors = draft.formData.honors
    if (draft.formData.populationData) formData.populationData = draft.formData.populationData
    if (draft.formData.investmentData) formData.investmentData = draft.formData.investmentData

    if (draft.currentStep != null) currentStep.value = draft.currentStep
    if (draft.popYearStart) popYearStart.value = draft.popYearStart
    if (draft.popYearEnd) popYearEnd.value = draft.popYearEnd
    if (draft.investYearStart) investYearStart.value = draft.investYearStart
    if (draft.investYearEnd) investYearEnd.value = draft.investYearEnd
    if (draft.relatedSchoolText) relatedSchoolText.value = draft.relatedSchoolText
    if (draft.relatedFundText) relatedFundText.value = draft.relatedFundText

    ElMessage.info(`已恢复上次草稿（保存于 ${new Date(draft.savedAt).toLocaleString()}）`)
  } catch {
    // 解析失败则忽略
  }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_STORAGE_KEY)
  lastSavedAt.value = ''
}

// ==================== 步骤校验 ====================
function validateCurrentStep(): boolean {
  if (currentStep.value === 0) {
    const b = formData.basicInfo
    if (!b.department?.trim()) {
      ElMessage.warning('请填写部门单位')
      return false
    }
    if (!b.supportUnit?.trim()) {
      ElMessage.warning('请填写帮扶单位')
      return false
    }
    if (!b.villageName?.trim()) {
      ElMessage.warning('请填写帮扶村名称')
      return false
    }
    if (!b.helpType) {
      ElMessage.warning('请选择帮扶类型')
      return false
    }
    if (!b.province) {
      ElMessage.warning('请选择省份')
      return false
    }
  }
  if (currentStep.value === 1) {
    // 投资数据: 任一年度填写了数据即认为有效(校验数据结构合法性)
    const hasAny = formData.investmentData.some(
      (d) =>
        d.militaryInvestment > 0 ||
        d.localInvestment > 0 ||
        d.leaderVisits > 0 ||
        d.soldierVisits > 0
    )
    const hasPartial = formData.investmentData.some((d) => {
      const filled = [
        d.militaryInvestment,
        d.localInvestment,
        d.leaderVisits,
        d.soldierVisits,
      ].filter((v) => v > 0)
      return filled.length > 0 && filled.length < 4
    })
    if (hasPartial) {
      ElMessage.warning('投资数据填写不完整：请补全已填写年度的各项数据')
      return false
    }
    if (!hasAny) {
      ElMessage.warning('请至少填写一个年度的投资数据')
      return false
    }
  }
  if (currentStep.value === 2) {
    // 专项板块: 填写了项目类型就必须填写投资额/数量
    const checks: Array<[string, string, number]> = [
      ['产业帮扶', formData.industryHelp.projectType, formData.industryHelp.investment],
      [
        '基础设施帮扶',
        formData.infrastructureHelp.projectType,
        formData.infrastructureHelp.investment,
      ],
    ]
    for (const [label, projectType, investment] of checks) {
      if (projectType?.trim() && !(investment > 0)) {
        ElMessage.warning(`请填写${label}的投资额`)
        return false
      }
      if (investment > 0 && !projectType?.trim()) {
        ElMessage.warning(`请填写${label}的项目类型`)
        return false
      }
    }
    const activityChecks: Array<[string, string, number]> = [
      ['党建帮扶', formData.partyBuildingHelp.activityType, formData.partyBuildingHelp.investment],
      ['医疗帮扶', formData.medicalHelp.activityType, formData.medicalHelp.investment],
    ]
    for (const [label, activityType, investment] of activityChecks) {
      if (activityType?.trim() && !(investment > 0)) {
        ElMessage.warning(`请填写${label}的投入金额`)
        return false
      }
      if (investment > 0 && !activityType?.trim()) {
        ElMessage.warning(`请填写${label}的活动类型`)
        return false
      }
    }
  }
  if (currentStep.value === 3) {
    // 消费帮扶与单位协作: 采购金额与销售额需同时填写或同时为空
    const c = formData.consumptionHelp
    if (c.purchaseAmount > 0 && !(c.salesAmount > 0)) {
      ElMessage.warning('请填写消费帮扶的销售额')
      return false
    }
    if (c.salesAmount > 0 && !(c.purchaseAmount > 0)) {
      ElMessage.warning('请填写消费帮扶的采购金额')
      return false
    }
  }
  return true
}

function validateAllSteps(): boolean {
  for (let step = 0; step < 5; step++) {
    const prev = currentStep.value
    currentStep.value = step
    if (!validateCurrentStep()) {
      return false
    }
    currentStep.value = prev
  }
  return true
}

function goNextStep() {
  if (!validateCurrentStep()) return
  if (currentStep.value < 4) {
    currentStep.value++
    saveDraftToLocal()
  }
}

function goPrevStep() {
  if (currentStep.value > 0) {
    currentStep.value--
    saveDraftToLocal()
  }
}

const handleSaveDraft = async () => {
  saveDraftToLocal()
  try {
    await submitVillageData()
    ElMessage.success('草稿已保存到服务器')
  } catch (e: any) {
    ElMessage.success('草稿已保存到本地')
  }
}

const handleSubmit = async () => {
  // 提交前校验全部步骤
  if (!validateAllSteps()) {
    return
  }
  try {
    await ElMessageBox.confirm('确认提交数据进行审核？提交后将清除本地草稿。', '提交确认', {
      type: 'info',
    })
    await submitVillageData()
    clearDraft()
    ElMessage.success('数据已提交审核')
    currentStep.value = 0
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.detail || '提交失败')
    }
  }
}

onMounted(() => {
  loadDraftFromLocal()
  autoSaveTimer = setInterval(saveDraftToLocal, AUTO_SAVE_INTERVAL)
})

onUnmounted(() => {
  if (autoSaveTimer) clearInterval(autoSaveTimer)
})

async function submitVillageData() {
  const b = formData.basicInfo
  const payload = {
    department: b.department,
    support_unit: b.supportUnit,
    village_name: b.villageName,
    province: detectRegionAttributes(b.province).province || '贵州省',
    city: b.city || undefined,
    county: b.county || undefined,
    township: b.township || undefined,
    is_three_regions: b.isThreeRegionsThreeStates,
    is_border_area: b.isBorderArea,
    is_ethnic_area: b.isEthnicArea,
    is_revolutionary_area: b.isRevolutionaryArea,
    is_key_county: b.isKeyCounty,
    is_revitalization_tier: b.isRevitalizationTier || undefined,
    is_in_overall_plan: b.includedInOverallPlan,
  }
  const res = await post('/supported-villages', payload)
  const village = res.data
  const villageId = village?.id || village?.data?.id

  if (!villageId) return village

  // 提交每年的人口数据和收入数据
  for (const pop of formData.populationData) {
    if (pop.totalPopulation > 0 || pop.households > 0) {
      await post(`/supported-villages/${villageId}/yearly/${pop.year}/population`, {
        total_population: pop.totalPopulation,
        total_households: pop.households,
      })
    }
    if (pop.perCapitaIncome > 0 || pop.collectiveEconomyIncome > 0) {
      await post(`/supported-villages/${villageId}/yearly/${pop.year}/income`, {
        per_capita_income: pop.perCapitaIncome,
        collective_income: pop.collectiveEconomyIncome,
      })
    }
  }

  // 提交每年的力量投入数据
  for (const inv of formData.investmentData) {
    if (inv.leaderVisits > 0 || inv.soldierVisits > 0) {
      await post(`/supported-villages/${villageId}/yearly/${inv.year}/force-investment`, {
        senior_leader_visits: inv.leaderVisits,
        unit_soldier_visits: inv.soldierVisits,
      })
    }
  }

  return village
}
</script>

<style scoped>
.comprehensive-entry {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.page-header {
  margin-bottom: 0;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1b4332;
  margin: 0 0 4px 0;
}
.page-desc {
  font-size: 14px;
  color: #666;
  margin: 0;
}
.steps-card {
  background: white;
  padding: 24px 32px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.step-content {
  background: white;
  padding: 32px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  min-height: 600px;
}
.step-panel {
  width: 100%;
}
.entry-form {
  width: 100%;
}
.entry-form :deep(.el-form-item__content) {
  width: calc(100% - 140px);
}
.entry-form :deep(.el-input__wrapper),
.entry-form :deep(.el-input-number),
.entry-form :deep(.el-select) {
  width: 100% !important;
}
.entry-form :deep(.el-textarea__inner) {
  min-height: 80px !important;
}
.wide-form :deep(.el-form-item__content) {
  width: calc(100% - 140px);
}
.wide-form :deep(.el-input__wrapper),
.wide-form :deep(.el-input-number),
.wide-form :deep(.el-select) {
  width: 100% !important;
}
.wide-form :deep(.el-input-number .el-input__inner) {
  text-align: left;
}
.form-section-title {
  font-size: 15px;
  font-weight: 600;
  color: #1b4332;
  margin: 24px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e8e8e8;
}
.form-section-title:first-child {
  margin-top: 0;
}
.year-data-row {
  margin-bottom: 8px;
}
.auto-calc {
  margin-top: 24px;
}
.dynamic-row {
  margin-bottom: 8px;
  padding: 8px;
  background: #fafafa;
  border-radius: 4px;
}
.dynamic-row-remove-btn {
  margin-top: 30px;
}
.action-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.auto-save-hint {
  font-size: 12px;
  color: var(--color-info);
  margin-left: 8px;
}
</style>
