import { describe, it, expect } from 'vitest'
import {
  FUND_TYPES,
  FUND_STATUS,
  PROJECT_STATUS,
  PROJECT_TYPES,
  POLICY_LEVELS,
  POLICY_STATUS,
  APPROVAL_STATUS,
  APPROVAL_ACTIONS,
  ENTITY_TYPES,
  TASK_PRIORITY,
  getFundTypeLabel,
  getFundStatusLabel,
  getProjectStatusLabel,
  getProjectTypeLabel,
  getApprovalStatusLabel,
  getApprovalActionLabel,
  getEntityTypeLabel,
  getTaskPriorityLabel,
} from '@/config/enums'

describe('config/enums', () => {
  it('FUND_TYPES 常量', () => {
    expect(FUND_TYPES.project).toBe('项目经费')
    expect(FUND_TYPES.operation).toBe('运营经费')
    expect(FUND_TYPES.education).toBe('教育经费')
    expect(FUND_TYPES.infrastructure).toBe('基建经费')
    expect(FUND_TYPES.emergency).toBe('应急经费')
  })

  it('FUND_STATUS 常量', () => {
    expect(FUND_STATUS.pending).toBe('待审批')
    expect(FUND_STATUS.approved).toBe('已审批')
    expect(FUND_STATUS.allocated).toBe('已拨付')
    expect(FUND_STATUS.in_use).toBe('使用中')
    expect(FUND_STATUS.completed).toBe('已完成')
    expect(FUND_STATUS.cancelled).toBe('已取消')
  })

  it('PROJECT_STATUS 八态常量（含后端 draft/pending/approved）', () => {
    expect(PROJECT_STATUS.draft).toBe('草稿')
    expect(PROJECT_STATUS.pending).toBe('待审批')
    expect(PROJECT_STATUS.approved).toBe('已审批')
    expect(PROJECT_STATUS.planning).toBe('规划中')
    expect(PROJECT_STATUS.in_progress).toBe('进行中')
    expect(PROJECT_STATUS.completed).toBe('已完成')
    expect(PROJECT_STATUS.cancelled).toBe('已取消')
    expect(PROJECT_STATUS.suspended).toBe('已暂停')
  })

  it('PROJECT_TYPES 常量', () => {
    expect(PROJECT_TYPES.infrastructure).toBe('基础设施')
    expect(PROJECT_TYPES.industry).toBe('产业发展')
    expect(PROJECT_TYPES.education).toBe('教育帮扶')
    expect(PROJECT_TYPES.medical).toBe('医疗帮扶')
    expect(PROJECT_TYPES.ecology).toBe('生态建设')
    expect(PROJECT_TYPES.party_building).toBe('党建引领')
  })

  it('POLICY_LEVELS 常量', () => {
    expect(POLICY_LEVELS.national).toBe('国家级')
    expect(POLICY_LEVELS.provincial).toBe('省级')
    expect(POLICY_LEVELS.municipal).toBe('市级')
    expect(POLICY_LEVELS.county).toBe('县级')
    expect(POLICY_LEVELS.department).toBe('部门级')
  })

  it('POLICY_STATUS 常量', () => {
    expect(POLICY_STATUS.draft).toBe('草稿')
    expect(POLICY_STATUS.published).toBe('已发布')
    expect(POLICY_STATUS.expired).toBe('已过期')
    expect(POLICY_STATUS.revoked).toBe('已撤销')
  })

  it('APPROVAL_STATUS 四态常量', () => {
    expect(APPROVAL_STATUS.pending).toBe('待审批')
    expect(APPROVAL_STATUS.approved).toBe('已通过')
    expect(APPROVAL_STATUS.rejected).toBe('已驳回')
    expect(APPROVAL_STATUS.withdrawn).toBe('已撤回')
  })

  it('APPROVAL_ACTIONS 常量（含转交）', () => {
    expect(APPROVAL_ACTIONS.approve).toBe('通过')
    expect(APPROVAL_ACTIONS.reject).toBe('拒绝')
    expect(APPROVAL_ACTIONS.transfer).toBe('转交')
  })

  it('ENTITY_TYPES 全量常量（含 rural_work/assessment）', () => {
    expect(ENTITY_TYPES.supported_village).toBe('帮扶村')
    expect(ENTITY_TYPES.village).toBe('帮扶村')
    expect(ENTITY_TYPES.project).toBe('项目')
    expect(ENTITY_TYPES.fund).toBe('经费')
    expect(ENTITY_TYPES.school).toBe('学校')
    expect(ENTITY_TYPES.rural_work).toBe('乡村工作')
    expect(ENTITY_TYPES.assessment).toBe('考核复核')
    expect(ENTITY_TYPES.policy).toBe('政策')
    expect(ENTITY_TYPES.other).toBe('其他')
  })

  it('TASK_PRIORITY 常量', () => {
    expect(TASK_PRIORITY.low).toBe('低')
    expect(TASK_PRIORITY.normal).toBe('普通')
    expect(TASK_PRIORITY.medium).toBe('中')
    expect(TASK_PRIORITY.high).toBe('高')
    expect(TASK_PRIORITY.urgent).toBe('紧急')
  })

  describe('getFundTypeLabel', () => {
    it('已知类型返回中文标签', () => {
      expect(getFundTypeLabel('project')).toBe('项目经费')
    })
    it('未知类型原样返回', () => {
      expect(getFundTypeLabel('unknown')).toBe('unknown')
    })
  })

  describe('getFundStatusLabel', () => {
    it('已知状态返回中文标签', () => {
      expect(getFundStatusLabel('allocated')).toBe('已拨付')
    })
    it('未知状态原样返回', () => {
      expect(getFundStatusLabel('weird')).toBe('weird')
    })
  })

  describe('getProjectStatusLabel', () => {
    it('已知状态返回中文标签', () => {
      expect(getProjectStatusLabel('in_progress')).toBe('进行中')
    })
    it('未知状态原样返回', () => {
      expect(getProjectStatusLabel('x')).toBe('x')
    })
  })

  describe('getProjectTypeLabel', () => {
    it('已知类型返回中文标签', () => {
      expect(getProjectTypeLabel('medical')).toBe('医疗帮扶')
    })
    it('未知类型原样返回', () => {
      expect(getProjectTypeLabel('y')).toBe('y')
    })
  })

  describe('getApprovalStatusLabel', () => {
    it('已知状态返回中文标签', () => {
      expect(getApprovalStatusLabel('pending')).toBe('待审批')
      expect(getApprovalStatusLabel('approved')).toBe('已通过')
      expect(getApprovalStatusLabel('rejected')).toBe('已驳回')
      expect(getApprovalStatusLabel('withdrawn')).toBe('已撤回')
    })
    it('未知状态原样返回', () => {
      expect(getApprovalStatusLabel('xyz')).toBe('xyz')
    })
  })

  describe('getApprovalActionLabel', () => {
    it('已知操作返回中文标签（含转交）', () => {
      expect(getApprovalActionLabel('approve')).toBe('通过')
      expect(getApprovalActionLabel('reject')).toBe('拒绝')
      expect(getApprovalActionLabel('transfer')).toBe('转交')
    })
    it('未知操作原样返回', () => {
      expect(getApprovalActionLabel('xyz')).toBe('xyz')
    })
  })

  describe('getEntityTypeLabel', () => {
    it('已知实体类型返回中文标签（含 rural_work/assessment）', () => {
      expect(getEntityTypeLabel('supported_village')).toBe('帮扶村')
      expect(getEntityTypeLabel('village')).toBe('帮扶村')
      expect(getEntityTypeLabel('project')).toBe('项目')
      expect(getEntityTypeLabel('fund')).toBe('经费')
      expect(getEntityTypeLabel('school')).toBe('学校')
      expect(getEntityTypeLabel('rural_work')).toBe('乡村工作')
      expect(getEntityTypeLabel('assessment')).toBe('考核复核')
      expect(getEntityTypeLabel('policy')).toBe('政策')
      expect(getEntityTypeLabel('other')).toBe('其他')
    })
    it('未知实体类型原样返回', () => {
      expect(getEntityTypeLabel('xyz')).toBe('xyz')
    })
  })

  describe('getTaskPriorityLabel', () => {
    it('已知优先级返回中文标签', () => {
      expect(getTaskPriorityLabel('low')).toBe('低')
      expect(getTaskPriorityLabel('normal')).toBe('普通')
      expect(getTaskPriorityLabel('medium')).toBe('中')
      expect(getTaskPriorityLabel('high')).toBe('高')
      expect(getTaskPriorityLabel('urgent')).toBe('紧急')
    })
    it('未知优先级原样返回', () => {
      expect(getTaskPriorityLabel('xyz')).toBe('xyz')
    })
  })
})
