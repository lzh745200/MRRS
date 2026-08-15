<template>
  <div class="section-data-form">
    <!-- 年份选择 -->
    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-width="140px"
      label-position="left"
    >
      <el-form-item label="数据年份">
        <el-select v-model="selectedYear" class="input-year-width" @change="handleYearChange">
          <el-option
            v-for="year in availableYears"
            :key="year"
            :label="`${year}年`"
            :value="year"
          />
        </el-select>
      </el-form-item>

      <!-- ==================== 人口数据 ==================== -->
      <template v-if="sectionKey === 'population'">
        <el-divider content-position="left">人口与户籍数据</el-divider>
        <el-row :gutter="24">
          <el-col :span="8">
            <el-form-item label="总户数" prop="totalHouseholds">
              <el-input-number
                v-model="formData.totalHouseholds"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="总人数" prop="totalPopulation">
              <el-input-number
                v-model="formData.totalPopulation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="常住人口数" prop="residentPopulation">
              <el-input-number
                v-model="formData.residentPopulation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="8">
            <el-form-item label="劳动力(人)" prop="laborForce">
              <el-input-number v-model="formData.laborForce" :min="0" class="input-full-width" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="外出务工(人)" prop="migrantWorkers">
              <el-input-number
                v-model="formData.migrantWorkers"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="脱贫人口(人)" prop="povertyPopulation">
              <el-input-number
                v-model="formData.povertyPopulation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="8">
            <el-form-item label="脱贫户数(户)" prop="povertyHouseholds">
              <el-input-number
                v-model="formData.povertyHouseholds"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="脱贫不稳定户(户)" prop="unstablePovertyHouseholds">
              <el-input-number
                v-model="formData.unstablePovertyHouseholds"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="脱贫不稳定户(人)" prop="unstablePovertyPopulation">
              <el-input-number
                v-model="formData.unstablePovertyPopulation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="边缘易致贫户(户)" prop="marginalPovertyHouseholds">
              <el-input-number
                v-model="formData.marginalPovertyHouseholds"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="边缘易致贫户(人)" prop="marginalPovertyPopulation">
              <el-input-number
                v-model="formData.marginalPovertyPopulation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="突发严重困难户(户)" prop="suddenDifficultyHouseholds">
              <el-input-number
                v-model="formData.suddenDifficultyHouseholds"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="突发严重困难户(人)" prop="suddenDifficultyPopulation">
              <el-input-number
                v-model="formData.suddenDifficultyPopulation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="村支书(退役人员)" prop="veteranVillageSecretary">
              <el-input-number
                v-model="formData.veteranVillageSecretary"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="村委员(退役人员)" prop="veteranVillageCommittee">
              <el-input-number
                v-model="formData.veteranVillageCommittee"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 收入数据 ==================== -->
      <template v-if="sectionKey === 'income'">
        <el-divider content-position="left">收入数据</el-divider>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="村人均纯收入(万元)" prop="perCapitaIncome">
              <el-input-number
                v-model="formData.perCapitaIncome"
                :min="0"
                :precision="4"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="县区人均收入(万元)" prop="countyPerCapitaIncome">
              <el-input-number
                v-model="formData.countyPerCapitaIncome"
                :min="0"
                :precision="4"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="村集体收入(万元)" prop="collectiveIncome">
              <el-input-number
                v-model="formData.collectiveIncome"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 力量投入 ==================== -->
      <template v-if="sectionKey === 'force_investment'">
        <el-divider content-position="left">力量投入情况</el-divider>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="上级领导到村(人次)" prop="seniorLeaderVisits">
              <el-input-number
                v-model="formData.seniorLeaderVisits"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="帮扶单位人员到村(人次)" prop="unitSoldierVisits">
              <el-input-number
                v-model="formData.unitSoldierVisits"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 产业帮扶 ==================== -->
      <template v-if="sectionKey === 'industry'">
        <el-divider content-position="left">产业帮扶</el-divider>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="当年投入(万元)" prop="investment">
              <el-input-number
                v-model="formData.investment"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划投入(万元)" prop="plannedInvestment">
              <el-input-number
                v-model="formData.plannedInvestment"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="种植养殖(个)" prop="plantingBreeding">
              <el-input-number
                v-model="formData.plantingBreeding"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="帮扶车间(个)" prop="workshop">
              <el-input-number v-model="formData.workshop" :min="0" class="input-full-width" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="乡村旅游(个)" prop="ruralTourism">
              <el-input-number v-model="formData.ruralTourism" :min="0" class="input-full-width" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="其他(个)" prop="otherIndustry">
              <el-input-number v-model="formData.otherIndustry" :min="0" class="input-full-width" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 基础设施 ==================== -->
      <template v-if="sectionKey === 'infrastructure'">
        <el-divider content-position="left">改善基础设施</el-divider>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="当年投入(万元)" prop="investment">
              <el-input-number
                v-model="formData.investment"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划投入(万元)" prop="plannedInvestment">
              <el-input-number
                v-model="formData.plannedInvestment"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="乡村道路(公里)" prop="roadKm">
              <el-input-number
                v-model="formData.roadKm"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="住房改造(户)" prop="housingRenovation">
              <el-input-number
                v-model="formData.housingRenovation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="水利设施(个)" prop="waterFacilities">
              <el-input-number
                v-model="formData.waterFacilities"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="文化广场(个)" prop="culturalPlaza">
              <el-input-number v-model="formData.culturalPlaza" :min="0" class="input-full-width" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="书屋网吧(个)" prop="libraryCafe">
              <el-input-number v-model="formData.libraryCafe" :min="0" class="input-full-width" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 党建帮扶 ==================== -->
      <template v-if="sectionKey === 'party_building'">
        <el-divider content-position="left">党建帮扶</el-divider>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="当年投入(万元)" prop="investment">
              <el-input-number
                v-model="formData.investment"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划投入(万元)" prop="plannedInvestment">
              <el-input-number
                v-model="formData.plannedInvestment"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="结对帮扶党支部(个)" prop="pairedBranches">
              <el-input-number
                v-model="formData.pairedBranches"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="党建指导员(人)" prop="partyInstructors">
              <el-input-number
                v-model="formData.partyInstructors"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="联建共促活动(次)" prop="jointActivities">
              <el-input-number
                v-model="formData.jointActivities"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="乡风文明活动(次)" prop="civilizationActivities">
              <el-input-number
                v-model="formData.civilizationActivities"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 医疗帮扶 ==================== -->
      <template v-if="sectionKey === 'medical'">
        <el-divider content-position="left">医疗帮扶</el-divider>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="当年投入(万元)" prop="investment">
              <el-input-number
                v-model="formData.investment"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划投入(万元)" prop="plannedInvestment">
              <el-input-number
                v-model="formData.plannedInvestment"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="帮建卫生院室(个)" prop="clinicsBuilt">
              <el-input-number v-model="formData.clinicsBuilt" :min="0" class="input-full-width" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="巡诊群众(人次)" prop="patientsServed">
              <el-input-number
                v-model="formData.patientsServed"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 消费帮扶 ==================== -->
      <template v-if="sectionKey === 'consumption'">
        <el-divider content-position="left">消费帮扶</el-divider>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="采购村产品(万元)" prop="villageProductsPurchase">
              <el-input-number
                v-model="formData.villageProductsPurchase"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采购他村产品(万元)" prop="otherProductsPurchase">
              <el-input-number
                v-model="formData.otherProductsPurchase"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="营区销售专柜(个)" prop="salesCounters">
              <el-input-number v-model="formData.salesCounters" :min="0" class="input-full-width" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="惠及群众(人)" prop="benefitedPopulation">
              <el-input-number
                v-model="formData.benefitedPopulation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 就业帮扶 ==================== -->
      <template v-if="sectionKey === 'employment'">
        <el-divider content-position="left">就业帮扶</el-divider>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="聘用脱贫群众(人)" prop="hiredPopulation">
              <el-input-number
                v-model="formData.hiredPopulation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="技能培训(人次)" prop="trainedPopulation">
              <el-input-number
                v-model="formData.trainedPopulation"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="推荐就业(人次)" prop="recommendedEmployment">
              <el-input-number
                v-model="formData.recommendedEmployment"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 教育帮扶 ==================== -->
      <template v-if="sectionKey === 'education'">
        <el-divider content-position="left">教育帮扶</el-divider>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="教育投入(万元)" prop="investment">
              <el-input-number
                v-model="formData.investment"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="捐赠帮扶村学校(所)" prop="donatedSchools">
              <el-input-number
                v-model="formData.donatedSchools"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="援建外村学校(所)" prop="aidedExternalSchools">
              <el-input-number
                v-model="formData.aidedExternalSchools"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="助学兴教活动(次)" prop="educationActivities">
              <el-input-number
                v-model="formData.educationActivities"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资助困难学生(人)" prop="aidedStudents">
              <el-input-number v-model="formData.aidedStudents" :min="0" class="input-full-width" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="校外辅导员(人)" prop="volunteerCounselors">
              <el-input-number
                v-model="formData.volunteerCounselors"
                :min="0"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- ==================== 村委会情况 ==================== -->
      <template v-if="sectionKey === 'committee'">
        <el-divider content-position="left">村委会基本情况</el-divider>
        <el-form-item label="基本情况描述">
          <el-input
            v-model="formData.overview"
            type="textarea"
            :rows="3"
            placeholder="请输入村委会基本情况"
          />
        </el-form-item>
        <el-form-item label="特色产业情况">
          <el-input
            v-model="formData.specialIndustry"
            type="textarea"
            :rows="3"
            placeholder="请输入村特色产业情况"
          />
        </el-form-item>
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item label="集体收入描述">
              <el-input v-model="formData.collectiveIncomeDesc" placeholder="请输入收入情况描述" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="集体收入(万元)" prop="collectiveIncomeAmount">
              <el-input-number
                v-model="formData.collectiveIncomeAmount"
                :min="0"
                :precision="2"
                class="input-full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">村委会成员</el-divider>
        <div class="form-block-gap">
          <el-button type="primary" size="small" @click="addCommitteeMember">新增成员</el-button>
        </div>
        <el-table :data="committeeMembers" border size="small" class="form-table-gap">
          <el-table-column label="姓名" min-width="100">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" placeholder="姓名" />
            </template>
          </el-table-column>
          <el-table-column label="职务" min-width="100">
            <template #default="{ row }">
              <el-input v-model="row.position" size="small" placeholder="职务" />
            </template>
          </el-table-column>
          <el-table-column label="联系方式" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.phone" size="small" placeholder="电话" />
            </template>
          </el-table-column>
          <el-table-column label="退役人员" width="90" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.isVeteran" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.remark" size="small" placeholder="备注" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70" align="center">
            <template #default="{ $index }">
              <el-button type="danger" text size="small" @click="committeeMembers.splice($index, 1)"
                >删除</el-button
              >
            </template>
          </el-table-column>
        </el-table>
      </template>

      <!-- ==================== 印证资料上传 ==================== -->
      <el-divider content-position="left">印证资料</el-divider>
      <div class="attachment-section">
        <el-upload
          :file-list="uploadFileList"
          :before-upload="handleBeforeUpload"
          :on-remove="handleUploadRemove"
          :http-request="handleCustomUpload"
          multiple
          accept=".jpg,.jpeg,.png,.gif,.bmp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.rar"
          :limit="10"
          :on-exceed="handleExceed"
        >
          <el-button type="primary" plain>
            <el-icon><Upload /></el-icon>上传印证资料
          </el-button>
          <template #tip>
            <div class="upload-tip">
              支持图片、PDF、Office文档、压缩包等格式，单文件不超过20MB，最多10个文件
            </div>
          </template>
        </el-upload>

        <!-- 已上传附件列表 -->
        <div v-if="attachments.length" class="attachment-list">
          <div v-for="att in attachments" :key="att.id" class="attachment-item">
            <div class="attachment-info">
              <el-icon class="file-icon"><Document /></el-icon>
              <span class="file-name" :title="att.fileName">{{ att.fileName }}</span>
              <span class="file-size">{{ formatFileSize(att.fileSize) }}</span>
            </div>
            <div class="attachment-actions">
              <el-button
                v-if="isPreviewable(att.fileType)"
                text
                type="primary"
                size="small"
                @click="handlePreview(att)"
              >
                预览
              </el-button>
              <el-button text type="primary" size="small" @click="handleDownload(att)">
                下载
              </el-button>
              <el-button text type="danger" size="small" @click="handleDeleteAttachment(att)">
                删除
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="no-attachment">暂无印证资料</div>
      </div>

      <!-- 操作按钮 -->
      <el-form-item class="form-item-actions">
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        <el-button @click="handleClose">取消</el-button>
      </el-form-item>
    </el-form>

    <!-- 文件预览弹窗 -->
    <el-dialog
      v-model="previewVisible"
      :title="previewTitle"
      width="800px"
      destroy-on-close
      append-to-body
    >
      <div class="preview-container">
        <img v-if="previewType === 'image'" :src="previewUrl" alt="预览" class="preview-image" />
        <iframe v-else-if="previewType === 'pdf'" :src="previewUrl" class="preview-pdf" />
        <div v-else class="preview-unsupported">
          <el-icon :size="48" color="var(--color-info)"><Document /></el-icon>
          <p>该文件类型不支持在线预览，请下载后查看</p>
          <el-button type="primary" @click="handleDownload(previewAttachment!)">
            下载文件
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Document } from '@element-plus/icons-vue'
import type { UploadFile, UploadRequestOptions, UploadRawFile } from 'element-plus'
import {
  getYearlyData,
  savePopulationData,
  saveIncomeData,
  saveIndustryData,
  saveInfrastructureData,
  saveEducationData,
  saveForceInvestmentData,
  savePartyBuildingData,
  saveMedicalData,
  saveConsumptionData,
  saveEmploymentData,
  saveCommitteeData,
  uploadSectionAttachment,
  getSectionAttachments,
  deleteSectionAttachment,
} from '@/api/supportedVillage'
interface SectionAttachment {
  id: number
  fileName: string
  fileSize: number
  fileType: string
  [key: string]: any
}

const props = defineProps<{
  villageId: number
  villageName: string
  sectionKey: string
  initialYear?: number
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const formRef = ref()
defineExpose({ formRef })

// ==================== 表单验证规则 ====================
// 通用规则生成器：必填 / 非负
function requiredRule(label: string) {
  return { required: true, message: `请输入${label}`, trigger: ['blur', 'change'] }
}

function nonNegativeRule(label: string) {
  return {
    validator: (_rule: any, value: number, callback: (error?: Error) => void) => {
      if (value != null && value < 0) {
        callback(new Error(`${label}不能为负数`))
      } else {
        callback()
      }
    },
    trigger: ['blur', 'change'],
  }
}

// 各板块数值字段配置：[字段名, 显示名称, 是否必填]
const SECTION_NUMERIC_FIELDS: Record<string, Array<[string, string, boolean]>> = {
  population: [
    ['totalHouseholds', '总户数', true],
    ['totalPopulation', '总人数', true],
    ['residentPopulation', '常住人口数', true],
    ['laborForce', '劳动力人数', false],
    ['migrantWorkers', '外出务工人数', false],
    ['povertyPopulation', '脱贫人口数', false],
    ['povertyHouseholds', '脱贫户数', false],
    ['unstablePovertyHouseholds', '脱贫不稳定户数', false],
    ['unstablePovertyPopulation', '脱贫不稳定人口数', false],
    ['marginalPovertyHouseholds', '边缘易致贫户数', false],
    ['marginalPovertyPopulation', '边缘易致贫人口数', false],
    ['suddenDifficultyHouseholds', '突发严重困难户数', false],
    ['suddenDifficultyPopulation', '突发严重困难人口数', false],
    ['veteranVillageSecretary', '村支书(退役人员)人数', false],
    ['veteranVillageCommittee', '村委员(退役人员)人数', false],
  ],
  income: [
    ['perCapitaIncome', '村人均纯收入', true],
    ['countyPerCapitaIncome', '县区人均收入', false],
    ['collectiveIncome', '村集体收入', true],
  ],
  force_investment: [
    ['seniorLeaderVisits', '上级领导到村人次', false],
    ['unitSoldierVisits', '帮扶单位人员到村人次', false],
  ],
  industry: [
    ['investment', '当年投入金额', true],
    ['plannedInvestment', '计划投入金额', false],
    ['plantingBreeding', '种植养殖数量', false],
    ['workshop', '帮扶车间数量', false],
    ['ruralTourism', '乡村旅游数量', false],
    ['otherIndustry', '其他产业数量', false],
  ],
  infrastructure: [
    ['investment', '当年投入金额', true],
    ['plannedInvestment', '计划投入金额', false],
    ['roadKm', '乡村道路里程', false],
    ['housingRenovation', '住房改造户数', false],
    ['waterFacilities', '水利设施数量', false],
    ['culturalPlaza', '文化广场数量', false],
    ['libraryCafe', '书屋网吧数量', false],
  ],
  party_building: [
    ['investment', '当年投入金额', true],
    ['plannedInvestment', '计划投入金额', false],
    ['pairedBranches', '结对帮扶党支部数量', false],
    ['partyInstructors', '党建指导员人数', false],
    ['jointActivities', '联建共促活动次数', false],
    ['civilizationActivities', '乡风文明活动次数', false],
  ],
  medical: [
    ['investment', '当年投入金额', true],
    ['plannedInvestment', '计划投入金额', false],
    ['clinicsBuilt', '帮建卫生院室数量', false],
    ['patientsServed', '巡诊群众人次', false],
  ],
  consumption: [
    ['villageProductsPurchase', '采购村产品金额', false],
    ['otherProductsPurchase', '采购他村产品金额', false],
    ['salesCounters', '销售专柜数量', false],
    ['benefitedPopulation', '惠及群众人数', false],
  ],
  employment: [
    ['hiredPopulation', '聘用脱贫群众人数', false],
    ['trainedPopulation', '技能培训人次', false],
    ['recommendedEmployment', '推荐就业人次', false],
  ],
  education: [
    ['investment', '教育投入金额', true],
    ['donatedSchools', '捐赠学校数量', false],
    ['aidedExternalSchools', '援建外村学校数量', false],
    ['educationActivities', '助学兴教活动次数', false],
    ['aidedStudents', '资助学生人数', false],
    ['volunteerCounselors', '校外辅导员人数', false],
  ],
  committee: [['collectiveIncomeAmount', '集体收入', false]],
}

// 动态验证规则 — 根据 sectionKey 生成对应规则
const formRules = computed(() => {
  const rules: Record<string, any[]> = {}

  // 1) 数值字段：关键字段必填 + 全部字段非负校验
  for (const [field, label, required] of SECTION_NUMERIC_FIELDS[props.sectionKey] ?? []) {
    rules[field] = []
    if (required) {
      rules[field].push(requiredRule(label))
    }
    rules[field].push(nonNegativeRule(label))
  }

  // 2) 特殊业务规则（人口板块：总人数须大于0，常住人口不能超过总人数）
  if (props.sectionKey === 'population') {
    rules.totalPopulation = [
      ...rules.totalPopulation,
      {
        validator: (_rule: any, value: number, callback: (error?: Error) => void) => {
          if (value != null && value <= 0) {
            callback(new Error('总人数必须大于0'))
          } else {
            callback()
          }
        },
        trigger: ['blur', 'change'],
      },
    ]
    rules.residentPopulation = [
      ...rules.residentPopulation,
      {
        validator: (_rule: any, value: number, callback: (error?: Error) => void) => {
          if (value != null && value > (formData.totalPopulation || 0)) {
            callback(new Error('常住人口不能超过总人数'))
          } else {
            callback()
          }
        },
        trigger: ['blur', 'change'],
      },
    ]
  }

  return rules
})
const saving = ref(false)
const selectedYear = ref(props.initialYear || new Date().getFullYear())
const availableYears = (() => {
  const years: number[] = []
  for (let y = 2017; y <= new Date().getFullYear() + 1; y++) {
    years.push(y)
  }
  return years.reverse()
})()

// 动态表单数据 — 根据 sectionKey 使用对应字段
const formData = reactive<Record<string, any>>({})

// 附件相关
const attachments = ref<SectionAttachment[]>([])
const uploadFileList = ref<UploadFile[]>([])

// 预览相关
const previewVisible = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')
const previewType = ref<'image' | 'pdf' | 'other'>('other')
const previewAttachment = ref<SectionAttachment | null>(null)

// sectionKey 与后端数据字段的映射
// 村委会成员列表（committee 板块专用）
const committeeMembers = ref<
  Array<{
    name: string
    position: string
    phone: string
    isVeteran: boolean
    remark: string
  }>
>([])

function addCommitteeMember() {
  committeeMembers.value.push({
    name: '',
    position: '',
    phone: '',
    isVeteran: false,
    remark: '',
  })
}

// 仅非对称映射：内部 prop key (snake_case) → 后端 API 响应 key (kebab-case)
// 单单词 key（population、income 等）各约定间不变，无需显式映射
const _SECTION_KEY_OVERRIDE: Record<string, string> = {
  force_investment: 'force-investment',
  party_building: 'party-building',
}
function resolveApiKey(sectionKey: string): string {
  return _SECTION_KEY_OVERRIDE[sectionKey] ?? sectionKey
}

// 各板块默认数据
function getDefaultFormData(key: string): Record<string, any> {
  const defaults: Record<string, Record<string, any>> = {
    population: {
      totalHouseholds: 0,
      totalPopulation: 0,
      residentPopulation: 0,
      laborForce: 0,
      migrantWorkers: 0,
      povertyPopulation: 0,
      povertyHouseholds: 0,
      unstablePovertyHouseholds: 0,
      unstablePovertyPopulation: 0,
      marginalPovertyHouseholds: 0,
      marginalPovertyPopulation: 0,
      suddenDifficultyHouseholds: 0,
      suddenDifficultyPopulation: 0,
      veteranVillageSecretary: 0,
      veteranVillageCommittee: 0,
    },
    income: {
      perCapitaIncome: 0,
      countyPerCapitaIncome: 0,
      collectiveIncome: 0,
    },
    force_investment: {
      seniorLeaderVisits: 0,
      unitSoldierVisits: 0,
    },
    industry: {
      investment: 0,
      plannedInvestment: 0,
      plantingBreeding: 0,
      workshop: 0,
      ruralTourism: 0,
      otherIndustry: 0,
    },
    infrastructure: {
      investment: 0,
      plannedInvestment: 0,
      roadKm: 0,
      housingRenovation: 0,
      waterFacilities: 0,
      culturalPlaza: 0,
      libraryCafe: 0,
    },
    party_building: {
      investment: 0,
      plannedInvestment: 0,
      pairedBranches: 0,
      partyInstructors: 0,
      jointActivities: 0,
      civilizationActivities: 0,
    },
    medical: {
      investment: 0,
      plannedInvestment: 0,
      clinicsBuilt: 0,
      patientsServed: 0,
    },
    consumption: {
      villageProductsPurchase: 0,
      otherProductsPurchase: 0,
      salesCounters: 0,
      benefitedPopulation: 0,
    },
    employment: {
      hiredPopulation: 0,
      trainedPopulation: 0,
      recommendedEmployment: 0,
    },
    education: {
      investment: 0,
      donatedSchools: 0,
      aidedExternalSchools: 0,
      educationActivities: 0,
      aidedStudents: 0,
      volunteerCounselors: 0,
    },
    committee: {
      overview: '',
      specialIndustry: '',
      collectiveIncomeDesc: '',
      collectiveIncomeAmount: 0,
    },
  }
  return { ...(defaults[key] || {}) }
}

function resetFormData() {
  const defaults = getDefaultFormData(props.sectionKey)
  Object.keys(formData).forEach((k) => delete formData[k])
  Object.assign(formData, defaults)
}

// 加载年度数据
async function loadSectionData() {
  resetFormData()
  committeeMembers.value = []
  try {
    const data = await getYearlyData(props.villageId, selectedYear.value)
    const apiKey = resolveApiKey(props.sectionKey)
    if (apiKey && (data as any)[apiKey]) {
      const sectionData = (data as any)[apiKey]
      Object.keys(formData).forEach((k) => {
        if (sectionData[k] !== undefined && sectionData[k] !== null) {
          formData[k] = sectionData[k]
        }
      })
      // 村委会板块加载成员列表
      if (props.sectionKey === 'committee' && sectionData.members) {
        committeeMembers.value = sectionData.members.map((m: any) => ({
          name: m.name || '',
          position: m.position || '',
          phone: m.phone || '',
          isVeteran: Boolean(m.isVeteran),
          remark: m.remark || '',
        }))
      }
    }
  } catch {
    // 无数据时使用默认值
  }
}

// 加载附件列表
async function loadAttachments() {
  try {
    attachments.value = await getSectionAttachments(props.villageId, props.sectionKey)
  } catch {
    attachments.value = []
  }
}

function handleYearChange() {
  loadSectionData()
  loadAttachments()
}

// 保存数据 — 只保存当前板块
const saveFnMap: Record<string, (villageId: number, year: number, data: any) => Promise<any>> = {
  population: savePopulationData,
  income: saveIncomeData,
  force_investment: saveForceInvestmentData,
  industry: saveIndustryData,
  infrastructure: saveInfrastructureData,
  party_building: savePartyBuildingData,
  medical: saveMedicalData,
  consumption: saveConsumptionData,
  employment: saveEmploymentData,
  education: saveEducationData,
  committee: (villageId: number, year: number, data: any) =>
    saveCommitteeData(villageId, {
      ...data,
      year,
      members: committeeMembers.value,
    }),
}

async function handleSave() {
  // Validate form before saving
  if (formRef.value) {
    try {
      await formRef.value.validate()
    } catch {
      ElMessage.warning('请完善必填信息后再保存')
      return
    }
  }

  const saveFn = saveFnMap[props.sectionKey]
  if (!saveFn) {
    ElMessage.error('未知板块类型')
    return
  }
  saving.value = true
  try {
    await saveFn(props.villageId, selectedYear.value, { ...formData })
    ElMessage.success('保存成功')
    emit('saved')
    emit('close')
  } catch (error: any) {
    logger.error('保存失败:', error)
    ElMessage.error(error?.message || '保存失败，请重试')
  } finally {
    saving.value = false
  }
}

function handleClose() {
  emit('close')
}

// ==================== 文件上传相关 ====================

function handleBeforeUpload(file: UploadRawFile) {
  const maxSize = 20 * 1024 * 1024 // 20MB
  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过20MB')
    return false
  }
  return true
}

function handleExceed() {
  ElMessage.warning('最多上传10个文件')
}

async function handleCustomUpload(options: UploadRequestOptions) {
  try {
    const att = await uploadSectionAttachment(props.villageId, props.sectionKey, options.file)
    attachments.value.push(att)
    ElMessage.success('上传成功')
  } catch (error: any) {
    ElMessage.error(error?.message || '上传失败')
  }
}

function handleUploadRemove(_file: UploadFile) {
  // el-upload 自带的移除只影响待上传列表，已上传附件通过 handleDeleteAttachment 删除
}

async function handleDeleteAttachment(att: SectionAttachment) {
  try {
    await ElMessageBox.confirm(`确定删除文件 "${att.fileName}" 吗？`, '删除确认')
  } catch {
    return
  }
  try {
    await deleteSectionAttachment(props.villageId, props.sectionKey, att.id)
    attachments.value = attachments.value.filter((a) => a.id !== att.id)
    ElMessage.success('删除成功')
  } catch (error: any) {
    ElMessage.error(error?.message || '删除失败')
  }
}

// ==================== 文件预览相关 ====================

function isPreviewable(fileType?: string): boolean {
  const type = (fileType ?? '').toLowerCase()
  return (
    type.startsWith('image/') ||
    type === 'application/pdf' ||
    /\.(jpg|jpeg|png|gif|bmp|webp|pdf)$/i.test(type)
  )
}

function getPreviewType(fileType?: string): 'image' | 'pdf' | 'other' {
  const type = (fileType ?? '').toLowerCase()
  if (type.startsWith('image/') || /\.(jpg|jpeg|png|gif|bmp|webp)$/i.test(type)) {
    return 'image'
  }
  if (type === 'application/pdf' || type.endsWith('.pdf')) {
    return 'pdf'
  }
  return 'other'
}

function handlePreview(att: SectionAttachment) {
  previewAttachment.value = att
  previewTitle.value = att.fileName
  previewUrl.value = att.fileUrl
  previewType.value = getPreviewType(att.fileType)
  previewVisible.value = true
}

function handleDownload(att: SectionAttachment) {
  const link = document.createElement('a')
  link.href = att.fileUrl
  link.setAttribute('download', att.fileName)
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// ==================== 初始化 ====================

onMounted(() => {
  resetFormData()
  loadSectionData()
  loadAttachments()
})
</script>

<style scoped>
.section-data-form {
  padding: 10px 0;
}

/* 确保 input-number 有足够最小宽度 */
.section-data-form :deep(.el-input-number) {
  min-width: 140px;
}

.section-data-form :deep(.el-form-item__label) {
  font-size: 13px;
}

/* 印证资料区域 */
.attachment-section {
  padding: 0 20px;
}

.upload-tip {
  font-size: 12px;
  color: var(--color-info);
  margin-top: 4px;
}

.attachment-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attachment-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  transition: background 0.2s;
}

.attachment-item:hover {
  background: var(--color-primary-light-8);
}

.attachment-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.file-icon {
  color: var(--color-primary);
  flex-shrink: 0;
}

.file-name {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: var(--color-info);
  flex-shrink: 0;
}

.attachment-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.no-attachment {
  color: #bbb;
  font-size: 13px;
  padding: 12px 0;
}

/* 预览弹窗 */
.preview-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.preview-image {
  max-width: 100%;
  max-height: 70vh;
  border-radius: 4px;
}

.preview-pdf {
  width: 100%;
  height: 70vh;
  border: none;
  border-radius: 4px;
}

.preview-unsupported {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: var(--color-info);
}
</style>
